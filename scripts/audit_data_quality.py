"""Controles de calidad por mes: accidentes, visitas, nómina y anomalías."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from _bootstrap import SRC  # noqa: F401

from pfi_prediccion.columns import (
    normalize_accidents_df,
    normalize_nomina_df,
    normalize_prevencion_df,
    normalize_universe_df,
)
from pfi_prediccion.config import (
    ACCIDENTS_PARQUET,
    NOMINA_PARQUET,
    PREVENCION_PARQUET,
    REPORTS_DATASET_DIR,
    UNIVERSE_PARQUET,
    ensure_dirs,
)


def _month_counts_accidents(accidents: pd.DataFrame) -> pd.DataFrame:
    df = accidents.copy()
    df["fecha_hora_accidente"] = pd.to_datetime(df["fecha_hora_accidente"])
    df["periodo"] = df["fecha_hora_accidente"].dt.to_period("M").astype(str)
    out = (
        df.groupby("periodo", as_index=False)
        .agg(
            accidentes=("id_accidente", "count")
            if "id_accidente" in df.columns
            else ("id_establecimiento", "size"),
            establecimientos=("id_establecimiento", "nunique"),
        )
        .sort_values("periodo")
    )
    return out


def _month_counts_simple(df: pd.DataFrame, value_col: str, name: str) -> pd.DataFrame:
    if df is None or df.empty or "periodo" not in df.columns:
        return pd.DataFrame(columns=["periodo", name])
    tmp = df.copy()
    tmp[value_col] = pd.to_numeric(tmp[value_col], errors="coerce").fillna(0)
    return (
        tmp.groupby("periodo", as_index=False)
        .agg(**{name: (value_col, "sum"), "filas": ("id_establecimiento", "size")})
        .sort_values("periodo")
    )


def audit(
    accidents: pd.DataFrame,
    prevencion: pd.DataFrame | None,
    nomina: pd.DataFrame | None,
    universe: pd.DataFrame | None,
) -> dict:
    acc_m = _month_counts_accidents(accidents)
    anomalies: list[dict] = []

    if not acc_m.empty:
        med = float(acc_m["accidentes"].median())
        for _, row in acc_m.iterrows():
            if med > 0 and row["accidentes"] > 3 * med:
                anomalies.append(
                    {
                        "tipo": "pico_accidentes",
                        "periodo": row["periodo"],
                        "valor": int(row["accidentes"]),
                        "mediana": med,
                    }
                )

    prev_m = None
    if prevencion is not None and not prevencion.empty:
        prev_m = _month_counts_simple(prevencion, "visitas_realizadas_mes", "visitas_realizadas")
        if not prev_m.empty:
            med = float(prev_m["visitas_realizadas"].median())
            for _, row in prev_m.iterrows():
                if med > 0 and row["visitas_realizadas"] > 5 * med:
                    anomalies.append(
                        {
                            "tipo": "pico_visitas",
                            "periodo": row["periodo"],
                            "valor": int(row["visitas_realizadas"]),
                            "mediana": med,
                            "nota": "Posible carga masiva; revisar antes de usar como baseline operativo.",
                        }
                    )

    nom_m = None
    cobertura_nomina = None
    if nomina is not None and not nomina.empty:
        nom_m = (
            nomina.groupby("periodo", as_index=False)
            .agg(
                establecimientos_con_nomina=("id_establecimiento", "nunique"),
                dotacion_total=("dotacion_nomina_mes", "sum"),
            )
            .sort_values("periodo")
        )
        if universe is not None and not universe.empty:
            n_uni = universe["id_establecimiento"].nunique()
            cobertura_nomina = {
                "establecimientos_universo": int(n_uni),
                "establecimientos_con_nomina_alguna_vez": int(
                    nomina["id_establecimiento"].nunique()
                ),
                "pct_universo_con_nomina": round(
                    100 * nomina["id_establecimiento"].nunique() / n_uni, 2
                )
                if n_uni
                else None,
            }

    # Atributos potencialmente "as-of-today" en universo (riesgo de leakage temporal)
    leakage_flags = {
        "universo_es_snapshot_actual": True,
        "campos_potencialmente_no_historicos": [
            "cantidad_capitas",
            "nivel_seguridad_empleador",
            "nivel_seguridad_establecimiento",
            "actividad_ciiu_establecimiento",
            "actividad_ciiu_empleador",
            "antiguedad_establecimiento_meses",
        ],
        "mitigacion": (
            "Usar estos campos como proxy estático documentado; "
            "no interpretar como serie temporal reconstruida. "
            "Historial de accidentes/visitas/nómina sí es temporal."
        ),
    }

    return {
        "periodo_accidentes_min": acc_m["periodo"].min() if not acc_m.empty else None,
        "periodo_accidentes_max": acc_m["periodo"].max() if not acc_m.empty else None,
        "accidentes_por_mes": acc_m.to_dict(orient="records"),
        "visitas_por_mes": prev_m.to_dict(orient="records") if prev_m is not None else [],
        "nomina_por_mes": nom_m.to_dict(orient="records") if nom_m is not None else [],
        "cobertura_nomina": cobertura_nomina,
        "anomalias": anomalies,
        "leakage_atributos_estaticos": leakage_flags,
        "recomendacion_export": (
            "Desplegar vistas SQL actualizadas (hasta 2025-12), exportar CSV desde SSMS "
            "y convertir a parquet con scripts/*_csv_to_parquet.py"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Auditoría de calidad de datos ML.")
    parser.add_argument("--output", type=str, default=str(REPORTS_DATASET_DIR / "data_quality_audit.json"))
    args = parser.parse_args()

    ensure_dirs()
    accidents = normalize_accidents_df(pd.read_parquet(ACCIDENTS_PARQUET))
    prevencion = (
        normalize_prevencion_df(pd.read_parquet(PREVENCION_PARQUET))
        if PREVENCION_PARQUET.exists()
        else None
    )
    nomina = (
        normalize_nomina_df(pd.read_parquet(NOMINA_PARQUET)) if NOMINA_PARQUET.exists() else None
    )
    universe = (
        normalize_universe_df(pd.read_parquet(UNIVERSE_PARQUET))
        if UNIVERSE_PARQUET.exists()
        else None
    )

    result = audit(accidents, prevencion, nomina, universe)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": True, "output": str(out), "anomalias": len(result["anomalias"])}, indent=2))


if __name__ == "__main__":
    main()
