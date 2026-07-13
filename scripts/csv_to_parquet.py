"""Convierte export CSV/TSV de SSMS a parquet para el pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from _bootstrap import SRC  # noqa: F401

from pfi_prediccion.columns import normalize_accidents_df, read_ssms_csv
from pfi_prediccion.config import ACCIDENTS_PARQUET, RAW_DIR, ensure_dirs


def read_ssms_export(path: Path) -> pd.DataFrame:
    return normalize_accidents_df(read_ssms_csv(path, min_columns=50))


def resolve_inputs(input_arg: str | None, inputs: list[str] | None) -> list[Path]:
    paths: list[Path] = []
    if inputs:
        paths.extend(Path(p) for p in inputs)
    elif input_arg:
        candidate = Path(input_arg)
        if candidate.is_dir():
            paths.extend(sorted(candidate.glob("accidentes_*.csv")))
            paths.extend(sorted(candidate.glob("accidentes_*.tsv")))
            if not paths:
                paths.extend(sorted(candidate.glob("*.csv")))
        else:
            paths.append(candidate)
    else:
        default_dir = RAW_DIR
        paths.extend(sorted(default_dir.glob("accidentes_20*.csv")))
        if not paths and (default_dir / "accidentes_ml.csv").exists():
            paths.append(default_dir / "accidentes_ml.csv")

    existing = [p for p in paths if p.exists()]
    if not existing:
        raise FileNotFoundError(
            "No se encontraron CSV. Exportá desde SSMS a data/raw/ "
            "(accidentes_2022.csv, accidentes_2023.csv, accidentes_2024.csv)."
        )
    return existing


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convierte CSV/TSV exportado desde SSMS a accidentes_ml.parquet."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=None,
        help="Archivo CSV o carpeta data/raw con exports por año",
    )
    parser.add_argument(
        "--inputs",
        nargs="+",
        default=None,
        help="Lista explícita de archivos a unir",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(ACCIDENTS_PARQUET),
        help="Parquet de salida",
    )
    args = parser.parse_args()

    ensure_dirs()
    input_paths = resolve_inputs(args.input, args.inputs)

    frames = [read_ssms_export(path) for path in input_paths]
    df = pd.concat(frames, ignore_index=True)

    if "fecha_hora_accidente" in df.columns:
        df = df.sort_values("fecha_hora_accidente").drop_duplicates()

    output_path = Path(args.output)
    df.to_parquet(output_path, index=False)

    print(
        json.dumps(
            {
                "ok": True,
                "inputs": [str(p) for p in input_paths],
                "output": str(output_path),
                "filas": len(df),
                "columnas": df.shape[1],
                "columnas_ok": "fecha_hora_accidente" in df.columns,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
