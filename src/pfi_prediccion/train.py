from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    fbeta_score,
    precision_recall_curve,
    recall_score,
)
from sklearn.model_selection import ParameterSampler, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier

from .config import (
    CALIBRATION_YEAR,
    HOLDOUT_YEAR,
    HORIZON_1M,
    MODEL_PIPELINE_PATH,
    MODEL_PIPELINE_COLD_PATH,
    MODEL_PIPELINE_WARM_PATH,
    MODEL_THRESHOLD_PATH,
    MODEL_XGBOOST_PATH,
    REPORTS_MODEL_DIR,
    TRAIN_YEARS,
    ensure_dirs,
    model_pipeline_path,
    target_column_for_horizon,
)
from .inference import predict_blended_batched, predict_proba_batched

NUMERIC_FEATURES = [
    "anio",
    "mes",
    "mes_sin",
    "mes_cos",
    "accidentes_3m",
    "accidentes_6m",
    "accidentes_12m",
    "accidentes_total_previos",
    "meses_desde_ultimo_accidente",
    "tendencia_accidentes_3m",
    "cantidad_capitas",
    "nivel_seguridad_empleador",
    "nivel_seguridad_establecimiento",
    "id_tipo_establecimiento",
    "flag_establecimiento_principal",
    "antiguedad_establecimiento_meses",
    "id_provincia_establecimiento",
    "flag_coordenadas_validas",
    "latitud_establecimiento",
    "longitud_establecimiento",
    "flag_riesgo_higienico",
    "dotacion_establecimiento",
    "log_dotacion",
    "frecuencia_visita_ciiu_meses",
    "visitas_planificadas_12m",
    "visitas_realizadas_12m",
    "ratio_visitas_realizadas",
    "brecha_visitas",
    "flag_alto_riesgo_historico",
    "flag_sin_historial_accidente",
    "accidentes_empleador_3m",
    "accidentes_empleador_6m",
    "accidentes_empleador_12m",
    "tasa_accidentes_12m_exposicion",
    "accidentes_por_capita_12m",
    "visitas_planificadas_mes",
    "visitas_realizadas_mes",
    "meses_desde_ultima_visita",
    "dotacion_nomina_mes",
    "edad_promedio",
    "pct_mayores_50",
    "pct_mujeres",
    "antiguedad_promedio_meses",
    "pct_antiguedad_menor_6m",
    "tareas_distintas",
    "pct_en_tarea_principal",
    "ratio_dotacion_nomina_capitas",
]

CATEGORICAL_FEATURES = [
    "actividad_ciiu_empleador",
    "actividad_ciiu_establecimiento",
    "actividad_ciiu_rev4_principal",
    "ciiu_seccion",
]

PARAM_DISTRIBUTION = {
    "model__n_estimators": [200, 300, 400, 500],
    "model__max_depth": [4, 5, 6, 7],
    "model__learning_rate": [0.03, 0.05, 0.08, 0.1],
    "model__subsample": [0.7, 0.8, 0.9, 1.0],
    "model__colsample_bytree": [0.7, 0.8, 0.9, 1.0],
    "model__min_child_weight": [1, 3, 5, 7],
    "model__reg_lambda": [0.5, 1.0, 2.0, 5.0],
    "model__gamma": [0.0, 0.1, 0.5, 1.0],
}

TUNE_MAX_ROWS = 250_000
THRESHOLD_MAX_ROWS = 100_000
MIN_DUAL_ROWS = 5_000
MIN_DUAL_POSITIVES = 30

