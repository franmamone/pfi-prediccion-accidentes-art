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
from sklearn.model_selection import RandomizedSearchCV, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBClassifier

from .inference import predict_blended_batched, predict_proba_batched
from .config import (
    MODEL_PIPELINE_COLD_PATH,
    MODEL_PIPELINE_PATH,
    MODEL_PIPELINE_WARM_PATH,
    MODEL_THRESHOLD_PATH,
    MODEL_XGBOOST_PATH,
    REPORTS_DIR,
    TARGET_COLUMN,
    TEST_YEAR,
    TRAIN_YEARS,
    VAL_YEAR,
    ensure_dirs,
)

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


def _tune_sample(X: pd.DataFrame, y: pd.Series, max_rows: int = TUNE_MAX_ROWS) -> tuple[pd.DataFrame, pd.Series]:
    if len(X) <= max_rows:
        return X, y
    X_sub, _, y_sub, _ = train_test_split(
        X, y, train_size=max_rows / len(X), stratify=y, random_state=42
    )
    return X_sub, y_sub


def _feature_columns(panel: pd.DataFrame) -> tuple[list[str], list[str]]:
    num: list[str] = []
    for c in NUMERIC_FEATURES:
        if c not in panel.columns:
            continue
        s = panel[c]
        if int(s.notna().sum()) == 0:
            continue
        if s.nunique(dropna=True) <= 1:
            continue
        num.append(c)
    cat: list[str] = []
    for c in CATEGORICAL_FEATURES:
        if c not in panel.columns:
            continue
        s = panel[c]
        if int(s.notna().sum()) == 0:
            continue
        if s.nunique(dropna=True) <= 1:
            continue
        cat.append(c)
    return num, cat


