from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import text
from sqlalchemy.engine import Engine

from .config import ACCIDENTS_PARQUET, ML_VIEW, ensure_dirs
from .db import get_engine


def fetch_accidents(engine: Engine | None = None) -> pd.DataFrame:
    engine = engine or get_engine()
    query = text(f"SELECT * FROM {ML_VIEW}")
    with engine.connect() as conn:
        return pd.read_sql(query, conn)


def export_accidents_parquet(
    output_path: Path | None = None,
    engine: Engine | None = None,
) -> Path:
    ensure_dirs()
    output_path = Path(output_path or ACCIDENTS_PARQUET)
    df = fetch_accidents(engine=engine)
    df.to_parquet(output_path, index=False)
    return output_path