# Ablaciones opcionales de grupos de features.
ABLATION_GROUPS = {
    "full": None,
    "sin_nomina": {
        "dotacion_nomina_mes",
        "edad_promedio",
        "pct_mayores_50",
        "pct_mujeres",
        "antiguedad_promedio_meses",
        "pct_antiguedad_menor_6m",
        "tareas_distintas",
        "pct_en_tarea_principal",
        "ratio_dotacion_nomina_capitas",
    },
    "sin_prevencion": {
        "visitas_planificadas_12m",
        "visitas_realizadas_12m",
        "ratio_visitas_realizadas",
        "brecha_visitas",
        "visitas_planificadas_mes",
        "visitas_realizadas_mes",
        "meses_desde_ultima_visita",
        "frecuencia_visita_ciiu_meses",
    },
    "solo_historial": None,  # se resuelve por inclusión
}

HISTORIAL_FEATURES = {
    "accidentes_3m",
    "accidentes_6m",
    "accidentes_12m",
    "accidentes_total_previos",
    "meses_desde_ultimo_accidente",
    "tendencia_accidentes_3m",
    "flag_alto_riesgo_historico",
    "flag_sin_historial_accidente",
    "accidentes_empleador_3m",
    "accidentes_empleador_6m",
    "accidentes_empleador_12m",
    "tasa_accidentes_12m_exposicion",
    "accidentes_por_capita_12m",
    "anio",
    "mes",
    "mes_sin",
    "mes_cos",
}


def _tune_sample(X: pd.DataFrame, y: pd.Series, max_rows: int = TUNE_MAX_ROWS) -> tuple[pd.DataFrame, pd.Series]:
    if len(X) <= max_rows:
        return X, y
    X_sub, _, y_sub, _ = train_test_split(
        X, y, train_size=max_rows / len(X), stratify=y, random_state=42
    )
    return X_sub, y_sub


