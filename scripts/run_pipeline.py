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
    HORIZON_1M,
    HORIZON_3M,
    NOMINA_PARQUET,
    PANEL_PARQUET,
    PREVENCION_PARQUET,
    TARGET_COLUMN_3M,
    UNIVERSE_PARQUET,
    ensure_dirs,
    load_env,
    target_column_for_horizon,
)
from pfi_prediccion.eda import run_eda
from pfi_prediccion.evaluate import evaluate_model
from pfi_prediccion.explain import run_shap_explain
from pfi_prediccion.export import export_accidents_parquet
from pfi_prediccion.dataset_reports import run_dataset_reports
from pfi_prediccion.panel import build_establishment_month_panel, panel_summary
from pfi_prediccion.ranking_policy import export_ranking_contract
from pfi_prediccion.train import train_ablation_suite, train_baseline


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


def _horizons(arg: str) -> list[str]:
    if arg == "both":
        return [HORIZON_1M, HORIZON_3M]
    if arg in {HORIZON_1M, HORIZON_3M}:
        return [arg]
    raise ValueError("--horizon debe ser 1m, 3m o both")


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
        "--horizon",
        type=str,
        default="both",
        choices=["1m", "3m", "both"],
        help="Horizonte de predicción: 1m, 3m o both",
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
        "--ablations",
        action="store_true",
        help="Correr ablaciones (sin nómina / sin prevención / solo historial)",
    )
    parser.add_argument(
        "--skip-shap",
        action="store_true",
        help="Omitir explicabilidad SHAP al final",
    )
    parser.add_argument(
        "--skip-reports",
        action="store_true",
        help="Omitir gráficos de reporte extendidos al final",
    )
    parser.add_argument(
        "--skip-ranking",
        action="store_true",
        help="Omitir export del ranking maestro / contrato API",
    )
    args = parser.parse_args()

    load_env()
    ensure_dirs()
    horizons = _horizons(args.horizon)

    if args.skip_export:
        accidents = normalize_accidents_df(pd.read_parquet(ACCIDENTS_PARQUET))
        export_path = ACCIDENTS_PARQUET
    else:
        export_path = export_accidents_parquet()
        accidents = normalize_accidents_df(pd.read_parquet(export_path))

    universe = _load_universe()
    if universe is not None:
        print(
            f"Universo cargado: {universe['id_establecimiento'].nunique():,} establecimientos",
            flush=True,
        )

    prevencion = _load_prevencion()
    if prevencion is not None:
        print(f"Prevención cargada: {len(prevencion):,} filas est×mes", flush=True)
    else:
        print("Prevención no encontrada (opcional).", flush=True)

    nomina = _load_nomina()
    if nomina is not None:
        print(f"Nómina cargada: {len(nomina):,} filas est×mes", flush=True)
    else:
        print("Nómina no encontrada (opcional).", flush=True)

    eda_summary = run_eda(accidents)

    need_rebuild = True
    if args.skip_panel and PANEL_PARQUET.exists():
        panel = pd.read_parquet(PANEL_PARQUET)
        if TARGET_COLUMN_3M in panel.columns:
            need_rebuild = False
            print(f"[pipeline] Cargando panel existente: {PANEL_PARQUET}", flush=True)
        else:
            print(
                "[pipeline] Panel existente sin target_3m; se reconstruye.",
                flush=True,
            )

    if need_rebuild:
        panel = build_establishment_month_panel(
            accidents,
            universe=universe,
            prevencion=prevencion,
            nomina=nomina,
        )
        print("[pipeline] Guardando panel...", flush=True)
        panel.to_parquet(PANEL_PARQUET, index=False)

    panel_stats = panel_summary(panel)

    model_by_horizon: dict = {}
    eval_by_horizon: dict = {}
    ranking_by_horizon: dict = {}
    ablation_by_horizon: dict = {}

    for horizon in horizons:
        target = target_column_for_horizon(horizon)
        print(f"[pipeline] Entrenando horizonte {horizon} (target={target})...", flush=True)
        model_by_horizon[horizon] = train_baseline(
            panel,
            dual_model=args.dual,
            full_retrain=args.full_retrain,
            horizon=horizon,
            target_column=target,
        )
        print(f"[pipeline] Evaluando horizonte {horizon}...", flush=True)
        eval_by_horizon[horizon] = evaluate_model(
            panel,
            horizon=horizon,
            target_column=target,
        )
        if args.ablations:
            print(f"[pipeline] Ablaciones {horizon}...", flush=True)
            ablation_by_horizon[horizon] = train_ablation_suite(panel, horizon=horizon)

        if not args.skip_ranking:
            print(f"[pipeline] Ranking maestro {horizon}...", flush=True)
            ranking_by_horizon[horizon] = export_ranking_contract(panel, horizon=horizon)

    shap_metrics = None
    if not args.skip_shap:
        print("[pipeline] SHAP (muestra, horizonte 1m)...", flush=True)
        shap_metrics = run_shap_explain(panel)

    reports_metrics = None
    if not args.skip_reports:
        print("[pipeline] Reportes gráficos del dataset...", flush=True)
        reports_metrics = run_dataset_reports(accidents, panel=panel)

    print(
        json.dumps(
            {
                "ok": True,
                "export": str(export_path),
                "universe": universe is not None,
                "prevencion": prevencion is not None,
                "nomina": nomina is not None,
                "panel": str(PANEL_PARQUET),
                "horizons": horizons,
                "eda": eda_summary,
                "panel_summary": panel_stats,
                "model": model_by_horizon,
                "evaluation": eval_by_horizon,
                "ablations": ablation_by_horizon or None,
                "ranking": ranking_by_horizon or None,
                "shap": shap_metrics,
                "reports": reports_metrics,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
