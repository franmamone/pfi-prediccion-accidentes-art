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
