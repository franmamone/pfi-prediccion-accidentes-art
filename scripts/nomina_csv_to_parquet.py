"""Convierte export CSV de nómina agregada por establecimiento×mes a parquet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import SRC  # noqa: F401

from pfi_prediccion.columns import normalize_nomina_df, read_ssms_csv
from pfi_prediccion.config import NOMINA_PARQUET, RAW_DIR, ensure_dirs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convierte nomina_establecimiento_mes.csv (SSMS) a parquet."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(RAW_DIR / "nomina_establecimiento_mes.csv"),
        help="CSV exportado desde ml.vw_nomina_establecimiento_mes_ml",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(NOMINA_PARQUET),
        help="Parquet de salida",
    )
    args = parser.parse_args()

    ensure_dirs()
    path = Path(args.input)
    if not path.exists():
        raise FileNotFoundError(
            f"No existe {path}. Exportá SELECT * FROM ml.vw_nomina_establecimiento_mes_ml en SSMS."
        )

    df = normalize_nomina_df(read_ssms_csv(path, min_columns=8))
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
                "dotacion_promedio": float(df["dotacion_nomina_mes"].mean()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
