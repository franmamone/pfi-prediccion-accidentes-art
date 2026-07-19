from __future__ import annotations

import argparse
import json

import pandas as pd

from _bootstrap import SRC  # noqa: F401

from pfi_prediccion.config import PANEL_PARQUET, REPORTS_MODEL_DIR, ensure_dirs
from pfi_prediccion.train import train_baseline


def main() -> None:
    parser = argparse.ArgumentParser(description="Entrena XGBoost sobre el panel y guarda métricas.")
    parser.add_argument(
        "--input",
        type=str,
        default=str(PANEL_PARQUET),
        help="Parquet del panel establecimiento×mes",
    )
    parser.add_argument(
        "--reports-dir",
        type=str,
        default=str(REPORTS_MODEL_DIR),
        help="Carpeta de métricas",
    )
    parser.add_argument("--dual", action="store_true", help="Modelo dual cold/warm")
    args = parser.parse_args()

    ensure_dirs()
    panel = pd.read_parquet(args.input)
    metrics = train_baseline(
        panel,
        reports_dir=args.reports_dir,
        dual_model=args.dual,
        full_retrain=args.full_retrain,
    )
    print(json.dumps({"ok": True, **metrics}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
