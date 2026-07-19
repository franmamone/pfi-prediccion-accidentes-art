from __future__ import annotations

import argparse
import json

import pandas as pd

from _bootstrap import SRC  # noqa: F401

from pfi_prediccion.columns import normalize_accidents_df
from pfi_prediccion.config import ACCIDENTS_PARQUET, REPORTS_EDA_DIR, ensure_dirs
from pfi_prediccion.eda import run_eda


def main() -> None:
    parser = argparse.ArgumentParser(description="EDA del dataset de accidentes.")
    parser.add_argument(
        "--input",
        type=str,
        default=str(ACCIDENTS_PARQUET),
        help="Parquet de accidentes",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(REPORTS_EDA_DIR),
        help="Carpeta de reportes",
    )
    args = parser.parse_args()

    ensure_dirs()
    accidents = normalize_accidents_df(pd.read_parquet(args.input))
    summary = run_eda(accidents, output_dir=args.output_dir)
    print(json.dumps({"ok": True, **summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
