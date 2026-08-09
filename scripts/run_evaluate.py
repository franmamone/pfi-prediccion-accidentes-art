"""Re-evalúa el modelo (sin reentrenar) para regenerar reports de holdout.

Usa el artifact ya entrenado y el panel existente. Regenera
top_k_per_month_{1m|3m}.json y evaluation_metrics_{1m|3m}.json con los
tramos de TOP_K_PER_MONTH vigentes (incluye 500/675/1000).
"""

from __future__ import annotations

import argparse
import json

import pandas as pd

from _bootstrap import SRC  # noqa: F401

from pfi_prediccion.config import (
    HORIZON_1M,
    HORIZON_3M,
    PANEL_PARQUET,
    target_column_for_horizon,
)
from pfi_prediccion.evaluate import evaluate_model


def main() -> None:
    parser = argparse.ArgumentParser(description="Evalúa (sin entrenar) y regenera reports")
    parser.add_argument("--horizonte", choices=["1m", "3m", "ambos"], default="ambos")
    args = parser.parse_args()

    panel = pd.read_parquet(PANEL_PARQUET)
    horizons = [HORIZON_1M, HORIZON_3M] if args.horizonte == "ambos" else [args.horizonte]
    for horizon in horizons:
        target = target_column_for_horizon(horizon)
        print(f"[evaluate] horizonte={horizon} target={target}...", flush=True)
        result = evaluate_model(panel, horizon=horizon, target_column=target)
        print(
            json.dumps(
                {"horizonte": horizon, "top_k_per_month": result.get("top_k_per_month")},
                ensure_ascii=False,
                default=str,
            ),
            flush=True,
        )

    print(json.dumps({"ok": True, "horizons": horizons}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
