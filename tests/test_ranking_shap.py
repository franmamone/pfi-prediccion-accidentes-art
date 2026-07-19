"""Pruebas de SHAP operativo: aditividad, agregación one-hot y serialización JSON."""

from __future__ import annotations

import json
import math

import numpy as np
import pandas as pd

from pfi_prediccion.ranking_explain import (
    aggregate_shap_by_original_feature,
    aggregate_shap_cohort,
    build_top_contributions,
    validate_additivity,
)
from pfi_prediccion.shap_narrative import _es_construccion, _seccion_label


def test_aggregate_one_hot_sums_to_original_feature():
    names = [
        "num__accidentes_12m",
        "cat__ciiu_seccion_15",
        "cat__ciiu_seccion_45",
        "cat__mes_3",
        "cat__mes_11",
    ]
    shap_row = np.array([0.10, 0.02, -0.05, 0.01, 0.03], dtype=float)
    agg = aggregate_shap_by_original_feature(names, shap_row)
    assert math.isclose(agg["accidentes_12m"], 0.10)
    assert math.isclose(agg["ciiu_seccion"], -0.03)
    assert math.isclose(agg["mes"], 0.04)


def test_additivity_base_plus_shap_equals_margin():
    base = 0.25
    shap_row = np.array([0.1, -0.05, 0.02], dtype=float)
    margin = base + shap_row.sum()
    assert validate_additivity(base, shap_row, margin)
    assert not validate_additivity(base, shap_row, margin + 0.01)


def test_top_contributions_have_direction_and_no_nan_json():
    row = pd.Series(
        {
            "accidentes_12m": 2,
            "ciiu_seccion": "45",
            "cantidad_capitas": 12,
        }
    )
    names = ["num__accidentes_12m", "cat__ciiu_seccion_45", "num__cantidad_capitas"]
    shap_row = np.array([0.2, -0.1, 0.05], dtype=float)
    contribs = build_top_contributions(row, names, shap_row, top_k=3)
    assert len(contribs) == 3
    assert {c["direccion"] for c in contribs} <= {"aumenta", "reduce"}
    payload = json.dumps({"contribuciones": contribs}, ensure_ascii=False)
    assert "NaN" not in payload
    loaded = json.loads(payload)
    for c in loaded["contribuciones"]:
        assert isinstance(c["shap_value"], float)
        assert not math.isnan(c["shap_value"])


def test_ciiu_narrative_uses_rev3_construction():
    assert _es_construccion("45")
    assert not _es_construccion("41")  # en Rev.3, 41 = agua
    label = _seccion_label("45")
    assert "Construcción" in label
    assert "div." in label


def test_horizon_association_keys_differ_by_horizon():
    """Misma establecimiento+período puede coexistir en 1m y 3m con claves distintas."""
    key_1m = ("2025-11", "1m", "abc")
    key_3m = ("2025-11", "3m", "abc")
    assert key_1m != key_3m
    assert key_1m[0] == key_3m[0] and key_1m[2] == key_3m[2]
    assert key_1m[1] != key_3m[1]


def test_aggregate_shap_cohort_uses_full_matrix_not_top5_only():
    rows = [
        {"accidentes_12m": 0.2, "ciiu_seccion": -0.05, "cantidad_capitas": 0.01},
        {"accidentes_12m": 0.1, "ciiu_seccion": 0.02, "cantidad_capitas": -0.03},
        {"accidentes_12m": 0.15, "ciiu_seccion": -0.01, "cantidad_capitas": 0.02},
    ]
    agg = aggregate_shap_cohort(rows, top_k=50, max_features=10)
    assert len(agg) == 3
    assert agg[0]["feature"] == "accidentes_12m"
    assert agg[0]["orden_importancia"] == 1
    assert agg[0]["metodo"] == "matriz_completa"
    assert agg[0]["items_cohorte"] == 3
