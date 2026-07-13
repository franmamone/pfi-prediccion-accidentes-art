from __future__ import annotations

import argparse
import json

import pandas as pd

from _bootstrap import SRC  # noqa: F401

from pfi_prediccion.config import PANEL_PARQUET, REPORTS_DIR, ensure_dirs
from pfi_prediccion.explain import run_shap_explain


def main() -> None:
    parser = argparse.ArgumentParser(description="Genera reportes SHAP del modelo entrenado.")
    parser.add_argument("--input", type=str, default=str(PANEL_PARQUET))
    parser.add_argument("--reports-dir", type=str, default=str(REPORTS_DIR))
    parser.add_argument("--sample-rows", type=int, default=500)
    args = parser.parse_args()

    ensure_dirs()
    panel = pd.read_parquet(args.input)
    result = run_shap_explain(
        panel,
        reports_dir=args.reports_dir,
        sample_rows=args.sample_rows,
    )
    print(json.dumps({"ok": True, **result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
