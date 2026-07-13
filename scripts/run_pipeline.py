from __future__ import annotations

import argparse
import json

import pandas as pd

from _bootstrap import SRC  # noqa: F401

from pfi_prediccion.columns import normalize_accidents_df, normalize_prevencion_df, normalize_universe_df
from pfi_prediccion.config import (
    ACCIDENTS_PARQUET,
    PANEL_PARQUET,
    PREVENCION_PARQUET,
    UNIVERSE_PARQUET,
    ensure_dirs,
    load_env,
)
from pfi_prediccion.eda import run_eda
from pfi_prediccion.evaluate import evaluate_model
from pfi_prediccion.explain import run_shap_explain
from pfi_prediccion.export import export_accidents_parquet
from pfi_prediccion.panel import build_establishment_month_panel, panel_summary
from pfi_prediccion.train import train_baseline


def _load_universe() -> pd.DataFrame | None:
    if not UNIVERSE_PARQUET.exists():
        return None
    return normalize_universe_df(pd.read_parquet(UNIVERSE_PARQUET))


def _load_prevencion() -> pd.DataFrame | None:
    if not PREVENCION_PARQUET.exists():
        return None
    return normalize_prevencion_df(pd.read_parquet(PREVENCION_PARQUET))


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
    parser.add_argument(
        "--dual",
        action="store_true",
        help="Usar modelo dual cold/warm (experimental; por defecto modelo único)",
    )
    parser.add_argument(
        "--full-retrain",
        action="store_true",
        help="Alias legacy; el reentreno full ya es el comportamiento por defecto",
    )
    parser.add_argument(
        "--skip-shap",
        action="store_true",
        help="Omitir explicabilidad SHAP al final",
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

    prevencion = _load_prevencion()
    if prevencion is not None:
        print(f"Prevención cargada: {len(prevencion):,} filas est×mes", flush=True)
    else:
        print("Prevención no encontrada (opcional). Ver docs/MEJORAS_ESTADO.md", flush=True)

    eda_summary = run_eda(accidents)

    if args.skip_panel and PANEL_PARQUET.exists():
        print(f"[pipeline] Cargando panel existente: {PANEL_PARQUET}", flush=True)
        panel = pd.read_parquet(PANEL_PARQUET)
    else:
        panel = build_establishment_month_panel(accidents, universe=universe, prevencion=prevencion)
        print("[pipeline] Guardando panel...", flush=True)
        panel.to_parquet(PANEL_PARQUET, index=False)

    panel_stats = panel_summary(panel)
    print("[pipeline] Entrenando modelo (puede tardar varios minutos)...", flush=True)
    train_metrics = train_baseline(
        panel,
        dual_model=args.dual,
        full_retrain=args.full_retrain,
    )
    print("[pipeline] Evaluando...", flush=True)
    eval_metrics = evaluate_model(panel)

    shap_metrics = None
    if not args.skip_shap:
        print("[pipeline] SHAP (muestra)...", flush=True)
        shap_metrics = run_shap_explain(panel)

    print(
        json.dumps(
            {
                "ok": True,
                "export": str(export_path),
                "universe": universe is not None,
                "prevencion": prevencion is not None,
                "panel": str(PANEL_PARQUET),
                "eda": eda_summary,
                "panel_summary": panel_stats,
                "model": train_metrics,
                "evaluation": eval_metrics,
                "shap": shap_metrics,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
