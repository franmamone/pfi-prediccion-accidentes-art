from __future__ import annotations

import argparse
import json

import pandas as pd

from _bootstrap import SRC  # noqa: F401

from pfi_prediccion.columns import normalize_accidents_df, normalize_universe_df
from pfi_prediccion.config import (
    ACCIDENTS_PARQUET,
    PANEL_PARQUET,
    UNIVERSE_PARQUET,
    ensure_dirs,
    load_env,
)
from pfi_prediccion.eda import run_eda
from pfi_prediccion.evaluate import evaluate_model
from pfi_prediccion.export import export_accidents_parquet
from pfi_prediccion.panel import build_establishment_month_panel, panel_summary
from pfi_prediccion.train import train_baseline


def _load_universe() -> pd.DataFrame | None:
    if not UNIVERSE_PARQUET.exists():
        return None
    return normalize_universe_df(pd.read_parquet(UNIVERSE_PARQUET))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pipeline completo: export → EDA → panel → modelo XGBoost → evaluación."
    )
    parser.add_argument(
        "--skip-export",
        action="store_true",
        help="Usar parquet existente en data/raw/",
    )
    parser.add_argument(
        "--skip-panel",
        action="store_true",
        help="Usar panel parquet existente (solo entrena y evalúa)",
    )
    args = parser.parse_args()

    load_env()
    ensure_dirs()

    if args.skip_export:
        accidents = normalize_accidents_df(pd.read_parquet(ACCIDENTS_PARQUET))
        export_path = ACCIDENTS_PARQUET
    else:
        export_path = export_accidents_parquet()
        accidents = normalize_accidents_df(pd.read_parquet(export_path))

    universe = _load_universe()
    if universe is not None:
        print(f"Universo cargado: {universe['id_establecimiento'].nunique():,} establecimientos", flush=True)

    eda_summary = run_eda(accidents)

    if args.skip_panel and PANEL_PARQUET.exists():
        print(f"[pipeline] Cargando panel existente: {PANEL_PARQUET}", flush=True)
        panel = pd.read_parquet(PANEL_PARQUET)
    else:
        panel = build_establishment_month_panel(accidents, universe=universe)
        print("[pipeline] Guardando panel...", flush=True)
        panel.to_parquet(PANEL_PARQUET, index=False)

    panel_stats = panel_summary(panel)
    print("[pipeline] Entrenando modelo (puede tardar varios minutos)...", flush=True)
    train_metrics = train_baseline(panel)
    print("[pipeline] Evaluando...", flush=True)
    eval_metrics = evaluate_model(panel)

    print(
        json.dumps(
            {
                "ok": True,
                "export": str(export_path),
                "universe": universe is not None,
                "panel": str(PANEL_PARQUET),
                "eda": eda_summary,
                "panel_summary": panel_stats,
                "model": train_metrics,
                "evaluation": eval_metrics,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
