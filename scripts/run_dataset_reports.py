"""Genera gráficos de reporte del dataset completo (accidentes + panel + modelo)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from _bootstrap import SRC  # noqa: F401

from pfi_prediccion.columns import normalize_accidents_df
from pfi_prediccion.config import ACCIDENTS_PARQUET, PANEL_PARQUET, REPORTS_DIR, ensure_dirs
from pfi_prediccion.dataset_reports import run_dataset_reports
from pfi_prediccion.eda import run_eda


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gráficos de reporte: accidentes, panel, modelo y catálogo explicativo."
    )
    parser.add_argument("--accidents", type=str, default=str(ACCIDENTS_PARQUET))
    parser.add_argument("--panel", type=str, default=str(PANEL_PARQUET))
    parser.add_argument("--output-dir", type=str, default=str(REPORTS_DIR))
    parser.add_argument(
        "--skip-eda",
        action="store_true",
        help="No regenerar gráficos EDA básicos (solo reportes extendidos)",
    )
    args = parser.parse_args()

    ensure_dirs()
    accidents = normalize_accidents_df(pd.read_parquet(args.accidents))

    panel = None
    panel_path = args.panel
    if panel_path and Path(panel_path).exists():
        panel = pd.read_parquet(panel_path)

    if not args.skip_eda:
        print("[reports] EDA básico de accidentes...", flush=True)
        run_eda(accidents, output_dir=args.output_dir)

    result = run_dataset_reports(accidents, panel=panel, output_dir=args.output_dir)
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
