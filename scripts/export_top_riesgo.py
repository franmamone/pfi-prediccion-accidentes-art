"""Exporta el ranking de mayor riesgo del último mes disponible en el panel."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import pandas as pd

from _bootstrap import SRC  # noqa: F401

from pfi_prediccion.config import MODEL_PIPELINE_PATH, PANEL_PARQUET, REPORTS_RANKING_DIR, ensure_dirs
from pfi_prediccion.inference import predict_blended_batched


def main() -> None:
    parser = argparse.ArgumentParser(description="Ranking top-N establecimientos en mayor riesgo.")
    parser.add_argument("--top", type=int, default=200, help="Cantidad de filas a exportar")
    parser.add_argument(
        "--periodo",
        type=str,
        default=None,
        help="Período feature (YYYY-MM). Por defecto, el último del panel.",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(REPORTS_RANKING_DIR / "top_riesgo.csv"),
        help="CSV de salida (;)",
    )
    args = parser.parse_args()

    ensure_dirs()
    panel = pd.read_parquet(PANEL_PARQUET)
    artifact = joblib.load(MODEL_PIPELINE_PATH)
    threshold = float(artifact["threshold"])
    features = artifact["features"]

    periodo = args.periodo or panel["periodo"].max()
    subset = panel[panel["periodo"] == periodo].copy()
    if subset.empty:
        raise ValueError(f"No hay filas para el período {periodo}")

    subset["score_riesgo"] = predict_blended_batched(artifact, subset[features])
    subset["alerta"] = (subset["score_riesgo"] >= threshold).astype(int)
    subset["rank"] = subset["score_riesgo"].rank(ascending=False, method="first").astype(int)

    cols = [
        "rank",
        "id_establecimiento",
        "id_empleador",
        "periodo",
        "periodo_objetivo",
        "score_riesgo",
        "alerta",
        "accidentes_3m",
        "accidentes_6m",
        "accidentes_12m",
        "actividad_ciiu_establecimiento",
        "id_provincia_establecimiento",
        "dotacion_establecimiento",
    ]
    cols = [c for c in cols if c in subset.columns]
    out = subset.sort_values("score_riesgo", ascending=False).head(args.top)[cols]

    output_path = Path(args.output)
    out.to_csv(output_path, index=False, sep=";")

    print(
        json.dumps(
            {
                "ok": True,
                "periodo": periodo,
                "periodo_objetivo": out["periodo_objetivo"].iloc[0] if len(out) else None,
                "top": args.top,
                "filas_exportadas": len(out),
                "threshold": threshold,
                "output": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
