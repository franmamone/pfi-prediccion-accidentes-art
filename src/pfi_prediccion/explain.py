from __future__ import annotations

import json
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap

from .config import MODEL_PIPELINE_PATH, REPORTS_DIR, TARGET_COLUMN, TEST_YEAR, ensure_dirs
from .inference import predict_blended_batched

SHAP_SAMPLE_ROWS = 500
SHAP_MAX_DISPLAY = 20


def _preprocessed_matrix(pipeline, X: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    preprocess = pipeline.named_steps["preprocess"]
    model = pipeline.named_steps["model"]
    Xt = preprocess.transform(X)
    feature_names = preprocess.get_feature_names_out()
    return Xt, list(feature_names)


def run_shap_explain(
    panel: pd.DataFrame,
    reports_dir: Path | None = None,
    pipeline_path: Path | None = None,
    sample_rows: int = SHAP_SAMPLE_ROWS,
) -> dict:
    """SHAP global (summary) y ejemplo por predicción sobre muestra de test."""
    ensure_dirs()
    reports_dir = Path(reports_dir or REPORTS_DIR)
    reports_dir.mkdir(parents=True, exist_ok=True)

    artifact = joblib.load(pipeline_path or MODEL_PIPELINE_PATH)
    features = artifact["features"]
    pipeline = artifact.get("pipeline_warm") or artifact["pipeline"]

    test_df = panel[panel["anio"] == TEST_YEAR].copy()
    if test_df.empty:
        raise ValueError("No hay filas de test para SHAP.")

    rng = np.random.default_rng(42)
    n = min(sample_rows, len(test_df))
    sample_idx = rng.choice(len(test_df), size=n, replace=False)
    sample = test_df.iloc[sample_idx]
    X_sample = sample[features]

    print(f"[shap] Calculando sobre {n} filas de test...", flush=True)
    Xt, feature_names = _preprocessed_matrix(pipeline, X_sample)
    explainer = shap.TreeExplainer(pipeline.named_steps["model"])
    shap_values = explainer.shap_values(Xt)

    summary_path = reports_dir / "shap_summary.png"
    plt.figure(figsize=(10, 8))
    shap.summary_plot(shap_values, Xt, feature_names=feature_names, show=False, max_display=SHAP_MAX_DISPLAY)
    plt.tight_layout()
    plt.savefig(summary_path, dpi=120, bbox_inches="tight")
    plt.close()

    mean_abs = np.abs(shap_values).mean(axis=0)
    order = np.argsort(-mean_abs)[:SHAP_MAX_DISPLAY]
    top_features = [
        {"feature": feature_names[i], "mean_abs_shap": float(mean_abs[i])}
        for i in order
    ]

    scores = predict_blended_batched(artifact, X_sample)
    top_row = int(np.argmax(scores))
    row_idx = sample.index[top_row]
    row_X = X_sample.iloc[[top_row]]
    Xt_row, _ = _preprocessed_matrix(pipeline, row_X)
    shap_row = explainer.shap_values(Xt_row)[0]
    local_explain = {
        "id_establecimiento": str(sample.loc[row_idx, "id_establecimiento"]),
        "periodo": str(sample.loc[row_idx, "periodo"]),
        "score_riesgo": float(scores[top_row]),
        "target_real": int(sample.loc[row_idx, TARGET_COLUMN]),
        "top_drivers": [
            {"feature": feature_names[i], "shap": float(shap_row[i])}
            for i in np.argsort(-np.abs(shap_row))[:10]
        ],
    }

    bar_path = reports_dir / "shap_local_top_prediction.png"
    top_local = local_explain["top_drivers"][:10]
    plt.figure(figsize=(10, 6))
    plt.barh(
        [d["feature"] for d in reversed(top_local)],
        [d["shap"] for d in reversed(top_local)],
        color="steelblue",
    )
    plt.xlabel("SHAP value")
    plt.title(
        f"Top predicción — est. {local_explain['id_establecimiento']} "
        f"({local_explain['periodo']}) score={local_explain['score_riesgo']:.3f}"
    )
    plt.tight_layout()
    plt.savefig(bar_path, dpi=120, bbox_inches="tight")
    plt.close()

    result = {
        "sample_rows": n,
        "summary_plot": str(summary_path),
        "local_plot": str(bar_path),
        "global_top_features": top_features,
        "local_example": local_explain,
        "dual_model": bool(artifact.get("dual_model")),
        "note": "SHAP calculado con pipeline warm (o único); segmento cold usa el mismo preprocess.",
    }
    (reports_dir / "shap_report.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return result
