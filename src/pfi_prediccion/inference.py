from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

DEFAULT_BATCH_ROWS = 50_000


def predict_proba_batched(
    pipeline: Pipeline,
    X: pd.DataFrame,
    batch_size: int = DEFAULT_BATCH_ROWS,
) -> np.ndarray:
    if len(X) <= batch_size:
        return pipeline.predict_proba(X)[:, 1]

    parts: list[np.ndarray] = []
    for start in range(0, len(X), batch_size):
        end = min(start + batch_size, len(X))
        parts.append(pipeline.predict_proba(X.iloc[start:end])[:, 1])
    return np.concatenate(parts)


def predict_blended_batched(
    artifact: dict,
    X: pd.DataFrame,
    batch_size: int = DEFAULT_BATCH_ROWS,
) -> np.ndarray:
    """Predicción por lotes con modelo dual (frío/cálido) o pipeline único."""
    features = artifact["features"]
    if not artifact.get("dual_model"):
        return predict_proba_batched(artifact["pipeline"], X[features], batch_size)

    if "flag_sin_historial_accidente" not in X.columns:
        raise ValueError("Se requiere flag_sin_historial_accidente para modelo dual.")

    probs = np.zeros(len(X), dtype=float)
    cold_mask = X["flag_sin_historial_accidente"].to_numpy() == 1
    if cold_mask.any():
        probs[cold_mask] = predict_proba_batched(
            artifact["pipeline_cold"], X.loc[cold_mask, features], batch_size
        )
    if (~cold_mask).any():
        probs[~cold_mask] = predict_proba_batched(
            artifact["pipeline_warm"], X.loc[~cold_mask, features], batch_size
        )
    return probs
