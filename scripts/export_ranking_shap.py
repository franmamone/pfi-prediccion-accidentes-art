"""Regenera ranking_maestro_{1m|3m}_{periodo}.json con contribuciones SHAP individuales."""

from __future__ import annotations

import argparse
import json

import pandas as pd

from _bootstrap import SRC  # noqa: F401

from pfi_prediccion.config import HORIZON_1M, HORIZON_3M, PANEL_PARQUET
from pfi_prediccion.ranking_policy import export_ranking_contract


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta ranking operativo con SHAP top-225")
    parser.add_argument("--periodo", default="2025-11", help="Período YYYY-MM")
    parser.add_argument(
        "--horizonte",
        choices=["1m", "3m", "ambos"],
        default="ambos",
        help="Horizonte a exportar",
    )
    args = parser.parse_args()

    panel = pd.read_parquet(PANEL_PARQUET)
    horizons = [HORIZON_1M, HORIZON_3M] if args.horizonte == "ambos" else [args.horizonte]
    results = []
    for horizon in horizons:
        print(f"[export] ranking+SHAP horizonte={horizon} periodo={args.periodo}...", flush=True)
        result = export_ranking_contract(panel, horizon=horizon, periodo=args.periodo)
        results.append(result)
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)

    print(json.dumps({"ok": True, "exports": len(results)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