def _feature_columns(
    panel: pd.DataFrame,
    drop_features: set[str] | None = None,
    only_features: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    drop_features = drop_features or set()
    num: list[str] = []
    for c in NUMERIC_FEATURES:
        if c not in panel.columns or c in drop_features:
            continue
        if only_features is not None and c not in only_features:
            continue
        s = panel[c]
        if int(s.notna().sum()) == 0:
            continue
        if s.nunique(dropna=True) <= 1:
            continue
        num.append(c)
    cat: list[str] = []
    for c in CATEGORICAL_FEATURES:
        if c not in panel.columns or c in drop_features:
            continue
        if only_features is not None and c not in only_features:
            continue
        s = panel[c]
        if int(s.notna().sum()) == 0:
            continue
        if s.nunique(dropna=True) <= 1:
            continue
        cat.append(c)
    return num, cat


def _filter_evaluable(panel: pd.DataFrame, target_col: str) -> pd.DataFrame:
    if target_col not in panel.columns:
        raise ValueError(f"Falta columna target {target_col}")
    out = panel[panel[target_col].notna()].copy()
    out[target_col] = out[target_col].astype(int)
    return out


def _temporal_splits(
    panel: pd.DataFrame,
    target_col: str,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Train 2022-2023, calibración 2024, holdout 2025 (si existe)."""
    data = _filter_evaluable(panel, target_col)
    train = data[data["anio"].isin(TRAIN_YEARS)].copy()
    calib = data[data["anio"] == CALIBRATION_YEAR].copy()
    holdout = data[data["anio"] == HOLDOUT_YEAR].copy()

    if train.empty:
        raise ValueError("Split temporal: train vacío.")
    if calib.empty and holdout.empty:
        raise ValueError("Split temporal: no hay calibración ni holdout.")

    # Si aún no hay 2025 exportado, usar 2024 como test (legacy) y 2023 como calib.
    if holdout.empty:
        print(
            "[train] Holdout 2025 no disponible: usando 2024 como test y 2023 como calibración.",
            flush=True,
        )
        train = data[data["anio"].isin((2022,))].copy()
        if train.empty:
            train = data[data["anio"].isin(TRAIN_YEARS)].copy()
        calib = data[data["anio"] == 2023].copy()
        holdout = data[data["anio"] == CALIBRATION_YEAR].copy()

    if train.empty or calib.empty or holdout.empty:
        raise ValueError(
            f"Split temporal incompleto: train={len(train)}, calib={len(calib)}, holdout={len(holdout)}"
        )
    return train, calib, holdout


def _build_pipeline(feature_cols_num: list[str], feature_cols_cat: list[str]) -> Pipeline:
    numeric_pipe = Pipeline(steps=[("imputer", SimpleImputer(strategy="median"))])
    categorical_pipe = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", max_categories=50)),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numeric_pipe, feature_cols_num),
            ("cat", categorical_pipe, feature_cols_cat),
        ]
    )

    model = XGBClassifier(
        objective="binary:logistic",
        eval_metric="aucpr",
        random_state=42,
        n_jobs=-1,
        tree_method="hist",
    )

    return Pipeline(steps=[("preprocess", preprocessor), ("model", model)])


def _scale_pos_weight(y: pd.Series) -> float:
    pos = int(y.sum())
    neg = int(len(y) - pos)
    return neg / pos if pos > 0 else 1.0


def _optimal_threshold(y_true: np.ndarray, y_prob: np.ndarray, beta: float = 2.0) -> float:
    """Umbral que maximiza F-beta (beta>1 favorece recall)."""
    precision, recall, thresholds = precision_recall_curve(y_true, y_prob)
    if len(thresholds) == 0:
        return 0.5

    best_t, best_score = 0.5, -1.0
    for t in thresholds:
        pred = (y_prob >= t).astype(int)
        score = fbeta_score(y_true, pred, beta=beta, zero_division=0)
        if score > best_score:
            best_score = score
            best_t = float(t)
    return best_t


def _expanding_temporal_folds(train_df: pd.DataFrame) -> list[tuple[np.ndarray, np.ndarray]]:
    """Folds temporales expansivos por año-mes dentro del train."""
    periods = sorted(train_df["periodo"].unique())
    if len(periods) < 6:
        # Fallback: split 70/30 temporal
        cut = max(1, int(len(periods) * 0.7))
        train_p = set(periods[:cut])
        val_p = set(periods[cut:])
        tr_idx = train_df.index[train_df["periodo"].isin(train_p)].to_numpy()
        va_idx = train_df.index[train_df["periodo"].isin(val_p)].to_numpy()
        return [(tr_idx, va_idx)] if len(va_idx) and len(tr_idx) else []

    folds: list[tuple[np.ndarray, np.ndarray]] = []
    # Validar últimos 3 bloques de ~3 meses
    block = max(2, len(periods) // 8)
    for i in range(3):
        val_end = len(periods) - i * block
        val_start = max(block, val_end - block)
        if val_start >= val_end:
            continue
        train_p = set(periods[:val_start])
        val_p = set(periods[val_start:val_end])
        if len(train_p) < 3 or not val_p:
            continue
        tr_idx = train_df.index[train_df["periodo"].isin(train_p)].to_numpy()
        va_idx = train_df.index[train_df["periodo"].isin(val_p)].to_numpy()
        if len(tr_idx) and len(va_idx):
            folds.append((tr_idx, va_idx))
    return folds or []


def _temporal_param_search(
    pipeline: Pipeline,
    train_df: pd.DataFrame,
    features: list[str],
    target_col: str,
    n_iter: int,
) -> dict:
    """Randomized search con folds temporales (no shuffle)."""
    folds = _expanding_temporal_folds(train_df)
    if not folds:
        raise ValueError("No se pudieron construir folds temporales.")

    X = train_df[features]
    y = train_df[target_col]
    X_tune, y_tune = _tune_sample(X, y)
    # Remap folds a índices posicionales del sample es complejo; evaluar en folds del train completo
    # pero con subconjunto de params y sample interno por fold.
    sampler = list(ParameterSampler(PARAM_DISTRIBUTION, n_iter=n_iter, random_state=42))
    best_score = -1.0
    best_params: dict = sampler[0]

    for i, params in enumerate(sampler, start=1):
        fold_scores: list[float] = []
        for tr_idx, va_idx in folds:
            X_tr = train_df.loc[tr_idx, features]
            y_tr = train_df.loc[tr_idx, target_col]
            X_va = train_df.loc[va_idx, features]
            y_va = train_df.loc[va_idx, target_col]
            if y_tr.sum() == 0 or y_va.sum() == 0:
                continue
            X_tr_s, y_tr_s = _tune_sample(X_tr, y_tr, max_rows=min(TUNE_MAX_ROWS, len(X_tr)))
            pipe = _build_pipeline(
                [c for c in features if c in NUMERIC_FEATURES],
                [c for c in features if c in CATEGORICAL_FEATURES],
            )
            # Rebuild with actual feature lists from parent pipeline
            num = [c for c in features if c in X_tr.columns and c in NUMERIC_FEATURES]
            cat = [c for c in features if c in X_tr.columns and c in CATEGORICAL_FEATURES]
            pipe = _build_pipeline(num, cat)
            pipe.set_params(**params)
            pipe.named_steps["model"].set_params(scale_pos_weight=_scale_pos_weight(y_tr_s))
            pipe.fit(X_tr_s[num + cat], y_tr_s)
            prob = predict_proba_batched(pipe, X_va[num + cat])
            fold_scores.append(float(average_precision_score(y_va, prob)))
        if not fold_scores:
            continue
        score = float(np.mean(fold_scores))
        if score > best_score:
            best_score = score
            best_params = params
        if i % 4 == 0 or i == len(sampler):
            print(
                f"[train] Temporal search {i}/{len(sampler)} best_pr_auc={best_score:.4f}",
                flush=True,
            )

    return {"best_params": best_params, "best_score": best_score, "n_folds": len(folds)}


def _fit_segment(
    train_df: pd.DataFrame,
    features: list[str],
    feature_cols_num: list[str],
    feature_cols_cat: list[str],
    target_col: str,
    label: str,
) -> tuple[Pipeline, dict]:
    X_train = train_df[features]
    y_train = train_df[target_col]
    scale_pos_weight = _scale_pos_weight(y_train)
    n_iter = 6 if len(X_train) > TUNE_MAX_ROWS else 10
    print(f"[train:{label}] Tuning temporal ({n_iter} configs)...", flush=True)

    search = _temporal_param_search(
        _build_pipeline(feature_cols_num, feature_cols_cat),
        train_df,
        features,
        target_col,
        n_iter=n_iter,
    )

    best = _build_pipeline(feature_cols_num, feature_cols_cat)
    best.set_params(**search["best_params"])
    best.named_steps["model"].set_params(scale_pos_weight=scale_pos_weight)

    # En paneles grandes (>250k) el fit completo puede agotar memoria/tiempo en Windows.
    # Se reentrena con muestra estratificada; los hiperparámetros ya vienen del search temporal.
    X_fit, y_fit = _tune_sample(X_train, y_train, max_rows=TUNE_MAX_ROWS)
    if len(X_fit) < len(X_train):
        print(
            f"[train:{label}] Ajuste final con muestra estratificada "
            f"{len(X_fit):,}/{len(X_train):,} filas...",
            flush=True,
        )
    else:
        print(f"[train:{label}] Ajuste final con {len(X_fit):,} filas...", flush=True)
    best.fit(X_fit, y_fit)
    return best, search


def train_baseline(
    panel: pd.DataFrame,
    reports_dir: Path | None = None,
    dual_model: bool = False,
    full_retrain: bool = False,
    horizon: str = HORIZON_1M,
    target_column: str | None = None,
    ablation: str = "full",
) -> dict:
    """Tuning temporal, umbral F2 y persistencia del pipeline por horizonte."""
    del full_retrain  # legacy no-op
    ensure_dirs()
    reports_dir = Path(reports_dir or REPORTS_MODEL_DIR)
    reports_dir.mkdir(parents=True, exist_ok=True)

    target_col = target_column or target_column_for_horizon(horizon)
    drop_features = ABLATION_GROUPS.get(ablation)
    only_features = HISTORIAL_FEATURES if ablation == "solo_historial" else None
    if ablation == "solo_historial":
        drop_features = None

    feature_cols_num, feature_cols_cat = _feature_columns(
        panel, drop_features=drop_features, only_features=only_features
    )
    features = feature_cols_num + feature_cols_cat

    train_df, calib_df, holdout_df = _temporal_splits(panel, target_col)
    X_train = train_df[features]
    y_train = train_df[target_col]
    X_calib = calib_df[features]
    y_calib = calib_df[target_col]
    X_holdout = holdout_df[features]
    y_holdout = holdout_df[target_col]

    use_dual = dual_model and "flag_sin_historial_accidente" in panel.columns
    cold_train = train_df[train_df["flag_sin_historial_accidente"] == 1]
    warm_train = train_df[train_df["flag_sin_historial_accidente"] == 0]

    if use_dual:
        cold_ok = (
            len(cold_train) >= MIN_DUAL_ROWS
            and int(cold_train[target_col].sum()) >= MIN_DUAL_POSITIVES
        )
        warm_ok = (
            len(warm_train) >= MIN_DUAL_ROWS
            and int(warm_train[target_col].sum()) >= MIN_DUAL_POSITIVES
        )
        use_dual = cold_ok and warm_ok
        if not use_dual:
            print("[train] Dual desactivado: segmento con pocos datos.", flush=True)

    search_meta: dict = {}
    if use_dual:
        pipeline_warm, search_warm = _fit_segment(
            warm_train, features, feature_cols_num, feature_cols_cat, target_col, "warm"
        )
        pipeline_cold, search_cold = _fit_segment(
            cold_train, features, feature_cols_num, feature_cols_cat, target_col, "cold"
        )
        artifact_core = {
            "dual_model": True,
            "pipeline_warm": pipeline_warm,
            "pipeline_cold": pipeline_cold,
            "pipeline": pipeline_warm,
        }
        search_meta = {"warm": search_warm, "cold": search_cold}
        X_cal_s, y_cal_s = _tune_sample(X_calib, y_calib, max_rows=THRESHOLD_MAX_ROWS)
        val_prob = predict_blended_batched({**artifact_core, "features": features}, X_cal_s)
    else:
        pipeline, search_meta = _fit_segment(
            train_df, features, feature_cols_num, feature_cols_cat, target_col, "all"
        )
        artifact_core = {"dual_model": False, "pipeline": pipeline}
        X_cal_s, y_cal_s = _tune_sample(X_calib, y_calib, max_rows=THRESHOLD_MAX_ROWS)
        val_prob = predict_proba_batched(pipeline, X_cal_s)

    threshold = _optimal_threshold(y_cal_s.to_numpy(), val_prob, beta=2.0)
    print(f"[train] Prediciendo holdout ({len(X_holdout):,} filas)...", flush=True)
    test_prob = predict_blended_batched({**artifact_core, "features": features}, X_holdout)
    y_pred = (test_prob >= threshold).astype(int)

    metrics = {
        "horizon": horizon,
        "target_column": target_col,
        "ablation": ablation,
        "train_rows": len(train_df),
        "calibration_rows": len(calib_df),
        "holdout_rows": len(holdout_df),
        "train_years": list(TRAIN_YEARS),
        "calibration_year": CALIBRATION_YEAR if (holdout_df["anio"] == HOLDOUT_YEAR).any() else 2023,
        "holdout_year": int(holdout_df["anio"].mode().iloc[0]),
        "train_positive_rate": float(y_train.mean()),
        "calibration_positive_rate": float(y_calib.mean()),
        "holdout_positive_rate": float(y_holdout.mean()),
        "recall": float(recall_score(y_holdout, y_pred, zero_division=0)),
        "pr_auc": float(average_precision_score(y_holdout, test_prob)),
        "threshold": threshold,
        "dual_model": use_dual,
        "temporal_search_best_score": (
            search_meta.get("best_score")
            if isinstance(search_meta, dict) and "best_score" in search_meta
            else None
        ),
        # Compat keys
        "val_rows": len(calib_df),
        "test_rows": len(holdout_df),
        "val_positive_rate": float(y_calib.mean()),
        "test_positive_rate": float(y_holdout.mean()),
    }
    if use_dual:
        metrics["warm_train_rows"] = len(warm_train)
        metrics["cold_train_rows"] = len(cold_train)

    suffix = f"_{horizon}" if ablation == "full" else f"_{horizon}_{ablation}"
    report = classification_report(y_holdout, y_pred, zero_division=0)
    (reports_dir / f"model_classification_report{suffix}.txt").write_text(report, encoding="utf-8")
    (reports_dir / f"model_metrics{suffix}.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    artifact = {
        **artifact_core,
        "threshold": threshold,
        "features": features,
        "feature_cols_num": feature_cols_num,
        "feature_cols_cat": feature_cols_cat,
        "metrics": metrics,
        "horizon": horizon,
        "target_column": target_col,
        "ablation": ablation,
        "panel_establecimientos": int(panel["id_establecimiento"].nunique()),
        "panel_filas": len(panel),
        "data_cutoff": {
            "train_years": list(TRAIN_YEARS),
            "calibration_year": CALIBRATION_YEAR,
            "holdout_year": HOLDOUT_YEAR,
        },
    }
    out_path = model_pipeline_path(horizon) if ablation == "full" else (
        MODEL_PIPELINE_PATH.parent / f"model_pipeline{suffix}.joblib"
    )
    primary_pipeline = artifact.get("pipeline_warm") or artifact["pipeline"]
    print(f"[train] Guardando modelo → {out_path.name}...", flush=True)
    joblib.dump(artifact, out_path)
    if ablation == "full" and horizon == HORIZON_1M:
        joblib.dump(artifact, MODEL_PIPELINE_PATH)
        if use_dual:
            joblib.dump(artifact["pipeline_cold"], MODEL_PIPELINE_COLD_PATH)
            joblib.dump(artifact["pipeline_warm"], MODEL_PIPELINE_WARM_PATH)
        MODEL_THRESHOLD_PATH.write_text(
            json.dumps({"threshold": threshold, "horizon": horizon}, indent=2),
            encoding="utf-8",
        )
        primary_pipeline.named_steps["model"].save_model(MODEL_XGBOOST_PATH)
        primary_pipeline.named_steps["model"].save_model(
            MODEL_XGBOOST_PATH.parent / "xgboost_baseline.json"
        )

    return {
        **metrics,
        "model_path": str(out_path),
        "reports_dir": str(reports_dir),
    }


def train_ablation_suite(
    panel: pd.DataFrame,
    horizon: str = HORIZON_1M,
    reports_dir: Path | None = None,
) -> dict:
    """Compara modelo completo vs sin nómina / sin prevención / solo historial."""
    results = {}
    for name in ("full", "sin_nomina", "sin_prevencion", "solo_historial"):
        print(f"[train] Ablación: {name}", flush=True)
        results[name] = train_baseline(
            panel,
            reports_dir=reports_dir,
            horizon=horizon,
            ablation=name,
        )
    out = Path(reports_dir or REPORTS_MODEL_DIR) / f"ablation_metrics_{horizon}.json"
    summary = {
        k: {
            "pr_auc": v.get("pr_auc"),
            "recall": v.get("recall"),
            "holdout_rows": v.get("holdout_rows"),
            "model_path": v.get("model_path"),
        }
        for k, v in results.items()
    }
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary
