from __future__ import annotations

import argparse
import json

from _bootstrap import SRC  # noqa: F401

from pfi_prediccion.config import ACCIDENTS_PARQUET, ensure_dirs, load_env
from pfi_prediccion.export import export_accidents_parquet


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta ml.vw_siniestros_accidente_ml a parquet.")
    parser.add_argument(
        "--output",
        type=str,
        default=str(ACCIDENTS_PARQUET),
        help="Ruta del parquet de salida",
    )
    args = parser.parse_args()

    load_env()
    ensure_dirs()

    output = export_accidents_parquet(output_path=args.output)
    print(json.dumps({"ok": True, "output": str(output)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
