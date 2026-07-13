from __future__ import annotations

import argparse
import json

import pandas as pd

from _bootstrap import SRC  # noqa: F401

from pfi_prediccion.columns import (
    normalize_accidents_df,
    normalize_nomina_df,
    normalize_prevencion_df,
    normalize_universe_df,
)
from pfi_prediccion.config import (
    ACCIDENTS_PARQUET,
    NOMINA_PARQUET,
    PANEL_PARQUET,
    PREVENCION_PARQUET,
    UNIVERSE_PARQUET,
    ensure_dirs,
)
from pfi_prediccion.panel import build_establishment_month_panel, panel_summary


def _load_universe() -> pd.DataFrame | None:
    if not UNIVERSE_PARQUET.exists():
        return None
    return normalize_universe_df(pd.read_parquet(UNIVERSE_PARQUET))


def _load_prevencion() -> pd.DataFrame | None:
    if not PREVENCION_PARQUET.exists():
        return None
    return normalize_prevencion_df(pd.read_parquet(PREVENCION_PARQUET))


def _load_nomina() -> pd.DataFrame | None:
    if not NOMINA_PARQUET.exists():
        return None
    return normalize_nomina_df(pd.read_parquet(NOMINA_PARQUET))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Construye panel establecimiento×mes con target T+1."
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(ACCIDENTS_PARQUET),
        help="Parquet de accidentes",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(PANEL_PARQUET),
        help="Parquet de panel",
    )
    parser.add_argument(
        "--no-universe",
        action="store_true",
        help="Ignorar establecimientos_universo.parquet aunque exista",
    )
    parser.add_argument(
        "--no-prevencion",
        action="store_true",
        help="Ignorar prevencion_establecimiento_mes.parquet aunque exista",
    )
    parser.add_argument(
        "--no-nomina",
        action="store_true",
        help="Ignorar nomina_establecimiento_mes.parquet aunque exista",
    )
    args = parser.parse_args()

    ensure_dirs()
    accidents = normalize_accidents_df(pd.read_parquet(args.input))
    universe = None if args.no_universe else _load_universe()
    prevencion = None if args.no_prevencion else _load_prevencion()
    nomina = None if args.no_nomina else _load_nomina()
    panel = build_establishment_month_panel(
        accidents,
        universe=universe,
        prevencion=prevencion,
        nomina=nomina,
    )
    panel.to_parquet(args.output, index=False)

    summary = panel_summary(panel)
    print(
        json.dumps(
            {
                "ok": True,
                "output": args.output,
                "universe": universe is not None,
                "prevencion": prevencion is not None,
                "nomina": nomina is not None,
                "summary": summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
