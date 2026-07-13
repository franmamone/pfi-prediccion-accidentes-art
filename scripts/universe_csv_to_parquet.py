"""Convierte export CSV del universo de establecimientos a parquet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import SRC  # noqa: F401

from pfi_prediccion.columns import normalize_universe_df, read_ssms_csv
from pfi_prediccion.config import RAW_DIR, UNIVERSE_PARQUET, ensure_dirs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convierte establecimientos_universo.csv (SSMS) a parquet."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(RAW_DIR / "establecimientos_universo.csv"),
        help="CSV exportado desde ml.vw_establecimientos_universo_ml",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(UNIVERSE_PARQUET),
        help="Parquet de salida",
    )
    args = parser.parse_args()

    ensure_dirs()
    path = Path(args.input)
    if not path.exists():
        raise FileNotFoundError(
            f"No existe {path}. Exportá SELECT * FROM ml.vw_establecimientos_universo_ml en SSMS."
        )

    df = normalize_universe_df(read_ssms_csv(path, min_columns=10))
    output_path = Path(args.output)
    df.to_parquet(output_path, index=False)

    print(
        json.dumps(
            {
                "ok": True,
                "input": str(path),
                "output": str(output_path),
                "establecimientos": int(df["id_establecimiento"].nunique()),
                "filas": len(df),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
