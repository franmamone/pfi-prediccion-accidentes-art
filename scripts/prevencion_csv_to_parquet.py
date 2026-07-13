"""Convierte export CSV de visitas/prevención por establecimiento×mes a parquet."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from _bootstrap import SRC  # noqa: F401

from pfi_prediccion.columns import normalize_prevencion_df, read_ssms_csv
from pfi_prediccion.config import PREVENCION_PARQUET, RAW_DIR, ensure_dirs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convierte prevencion_establecimiento_mes.csv (SSMS) a parquet."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(RAW_DIR / "prevencion_establecimiento_mes.csv"),
        help="CSV exportado desde ml.vw_prevencion_establecimiento_mes_ml",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(PREVENCION_PARQUET),
        help="Parquet de salida",
    )
    args = parser.parse_args()

    ensure_dirs()
    path = Path(args.input)
    if not path.exists():
        raise FileNotFoundError(
            f"No existe {path}. Exportá SELECT * FROM ml.vw_prevencion_establecimiento_mes_ml en SSMS."
        )

    df = normalize_prevencion_df(read_ssms_csv(path, min_columns=4))
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