def _temporal_splits(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    train = panel[panel["anio"].isin(TRAIN_YEARS)].copy()
    val = panel[panel["anio"] == VAL_YEAR].copy()
    test = panel[panel["anio"] == TEST_YEAR].copy()
    if train.empty or val.empty or test.empty:
        raise ValueError(
            f"Split temporal incompleto: train={len(train)}, val={len(val)}, test={len(test)}"
        )
    return train, val, test


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


def _fit_segment(
    train_df: pd.DataFrame,
    features: list[str],
    feature_cols_num: list[str],
    feature_cols_cat: list[str],
    label: str,
    full_retrain: bool,
) -> Pipeline:
    X_train = train_df[features]
    y_train = train_df[TARGET_COLUMN]
    scale_pos_weight = _scale_pos_weight(y_train)
    pipeline = _build_pipeline(feature_cols_num, feature_cols_cat)
    pipeline.named_steps["model"].set_params(scale_pos_weight=scale_pos_weight)

    X_tune, y_tune = _tune_sample(X_train, y_train)
    n_iter = 12 if len(X_train) > TUNE_MAX_ROWS else 20
    print(f"[train:{label}] Tuning {len(X_tune):,}/{len(X_train):,} filas ({n_iter} iter)...", flush=True)

    search = RandomizedSearchCV(
        pipeline,
        param_distributions=PARAM_DISTRIBUTION,
        n_iter=n_iter,
        scoring="average_precision",
        cv=3,
        random_state=42,
        n_jobs=-1,
        verbose=0,
    )
    search.fit(X_tune, y_tune)

    best = _build_pipeline(feature_cols_num, feature_cols_cat)
    best.set_params(**search.best_params_)
    best.named_steps["model"].set_params(scale_pos_weight=scale_pos_weight)
    if len(X_train) > len(X_tune):
        print(
            f"[train:{label}] Reentrenando con {len(X_train):,} filas "
            f"(hiperparámetros de muestra {len(X_tune):,})...",
            flush=True,
        )
    else:
        print(f"[train:{label}] Ajuste final con {len(X_train):,} filas...", flush=True)
    best.fit(X_train, y_train)
    return best


def predict_blended(artifact: dict, X: pd.DataFrame) -> np.ndarray:
    """Score usando modelo dual (frío/cálido) o pipeline único."""
    return predict_blended_batched(artifact, X, batch_size=len(X) + 1)


def train_baseline(
    panel: pd.DataFrame,
    reports_dir: Path | None = None,
    dual_model: bool = False,
    full_retrain: bool = False,
) -> dict:
    """Tuning de hiperparámetros, umbral F2 y persistencia del pipeline."""
    ensure_dirs()
    reports_dir = Path(reports_dir or REPORTS_DIR)
    reports_dir.mkdir(parents=True, exist_ok=True)

    feature_cols_num, feature_cols_cat = _feature_columns(panel)
    features = feature_cols_num + feature_cols_cat

    train_df, val_df, test_df = _temporal_splits(panel)
    X_train = train_df[features]
    y_train = train_df[TARGET_COLUMN]
    X_val = val_df[features]
    y_val = val_df[TARGET_COLUMN]
    X_test = test_df[features]
    y_test = test_df[TARGET_COLUMN]

    use_dual = dual_model and "flag_sin_historial_accidente" in panel.columns
    cold_train = train_df[train_df["flag_sin_historial_accidente"] == 1]
    warm_train = train_df[train_df["flag_sin_historial_accidente"] == 0]

    if use_dual:
        cold_ok = len(cold_train) >= MIN_DUAL_ROWS and int(cold_train[TARGET_COLUMN].sum()) >= MIN_DUAL_POSITIVES
        warm_ok = len(warm_train) >= MIN_DUAL_ROWS and int(warm_train[TARGET_COLUMN].sum()) >= MIN_DUAL_POSITIVES
        use_dual = cold_ok and warm_ok
        if not use_dual:
            print("[train] Dual desactivado: segmento con pocos datos.", flush=True)

    if use_dual:
        pipeline_warm = _fit_segment(warm_train, features, feature_cols_num, feature_cols_cat, "warm", full_retrain)
        pipeline_cold = _fit_segment(cold_train, features, feature_cols_num, feature_cols_cat, "cold", full_retrain)
        artifact_core = {
            "dual_model": True,
            "pipeline_warm": pipeline_warm,
            "pipeline_cold": pipeline_cold,
            "pipeline": pipeline_warm,
        }
        X_val_thresh, y_val_thresh = _tune_sample(X_val, y_val, max_rows=THRESHOLD_MAX_ROWS)
        val_prob = predict_blended_batched({**artifact_core, "features": features}, X_val_thresh)
    else:
        pipeline = _fit_segment(train_df, features, feature_cols_num, feature_cols_cat, "all", full_retrain)
        artifact_core = {"dual_model": False, "pipeline": pipeline}
        X_val_thresh, y_val_thresh = _tune_sample(X_val, y_val, max_rows=THRESHOLD_MAX_ROWS)
        val_prob = predict_proba_batched(pipeline, X_val_thresh)

    threshold = _optimal_threshold(y_val_thresh.to_numpy(), val_prob, beta=2.0)
    print(f"[train] Prediciendo test ({len(X_test):,} filas)...", flush=True)
    test_prob = predict_blended_batched({**artifact_core, "features": features}, X_test)
    y_pred = (test_prob >= threshold).astype(int)

    metrics = {
        "train_rows": len(train_df),
        "val_rows": len(val_df),
        "test_rows": len(test_df),
        "train_positive_rate": float(y_train.mean()),
        "val_positive_rate": float(y_val.mean()),
        "test_positive_rate": float(y_test.mean()),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "pr_auc": float(average_precision_score(y_test, test_prob)),
        "threshold": threshold,
        "dual_model": use_dual,
        "full_retrain": full_retrain,
    }
    if use_dual:
        metrics["warm_train_rows"] = len(warm_train)
        metrics["cold_train_rows"] = len(cold_train)

    report = classification_report(y_test, y_pred, zero_division=0)
    (reports_dir / "model_classification_report.txt").write_text(report, encoding="utf-8")
    (reports_dir / "model_metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    (reports_dir / "baseline_classification_report.txt").write_text(report, encoding="utf-8")
    (reports_dir / "baseline_metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    artifact = {
        **artifact_core,
        "threshold": threshold,
        "features": features,
        "feature_cols_num": feature_cols_num,
        "feature_cols_cat": feature_cols_cat,
        "metrics": metrics,
        "panel_establecimientos": int(panel["id_establecimiento"].nunique()),
        "panel_filas": len(panel),
    }
    primary_pipeline = artifact.get("pipeline_warm") or artifact["pipeline"]
    print("[train] Guardando modelo...", flush=True)
    joblib.dump(artifact, MODEL_PIPELINE_PATH)
    if use_dual:
        joblib.dump(artifact["pipeline_cold"], MODEL_PIPELINE_COLD_PATH)
        joblib.dump(artifact["pipeline_warm"], MODEL_PIPELINE_WARM_PATH)
    MODEL_THRESHOLD_PATH.write_text(
        json.dumps({"threshold": threshold}, indent=2),
        encoding="utf-8",
    )
    primary_pipeline.named_steps["model"].save_model(MODEL_XGBOOST_PATH)
    primary_pipeline.named_steps["model"].save_model(
        MODEL_XGBOOST_PATH.parent / "xgboost_baseline.json"
    )

    return {
        **metrics,
        "model_path": str(MODEL_PIPELINE_PATH),
        "reports_dir": str(reports_dir),
    }
