"""Pruebas de targets 1m/3m, bordes y evaluación operativa."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from pfi_prediccion.config import TARGET_COLUMN_1M, TARGET_COLUMN_3M
from pfi_prediccion.evaluate import recall_at_top_k, top_k_per_quarter_non_overlapping
from pfi_prediccion.panel import _rolling_accident_features


def _tiny_panel() -> pd.DataFrame:
    """Un establecimiento, 6 meses, accidentes en mes 3 y 6 (1-indexed positions)."""
    periods = pd.period_range("2024-01", "2024-06", freq="M")
    accidentes = [0, 0, 1, 0, 0, 1]
    return pd.DataFrame(
        {
            "id_establecimiento": ["E1"] * 6,
            "periodo_key": periods,
            "periodo": periods.astype(str),
            "accidentes_en_mes": accidentes,
        }
    )


def test_target_1m_and_3m_values():
    panel = _rolling_accident_features(_tiny_panel(), data_end=pd.Period("2024-06", freq="M"))

    # Mes 2024-02 → T+1=mar tiene accidente → 1
    row_feb = panel.loc[panel["periodo"] == "2024-02"].iloc[0]
    assert row_feb[TARGET_COLUMN_1M] == 1.0

    # Mes 2024-03 → T+1=abr sin accidente → 0
    row_mar = panel.loc[panel["periodo"] == "2024-03"].iloc[0]
    assert row_mar[TARGET_COLUMN_1M] == 0.0

    # Mes 2024-03 → T+1..T+3 = abr,may,jun; jun tiene accidente → 1
    # (abril no es evaluable a 3m: faltaría julio)
    row_mar_3m = panel.loc[panel["periodo"] == "2024-03"].iloc[0]
    assert row_mar_3m[TARGET_COLUMN_3M] == 1.0

    # Mes 2024-01 → T+1..T+3 = feb,mar,abr; mar tiene → 1
    row_jan = panel.loc[panel["periodo"] == "2024-01"].iloc[0]
    assert row_jan[TARGET_COLUMN_3M] == 1.0

    row_apr = panel.loc[panel["periodo"] == "2024-04"].iloc[0]
    assert pd.isna(row_apr[TARGET_COLUMN_3M])


def test_borders_are_nan_not_zero():
    panel = _rolling_accident_features(_tiny_panel(), data_end=pd.Period("2024-06", freq="M"))

    # Último mes: sin T+1 → NaN
    last = panel.loc[panel["periodo"] == "2024-06"].iloc[0]
    assert pd.isna(last[TARGET_COLUMN_1M])
    assert pd.isna(last[TARGET_COLUMN_3M])

    # Meses sin 3 futuros completos (abr=ok con end-3=mar? end-3 = 2024-03)
    # end=2024-06 → evaluable 3m hasta 2024-03
    may = panel.loc[panel["periodo"] == "2024-05"].iloc[0]
    assert pd.isna(may[TARGET_COLUMN_3M])
    # 1m para mayo sí evaluable (junio existe)
    assert may[TARGET_COLUMN_1M] == 1.0


def test_no_leakage_future_into_past_features():
    """accidentes_en_mes del futuro no debe entrar en rolling pasado vía target fill."""
    panel = _rolling_accident_features(_tiny_panel(), data_end=pd.Period("2024-06", freq="M"))
    # En enero, accidentes_3m solo mira enero (rolling hacia atrás del mes actual inclusive)
    jan = panel.loc[panel["periodo"] == "2024-01"].iloc[0]
    assert jan["accidentes_3m"] == 0
    # En marzo, rolling 3m = ene+feb+mar = 1
    mar = panel.loc[panel["periodo"] == "2024-03"].iloc[0]
    assert mar["accidentes_3m"] == 1


def test_recall_at_top_k():
    y_true = np.array([1, 0, 1, 0, 0])
    y_prob = np.array([0.9, 0.8, 0.1, 0.2, 0.05])
    m = recall_at_top_k(y_true, y_prob, k=2)
    assert m["positives_in_top"] == 1
    assert m["precision"] == 0.5


def test_quarterly_non_overlapping_dedup():
    rows = []
    for periodo in ("2025-03", "2025-03", "2025-06"):
        rows.append(
            {
                "id_establecimiento": "A" if periodo.endswith("03") else "B",
                "periodo": periodo,
                "target_accidente_3m": 1,
                "score_riesgo": 0.9,
            }
        )
    # Duplicado mismo establecimiento mismo corte
    rows.append(
        {
            "id_establecimiento": "A",
            "periodo": "2025-03",
            "target_accidente_3m": 0,
            "score_riesgo": 0.1,
        }
    )
    scored = pd.DataFrame(rows)
    out = top_k_per_quarter_non_overlapping(
        scored, target_col="target_accidente_3m", year=2025, k_values=[1]
    )
    # Solo un establecimiento único en 2025-03
    mar = next(q for q in out["quarters"] if q["cutoff"] == "2025-03")
    assert mar["establecimientos_unicos"] == 1
