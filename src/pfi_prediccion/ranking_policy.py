"""Política operativa: ranking maestro consumible por API/app React."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd

from .config import (
    CAPACITY_CRITICAL,
    CAPACITY_MONTHLY,
    CAPACITY_QUARTERLY,
    HORIZON_1M,
    HORIZON_3M,
    PROCESSED_DIR,
    REPORTS_RANKING_DIR,
    VISIT_COOLDOWN_MONTHS,
    ensure_dirs,
    model_pipeline_path,
    target_column_for_horizon,
)
from .features import ciiu_seccion
from .inference import predict_blended_batched


SECTOR_LABELS = {
    "41": "Construcción",
    "42": "Construcción",
    "43": "Construcción",
    "10": "Industria",
    "11": "Industria",
    "12": "Industria",
    "13": "Industria",
    "14": "Industria",
    "15": "Industria",
    "16": "Industria",
    "17": "Industria",
    "18": "Industria",
    "19": "Industria",
    "20": "Industria",
    "21": "Industria",
    "22": "Industria",
    "23": "Industria",
    "24": "Industria",
    "25": "Industria",
    "26": "Industria",
    "27": "Industria",
    "28": "Industria",
    "29": "Industria",
    "30": "Industria",
    "31": "Industria",
    "32": "Industria",
    "33": "Industria",
    "45": "Comercio",
    "46": "Comercio",
    "47": "Comercio",
    "49": "Transporte",
    "50": "Transporte",
    "51": "Transporte",
    "52": "Transporte",
    "53": "Transporte",
    "86": "Salud",
    "87": "Salud",
    "88": "Salud",
}


def _sector_label(code) -> str:
    sec = ciiu_seccion(code)
    return SECTOR_LABELS.get(sec, "Otros")


def _band(rank: int) -> str:
    if rank <= CAPACITY_CRITICAL:
        return "critico"
    if rank <= CAPACITY_MONTHLY:
        return "alto"
    return "medio"


def build_master_ranking(
    panel: pd.DataFrame,
    periodo: str | None = None,
    horizon: str = HORIZON_1M,
    pipeline_path: Path | None = None,
) -> pd.DataFrame:
    """Lista maestra de un período: ranking, banda, cooldown, sector, motivo."""
    target_col = target_column_for_horizon(horizon)
    path = Path(pipeline_path or model_pipeline_path(horizon))
    artifact = joblib.load(path)
    features = artifact["features"]
    threshold = float(artifact["threshold"])

    df = panel.copy()
    if periodo is None:
        # Último período con target evaluable o último del panel
        if target_col in df.columns and df[target_col].notna().any():
            periodo = str(df.loc[df[target_col].notna(), "periodo"].max())
        else:
            periodo = str(df["periodo"].max())

    month = df[df["periodo"] == periodo].copy()
    if month.empty:
        raise ValueError(f"No hay filas para periodo={periodo}")

    scores = predict_blended_batched(artifact, month[features])
    month = month.reset_index(drop=True)
    month["score_riesgo"] = scores
    month["alerta_umbral"] = (month["score_riesgo"] >= threshold).astype(int)
    month = month.sort_values("score_riesgo", ascending=False).reset_index(drop=True)
    month["ranking"] = month.index + 1
    month["banda"] = month["ranking"].map(_band)
    month["horizonte"] = horizon
    month["motivo"] = "predictivo"

    if "flag_pese_vigente" in month.columns:
        month.loc[month["flag_pese_vigente"].fillna(0).astype(int) == 1, "motivo"] = (
            month.loc[month["flag_pese_vigente"].fillna(0).astype(int) == 1, "motivo"].map(
                lambda m: "predictivo+prs" if m == "predictivo" else m
            )
        )
        month["obligacion_prs"] = month["flag_pese_vigente"].fillna(0).astype(int)
    else:
        month["obligacion_prs"] = 0

    if "meses_desde_ultima_visita" in month.columns:
        m = month["meses_desde_ultima_visita"]
        month["en_cooldown"] = (m.notna() & (m < VISIT_COOLDOWN_MONTHS)).astype(int)
        month["ultima_visita_hace_meses"] = m
    else:
        month["en_cooldown"] = 0
        month["ultima_visita_hace_meses"] = pd.NA

    if "actividad_ciiu_establecimiento" in month.columns:
        month["sector"] = month["actividad_ciiu_establecimiento"].map(_sector_label)
        month["ciiu_seccion"] = month["actividad_ciiu_establecimiento"].map(ciiu_seccion)
    else:
        month["sector"] = "Otros"
        month["ciiu_seccion"] = "NA"

    keep = [
        "periodo",
        "id_establecimiento",
        "id_empleador" if "id_empleador" in month.columns else None,
        "ranking",
        "score_riesgo",
        "banda",
        "horizonte",
        "motivo",
        "obligacion_prs",
        "en_cooldown",
        "ultima_visita_hace_meses",
        "sector",
        "ciiu_seccion",
        "cantidad_capitas" if "cantidad_capitas" in month.columns else None,
        "dotacion_nomina_mes" if "dotacion_nomina_mes" in month.columns else None,
        "alerta_umbral",
        target_col if target_col in month.columns else None,
    ]
    keep = [c for c in keep if c is not None]
    return month[keep]


def export_ranking_contract(
    panel: pd.DataFrame,
    horizon: str = HORIZON_1M,
    periodo: str | None = None,
    output_dir: Path | None = None,
) -> dict:
    """Exporta CSV/JSON con el contrato que consumirá la API .NET / React."""
    ensure_dirs()
    output_dir = Path(output_dir or REPORTS_RANKING_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    ranking = build_master_ranking(panel, periodo=periodo, horizon=horizon)
    periodo = str(ranking["periodo"].iloc[0])

    csv_path = output_dir / f"ranking_maestro_{horizon}_{periodo}.csv"
    json_path = output_dir / f"ranking_maestro_{horizon}_{periodo}.json"
    contract_path = output_dir / "ranking_contract.json"

    ranking.to_csv(csv_path, index=False, sep=";")

    payload = {
        "periodo": periodo,
        "horizonte": horizon,
        "generado_para": "api_dotnet / react_app",
        "politica": {
            "capacidad_criticos": CAPACITY_CRITICAL,
            "capacidad_mensual": CAPACITY_MONTHLY,
            "capacidad_trimestral": CAPACITY_QUARTERLY,
            "cooldown_meses": VISIT_COOLDOWN_MONTHS,
            "bandas": {
                "critico": f"ranking 1..{CAPACITY_CRITICAL}",
                "alto": f"ranking {CAPACITY_CRITICAL + 1}..{CAPACITY_MONTHLY}",
                "medio": f"ranking > {CAPACITY_MONTHLY}",
            },
            "motivos": ["predictivo", "predictivo+prs", "prs", "seguimiento"],
            "reglas": [
                "Una sola lista maestra; filtros por sector sin forzar top-50 por rubro.",
                "Cola PRS obligatoria separada de la predictiva.",
                "Establecimientos en cooldown se marcan pero no se excluyen automáticamente de la vista.",
                "Score = prioridad relativa, no probabilidad calibrada por defecto.",
            ],
        },
        "totales": {
            "filas": len(ranking),
            "criticos": int((ranking["banda"] == "critico").sum()),
            "altos": int((ranking["banda"] == "alto").sum()),
            "en_cooldown": int(ranking["en_cooldown"].sum()),
            "con_obligacion_prs": int(ranking["obligacion_prs"].sum()),
        },
        "items": ranking.head(CAPACITY_MONTHLY).to_dict(orient="records"),
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    contract = {
        "endpoint_sugerido": "GET /api/riesgo?periodo={periodo}&horizonte=1m|3m",
        "campos": [
            {"nombre": c, "descripcion": _field_doc(c)}
            for c in ranking.columns
        ],
        "ejemplo_archivo_csv": str(csv_path.name),
        "ejemplo_archivo_json": str(json_path.name),
    }
    contract_path.write_text(json.dumps(contract, indent=2, ensure_ascii=False), encoding="utf-8")

    # Copia procesada para jobs
    processed = PROCESSED_DIR / f"ranking_maestro_{horizon}.parquet"
    ranking.to_parquet(processed, index=False)

    return {
        "periodo": periodo,
        "horizon": horizon,
        "csv": str(csv_path),
        "json": str(json_path),
        "contract": str(contract_path),
        "parquet": str(processed),
        "totales": payload["totales"],
    }


def _field_doc(name: str) -> str:
    docs = {
        "periodo": "Mes de decisión (features conocidas al cierre del mes)",
        "id_establecimiento": "Hash anónimo del establecimiento",
        "id_empleador": "Hash anónimo del empleador",
        "ranking": "Posición 1 = mayor riesgo",
        "score_riesgo": "Score del modelo (prioridad relativa)",
        "banda": "critico | alto | medio",
        "horizonte": "1m o 3m",
        "motivo": "predictivo / predictivo+prs / ...",
        "obligacion_prs": "1 si hay programa PESE/PRS vigente",
        "en_cooldown": "1 si visitado hace < N meses",
        "ultima_visita_hace_meses": "Meses desde última visita realizada",
        "sector": "Rubro agrupado para UI",
        "ciiu_seccion": "Sección CIIU 2 dígitos",
        "alerta_umbral": "1 si score >= umbral F2",
    }
    return docs.get(name, name)
