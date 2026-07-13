"""Exporta el panel o accidentes parquet a CSV para abrir en Excel."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from _bootstrap import SRC  # noqa: F401

from pfi_prediccion.config import ACCIDENTS_PARQUET, PANEL_PARQUET, REPORTS_DIR, ensure_dirs


def main() -> None:
    parser = argparse.ArgumentParser(description="Exporta parquet a CSV legible en Excel.")
    parser.add_argument(
        "--input",
        type=str,
        default=str(PANEL_PARQUET),
        help="Archivo .parquet de entrada",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="CSV de salida (default: reports/<nombre>.csv)",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Limitar filas (útil para muestras rápidas)",
    )
    args = parser.parse_args()

    ensure_dirs()
    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"No existe: {input_path}")

    df = pd.read_parquet(input_path)
    if args.max_rows:
        df = df.head(args.max_rows)

    output_path = Path(args.output) if args.output else REPORTS_DIR / f"{input_path.stem}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig", sep=";")

    print(
        json.dumps(
            {
                "ok": True,
                "input": str(input_path),
                "output": str(output_path),
                "filas": len(df),
                "columnas": df.shape[1],
                "abrir_con": "Excel o bloc de notas (separador ;)",
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
