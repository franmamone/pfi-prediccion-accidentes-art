"""Política operativa: ranking maestro consumible por API/app React."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import pandas as pd

from .config import (
    BAND_ACCURACY_THRESHOLDS,
    CAPACITY_CRITICAL,
    CAPACITY_MONTHLY,
    CAPACITY_QUARTERLY,
    DATA_END,
    HORIZON_1M,
    HORIZON_3M,
    PROCESSED_DIR,
    REPORTS_RANKING_DIR,
    VISIT_COOLDOWN_MONTHS,
    banda_por_acierto,
    ensure_dirs,
    model_pipeline_path,
    target_column_for_horizon,
)
from .features import ciiu_seccion, sector_label
from .inference import predict_blended_batched
from .ranking_explain import explain_ranking_items


def _sector_label(code) -> str:
    return sector_label(code)


def _band(rank: int, horizon: str = HORIZON_1M) -> str:
    """Banda por acierto histórico del tramo (ver config.banda_por_acierto)."""
    return banda_por_acierto(rank, horizon)


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
    month["banda"] = month["ranking"].map(lambda r: _band(int(r), horizon))
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
    export_n: int = CAPACITY_MONTHLY,
) -> dict:
    """Exporta CSV/JSON con el contrato que consumirá la API .NET / React.

    ``export_n`` controla cuántos establecimientos (top del ranking) se
    exportan con SHAP individual. Por defecto la capacidad mensual (225);
    subirlo (p. ej. 1000) permite mostrar también la banda ``medio``.
    """
    ensure_dirs()
    output_dir = Path(output_dir or REPORTS_RANKING_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    export_n = max(int(export_n or CAPACITY_MONTHLY), 1)

    ranking = build_master_ranking(panel, periodo=periodo, horizon=horizon)
    periodo = str(ranking["periodo"].iloc[0])

    # SHAP individual sobre el top operativo: requiere features completas del panel del mes.
    month_panel = panel[panel["periodo"] == periodo].copy()
    month_panel = month_panel.merge(
        ranking[["id_establecimiento", "score_riesgo", "ranking"]],
        on="id_establecimiento",
        how="inner",
        suffixes=("", "_rank"),
    )
    if "score_riesgo_rank" in month_panel.columns:
        month_panel["score_riesgo"] = month_panel["score_riesgo_rank"]
        month_panel = month_panel.drop(columns=["score_riesgo_rank"])
    shap_by_id, shap_agregados = explain_ranking_items(
        month_panel, horizon=horizon, top_n=export_n
    )
    additivity_ok = sum(1 for v in shap_by_id.values() if v.get("additivity_ok"))
    additivity_fail = len(shap_by_id) - additivity_ok

    csv_path = output_dir / f"ranking_maestro_{horizon}_{periodo}.csv"
    json_path = output_dir / f"ranking_maestro_{horizon}_{periodo}.json"
    contract_path = output_dir / "ranking_contract.json"

    ranking.to_csv(csv_path, index=False, sep=";")

    items = ranking.head(export_n).to_dict(orient="records")
    # Evitar NaN/NaT en JSON (targets futuros no evaluables).
    for item in items:
        for key, value in list(item.items()):
            if value is None:
                continue
            if isinstance(value, float) and (pd.isna(value) or value != value):
                item[key] = None
            elif pd.isna(value):
                item[key] = None
        est_id = str(item["id_establecimiento"])
        shap_info = shap_by_id.get(est_id)
        if not shap_info:
            item["contribuciones"] = []
            item["motivo_principal"] = None
            continue
        item["contribuciones"] = shap_info["contribuciones"]
        item["motivo_principal"] = shap_info.get("motivo_principal")

    model_path = model_pipeline_path(horizon)
    modelo_version = model_path.name
    if "data_end" in panel.columns and panel["data_end"].notna().any():
        datos_hasta = str(panel.loc[panel["data_end"].notna(), "data_end"].iloc[0])
    else:
        datos_hasta = DATA_END

    payload = {
        "periodo": periodo,
        "horizonte": horizon,
        "generado_para": "api_dotnet / react_app",
        "modelo_version": modelo_version,
        "datos_hasta": datos_hasta,
        "politica": {
            "capacidad_criticos": CAPACITY_CRITICAL,
            "capacidad_mensual": CAPACITY_MONTHLY,
            "capacidad_trimestral": CAPACITY_QUARTERLY,
            "cooldown_meses": VISIT_COOLDOWN_MONTHS,
            "bandas_criterio": "acierto histórico (precision@K) del tramo",
            "bandas_umbrales": BAND_ACCURACY_THRESHOLDS.get(horizon, {}),
            "bandas": {
                b: f"acierto {int(round(v * 100))}%+"
                for b, v in (BAND_ACCURACY_THRESHOLDS.get(horizon, {}) or {}).items()
            },
            "motivos": ["predictivo", "predictivo+prs", "prs", "seguimiento"],
            "reglas": [
                "Una sola lista maestra; filtros por sector sin forzar top-50 por rubro.",
                "Cola PRS obligatoria separada de la predictiva.",
                "Establecimientos en cooldown se marcan pero no se excluyen automáticamente de la vista.",
                "Score = prioridad relativa, no probabilidad calibrada por defecto.",
                "contribuciones SHAP = aporte en escala interna del modelo (margen), no probabilidad ni % del puntaje.",
                "shap_agregados = media exacta sobre matriz completa top-K (no promedia los 5 factores truncados).",
            ],
        },
        "totales": {
            "filas": len(ranking),
            "criticos": int((ranking["banda"] == "critico").sum()),
            "altos": int((ranking["banda"] == "alto").sum()),
            "medios": int((ranking["banda"] == "medio").sum()),
            "bajos": int((ranking["banda"] == "bajo").sum()),
            "en_cooldown": int(ranking["en_cooldown"].sum()),
            "con_obligacion_prs": int(ranking["obligacion_prs"].sum()),
            "shap_explicados": len(shap_by_id),
            "shap_aditividad_ok": additivity_ok,
            "shap_aditividad_fail": additivity_fail,
        },
        "shap_agregados": shap_agregados,
        "items": items,
    }
    # Hash estable del contenido analítico (sin timestamps).
    hash_body = json.dumps(
        {
            "periodo": periodo,
            "horizonte": horizon,
            "modelo_version": modelo_version,
            "datos_hasta": datos_hasta,
            "items": [
                {
                    "id": i["id_establecimiento"],
                    "ranking": i["ranking"],
                    "score": round(float(i["score_riesgo"]), 6),
                }
                for i in items
            ],
            "shap_agregados": shap_agregados,
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    payload["artifact_hash"] = hashlib.sha256(hash_body).hexdigest()

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
        "shap_explicados": len(shap_by_id),
        "shap_aditividad_ok": additivity_ok,
        "artifact_hash": payload["artifact_hash"],
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
