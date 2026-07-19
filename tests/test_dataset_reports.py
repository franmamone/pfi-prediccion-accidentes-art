import pandas as pd

from pfi_prediccion.dataset_reports import (
    _capitas_band,
    _condition_metrics,
    _monthly_topk,
    ciiu_division_label,
)


def test_ciiu_uses_rev3_division_labels() -> None:
    assert ciiu_division_label(751100) == "Div. 75 — Administración pública y defensa"
    assert ciiu_division_label("801000") == "Div. 80 — Enseñanza"
    assert ciiu_division_label(None) == "Sin actividad informada"


def test_capitas_bands_keep_zero_as_unknown() -> None:
    values = pd.Series([None, 0, 1, 10, 11, 50, 51, 200, 201])
    assert _capitas_band(values).tolist() == [
        "Sin dato/0",
        "Sin dato/0",
        "1–10",
        "1–10",
        "11–50",
        "11–50",
        "51–200",
        "51–200",
        "201+",
    ]


def test_holdout_conditions_use_only_requested_periods() -> None:
    scored = pd.DataFrame(
        {
            "id_establecimiento": ["a", "b", "a", "b"],
            "periodo": ["2025-01", "2025-01", "2025-03", "2025-03"],
            "target": [0, 1, 1, 1],
            "score_riesgo": [0.9, 0.8, 0.9, 0.8],
        }
    )
    panel = pd.DataFrame(
        {
            "id_establecimiento": ["a", "b", "a", "b"],
            "periodo": ["2025-01", "2025-01", "2025-03", "2025-03"],
            "accidentes_total_previos": [1, 0, 1, 0],
            "cantidad_capitas": [100, 5, 100, 5],
            "dotacion_nomina_mes": [10, 0, 10, 0],
            "actividad_ciiu_establecimiento": [751100, 801000, 751100, 801000],
        }
    )

    monthly = _monthly_topk(scored, "target", k=1)
    assert monthly["precision"].tolist() == [0.0, 1.0]

    metrics = _condition_metrics(
        scored,
        panel,
        target="target",
        k=2,
        periods={"2025-03"},
    )
    history = {row["condicion"]: row for row in metrics["historial"]}
    assert history["Con accidentes previos"]["seleccionados"] == 1
    assert history["Sin accidentes previos"]["seleccionados"] == 1
    assert history["Con accidentes previos"]["precision"] == 1.0
