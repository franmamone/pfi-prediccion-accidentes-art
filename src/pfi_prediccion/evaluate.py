from __future__ import annotations

import json
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, precision_recall_curve

from .config import MODEL_PIPELINE_PATH, REPORTS_DIR, TARGET_COLUMN, TEST_YEAR, ensure_dirs
from .inference import predict_proba_batched


TOP_K_VALUES = [50, 100, 200, 500, 1000, 2000]


def recall_at_top_k(y_true: np.ndarray, y_prob: np.ndarray, k: int) -> dict:
    n = len(y_true)
    k = min(k, n)
    if k == 0:
        return {"k": k, "recall": 0.0, "precision": 0.0, "lift": 0.0, "positives_in_top": 0}

    order = np.argsort(-y_prob)
    top_idx = order[:k]
    positives_top = int(y_true[top_idx].sum())
    total_positives = int(y_true.sum())
    base_rate = total_positives / n if n else 0.0
    precision = positives_top / k
    recall = positives_top / total_positives if total_positives else 0.0
    lift = precision / base_rate if base_rate > 0 else 0.0

    return {
        "k": k,
        "recall": float(recall),
        "precision": float(precision),
        "lift": float(lift),
        "positives_in_top": positives_top,
        "total_positives": total_positives,
    }


def evaluate_model(
    panel: pd.DataFrame,
    reports_dir: Path | None = None,
    pipeline_path: Path | None = None,
) -> dict:
    ensure_dirs()
    reports_dir = Path(reports_dir or REPORTS_DIR)
    reports_dir.mkdir(parents=True, exist_ok=True)

    artifact = joblib.load(pipeline_path or MODEL_PIPELINE_PATH)
    pipeline = artifact["pipeline"]
    threshold = float(artifact["threshold"])
    features = artifact["features"]

    test_df = panel[panel["anio"] == TEST_YEAR].copy()
    X_test = test_df[features]
    y_test = test_df[TARGET_COLUMN].to_numpy()

    print(f"[evaluate] Prediciendo test ({len(X_test):,} filas)...", flush=True)
    y_prob = predict_proba_batched(pipeline, X_test)

    top_k_metrics = [recall_at_top_k(y_test, y_prob, k) for k in TOP_K_VALUES]

    precision, recall, _ = precision_recall_curve(y_test, y_prob)
    pr_auc = float(average_precision_score(y_test, y_prob))

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    axes[0].plot(recall, precision, label=f"PR-AUC = {pr_auc:.3f}")
    axes[0].set_xlabel("Recall")
    axes[0].set_ylabel("Precisión")
    axes[0].set_title("Curva precisión-recall (test 2024)")
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    ks = [m["k"] for m in top_k_metrics]
    recalls = [m["recall"] for m in top_k_metrics]
    lifts = [m["lift"] for m in top_k_metrics]
    axes[1].bar(range(len(ks)), recalls, color="steelblue", alpha=0.8)
    axes[1].set_xticks(range(len(ks)))
    axes[1].set_xticklabels([str(k) for k in ks], rotation=45)
    axes[1].set_ylabel("Recall")
    axes[1].set_title("Recall @ top-K")
    for i, lift in enumerate(lifts):
        axes[1].text(i, recalls[i] + 0.01, f"×{lift:.1f}", ha="center", fontsize=8)

    fig.tight_layout()
    chart_path = reports_dir / "model_evaluation.png"
    fig.savefig(chart_path, dpi=120)
    plt.close(fig)

    scored = test_df[
        ["id_establecimiento", "periodo", "periodo_objetivo", TARGET_COLUMN]
    ].copy()
    scored["score_riesgo"] = y_prob
    scored["alerta"] = (y_prob >= threshold).astype(int)
    scored = scored.sort_values("score_riesgo", ascending=False)
    scored.to_csv(reports_dir / "scored_panel_test_2024.csv", index=False, sep=";")

    results = {
        "test_rows": len(test_df),
        "pr_auc": pr_auc,
        "threshold": threshold,
        "top_k": top_k_metrics,
        "chart_path": str(chart_path),
        "scored_path": str(reports_dir / "scored_panel_test_2024.csv"),
    }

    (reports_dir / "evaluation_metrics.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return results
