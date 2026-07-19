"""Pruebas de splits temporales y política de ranking."""

from __future__ import annotations

import pandas as pd
import pytest

from pfi_prediccion.config import (
    CALIBRATION_YEAR,
    HOLDOUT_YEAR,
    TARGET_COLUMN_1M,
    TRAIN_YEARS,
)
from pfi_prediccion.ranking_policy import _band
from pfi_prediccion.train import _expanding_temporal_folds, _temporal_splits


def _fake_panel() -> pd.DataFrame:
    rows = []
    for year in (2022, 2023, 2024, 2025):
        for month in range(1, 13):
            if year == 2025 and month > 9:
                target = float("nan")
            else:
                target = 1.0 if month % 7 == 0 else 0.0
            rows.append(
                {
                    "id_establecimiento": "E1",
                    "periodo": f"{year}-{month:02d}",
                    "anio": year,
                    "mes": month,
                    TARGET_COLUMN_1M: target,
                }
            )
    return pd.DataFrame(rows)


def test_temporal_splits_keep_holdout_2025():
    train, calib, holdout = _temporal_splits(_fake_panel(), TARGET_COLUMN_1M)
    assert set(train["anio"].unique()).issubset(set(TRAIN_YEARS))
    assert set(calib["anio"].unique()) == {CALIBRATION_YEAR}
    assert set(holdout["anio"].unique()) == {HOLDOUT_YEAR}
    assert holdout[TARGET_COLUMN_1M].notna().all()


def test_temporal_splits_fallback_without_2025():
    panel = _fake_panel()
    panel = panel[panel["anio"] < 2025].copy()
    train, calib, holdout = _temporal_splits(panel, TARGET_COLUMN_1M)
    assert not holdout.empty
    assert holdout["anio"].max() == 2024


def test_expanding_folds_are_temporal():
    panel = _fake_panel()
    train = panel[panel["anio"].isin(TRAIN_YEARS)].copy()
    train = train[train[TARGET_COLUMN_1M].notna()]
    folds = _expanding_temporal_folds(train)
    assert folds
    for tr_idx, va_idx in folds:
        tr_periods = set(train.loc[tr_idx, "periodo"])
        va_periods = set(train.loc[va_idx, "periodo"])
        assert tr_periods.isdisjoint(va_periods)
        assert max(tr_periods) < min(va_periods)


def test_band_thresholds():
    assert _band(1) == "critico"
    assert _band(50) == "critico"
    assert _band(51) == "alto"
    assert _band(225) == "alto"
    assert _band(226) == "medio"
