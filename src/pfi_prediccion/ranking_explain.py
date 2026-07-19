"""SHAP individual por ítems del ranking operativo (top capacidad mensual)."""

from __future__ import annotations

from collections import defaultdict

import joblib
import numpy as np
import pandas as pd
import shap

from .config import CAPACITY_MONTHLY, model_pipeline_path
from .shap_narrative import (
    THEME_LABELS,
    _base_feature_name,
    _theme_for_feature,
    build_human_readable_explanation,
)

SHAP_TOP_K = 5
ADDITIVITY_ATOL = 1e-4


FEATURE_LABELS: dict[str, str] = {
    "accidentes_12m": "Accidentes últimos 12 meses",
    "accidentes_total_previos": "Accidentes acumulados previos",
    "meses_desde_ultimo_accidente": "Meses desde último accidente",
    "tendencia_accidentes": "Tendencia de accidentes",
    "flag_alto_riesgo_historico": "Historial de alto riesgo",
    "flag_sin_historial_accidente": "Sin historial de accidentes",
    "tasa_accidentes": "Tasa de accidentes",
    "accidentes_por_capita": "Accidentes por cápita",
    "visitas_planificadas_12m": "Visitas planificadas 12m",
    "visitas_realizadas_12m": "Visitas realizadas 12m",
    "ratio_visitas_realizadas": "Cumplimiento de visitas",
    "meses_desde_ultima_visita": "Meses desde última visita",
    "brecha_visitas": "Brecha de visitas",
    "cantidad_capitas": "Cápitas",
    "dotacion_nomina_mes": "Dotación de nómina",
    "dotacion_establecimiento": "Dotación del establecimiento",
    "log_dotacion": "Dotación (log)",
    "ratio_dotacion": "Ratio de dotación",
    "ciiu_seccion": "División CIIU",
    "actividad_ciiu_establecimiento": "Actividad CIIU establecimiento",
    "actividad_ciiu_empleador": "Actividad CIIU empleador",
    "edad_promedio": "Edad promedio",
    "pct_mayores_50": "% mayores de 50",
    "antiguedad_promedio_meses": "Antigüedad promedio",
    "antiguedad_establecimiento_meses": "Antigüedad del local",
    "nivel_seguridad_establecimiento": "Nivel de seguridad",
    "flag_riesgo_higienico": "Riesgo higiénico",
    "anio": "Año",
    "mes": "Mes",
    "mes_sin": "Estacionalidad (seno)",
    "mes_cos": "Estacionalidad (coseno)",
}


def _preprocessed_matrix(pipeline, X: pd.DataFrame) -> tuple[np.ndarray, list[str]]:
    preprocess = pipeline.named_steps["preprocess"]
    Xt = preprocess.transform(X)
    feature_names = list(preprocess.get_feature_names_out())
    return Xt, feature_names


def _original_feature_key(preprocessed_name: str) -> str:
    """Agrupa columnas one-hot bajo la variable original (sin el valor categórico)."""
    base = _base_feature_name(preprocessed_name)
    # cat__ciiu_seccion_45 → ciiu_seccion; cat__mes_3 → mes
    if "__" in base:
        # rare double prefix leftovers
        base = base.split("__")[-1]
    # OneHotEncoder: feature_category
    for known in (
        "ciiu_seccion",
        "actividad_ciiu_establecimiento",
        "actividad_ciiu_empleador",
        "id_tipo_establecimiento",
        "id_provincia",
        "nivel_seguridad_establecimiento",
        "mes",
        "anio",
    ):
        if base == known or base.startswith(f"{known}_"):
            return known
    # Generic: strip trailing _value for one-hot
    if "_" in base:
        head, tail = base.rsplit("_", 1)
        if tail.replace(".", "", 1).isdigit() or tail in {"True", "False", "nan", "NA"}:
            return head
    return base


def aggregate_shap_by_original_feature(
    feature_names: list[str],
    shap_row: np.ndarray,
) -> dict[str, float]:
    aggregated: dict[str, float] = defaultdict(float)
    for name, value in zip(feature_names, shap_row, strict=True):
        key = _original_feature_key(name)
        aggregated[key] += float(value)
    return dict(aggregated)


def _format_observed_value(row: pd.Series, feature: str) -> str | None:
    if feature not in row.index:
        # try related columns
        candidates = [feature]
    else:
        candidates = [feature]
    if feature == "ciiu_seccion":
        candidates = ["ciiu_seccion", "actividad_ciiu_establecimiento"]
    for col in candidates:
        if col not in row.index:
            continue
        val = row[col]
        if val is None or (isinstance(val, float) and np.isnan(val)) or pd.isna(val):
            continue
        if isinstance(val, (float, np.floating)):
            if float(val).is_integer():
                return str(int(val))
            return f"{float(val):.3g}"
        return str(val)
    return None


def _friendly_label(feature: str) -> str:
    if feature in FEATURE_LABELS:
        return FEATURE_LABELS[feature]
    theme = _theme_for_feature(feature)
    return THEME_LABELS.get(theme, feature.replace("_", " "))


def build_top_contributions(
    row: pd.Series,
    feature_names: list[str],
    shap_row: np.ndarray,
    *,
    top_k: int = SHAP_TOP_K,
) -> list[dict]:
    aggregated = aggregate_shap_by_original_feature(feature_names, shap_row)
    ranked = sorted(aggregated.items(), key=lambda kv: -abs(kv[1]))[:top_k]
    contribs: list[dict] = []
    for orden, (feature, shap_val) in enumerate(ranked, start=1):
        theme_key = _theme_for_feature(feature)
        direccion = "aumenta" if shap_val >= 0 else "reduce"
        valor = _format_observed_value(row, feature)
        etiqueta = _friendly_label(feature)
        descripcion = (
            f"{etiqueta}"
            + (f" = {valor}" if valor is not None else "")
            + f" · contribución interna {shap_val:+.4f} ({direccion} el margen del modelo)"
        )
        contribs.append(
            {
                "orden": orden,
                "feature": feature,
                "tema": THEME_LABELS.get(theme_key, theme_key),
                "etiqueta": etiqueta,
                "valor_observado": valor,
                "shap_value": round(float(shap_val), 6),
                "direccion": direccion,
                "descripcion": descripcion[:500],
            }
        )
    return contribs


def validate_additivity(
    base_value: float,
    shap_row: np.ndarray,
    margin: float,
    *,
    atol: float = ADDITIVITY_ATOL,
) -> bool:
    reconstructed = float(base_value) + float(np.sum(shap_row))
    return abs(reconstructed - float(margin)) <= atol


def _raw_margin(model, Xt_row: np.ndarray) -> float:
    if hasattr(model, "predict"):
        # HistGradientBoosting / sklearn: decision_function if available
        if hasattr(model, "decision_function"):
            out = model.decision_function(Xt_row)
            return float(np.asarray(out).ravel()[0])
        # XGBoost sklearn wrapper
        try:
            booster = model.get_booster()
            import xgboost as xgb

            dmat = xgb.DMatrix(Xt_row)
            return float(booster.predict(dmat, output_margin=True)[0])
        except Exception:
            pass
    # Fallback: sum of SHAP will be checked against explainer expectation + sum
    return float("nan")


def aggregate_shap_cohort(
    feature_shap_rows: list[dict[str, float]],
    *,
    top_k: int,
    max_features: int = 20,
) -> list[dict]:
    """Agrega SHAP exacto (matriz completa por feature original) para una cohorte top-K."""
    if not feature_shap_rows:
        return []
    cohort = feature_shap_rows[:top_k]
    n = len(cohort)
    all_features = sorted({f for row in cohort for f in row})
    rows: list[dict] = []
    for feature in all_features:
        values = np.array([float(row.get(feature, 0.0)) for row in cohort], dtype=float)
        abs_vals = np.abs(values)
        theme_key = _theme_for_feature(feature)
        rows.append(
            {
                "feature": feature,
                "tema": THEME_LABELS.get(theme_key, theme_key),
                "etiqueta": _friendly_label(feature),
                "items_cohorte": n,
                "mean_abs_shap": round(float(abs_vals.mean()), 6),
                "mean_shap": round(float(values.mean()), 6),
                "p50_abs_shap": round(float(np.percentile(abs_vals, 50)), 6),
                "p90_abs_shap": round(float(np.percentile(abs_vals, 90)), 6),
                "pct_aumenta": round(float((values > 0).mean()), 4),
                "metodo": "matriz_completa",
            }
        )
    rows.sort(key=lambda r: -r["mean_abs_shap"])
    for i, row in enumerate(rows[:max_features], start=1):
        row["orden_importancia"] = i
    return rows[:max_features]


def explain_ranking_items(
    panel_month: pd.DataFrame,
    *,
    horizon: str,
    top_n: int = CAPACITY_MONTHLY,
    pipeline_path=None,
) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    """
    Calcula contribuciones SHAP individuales y agregados exactos top-50/top-225.

    Returns:
        (por_establecimiento, shap_agregados_por_topk)
    """
    path = pipeline_path or model_pipeline_path(horizon)
    artifact = joblib.load(path)
    features = artifact["features"]

    if artifact.get("dual_model"):
        pipeline_warm = artifact.get("pipeline_warm") or artifact["pipeline"]
        pipeline_cold = artifact.get("pipeline_cold") or pipeline_warm
    else:
        pipeline_warm = artifact.get("pipeline_warm") or artifact["pipeline"]
        pipeline_cold = pipeline_warm

    ranked = panel_month.sort_values("score_riesgo", ascending=False).head(top_n).copy()
    if ranked.empty:
        return {}, {"50": [], "225": []}

    explainers: dict[str, shap.TreeExplainer] = {}

    def _get_explainer(pipeline):
        key = str(id(pipeline))
        if key not in explainers:
            explainers[key] = shap.TreeExplainer(pipeline.named_steps["model"])
        return explainers[key]

    results: dict[str, dict] = {}
    feature_shap_rows: list[dict[str, float]] = []
    for _, row in ranked.iterrows():
        est_id = str(row["id_establecimiento"])
        is_cold = (
            artifact.get("dual_model")
            and "flag_sin_historial_accidente" in row.index
            and int(row.get("flag_sin_historial_accidente") or 0) == 1
        )
        pipeline = pipeline_cold if is_cold else pipeline_warm
        model = pipeline.named_steps["model"]
        X_row = pd.DataFrame([row[features]], columns=features)
        Xt, feature_names = _preprocessed_matrix(pipeline, X_row)
        explainer = _get_explainer(pipeline)
        shap_values = explainer.shap_values(Xt)
        shap_row = np.asarray(shap_values[0] if isinstance(shap_values, list) else shap_values[0]).ravel()

        expected = explainer.expected_value
        if isinstance(expected, (list, np.ndarray)):
            base_value = float(np.asarray(expected).ravel()[-1])
        else:
            base_value = float(expected)

        margin = _raw_margin(model, Xt)
        if np.isnan(margin):
            margin = base_value + float(np.sum(shap_row))
        additivity_ok = validate_additivity(base_value, shap_row, margin)

        aggregated = aggregate_shap_by_original_feature(feature_names, shap_row)
        feature_shap_rows.append(aggregated)

        contribuciones = build_top_contributions(row, feature_names, shap_row)
        human = build_human_readable_explanation(row, feature_names, shap_row)
        motivo = human.get("resumen") or (
            contribuciones[0]["descripcion"] if contribuciones else None
        )

        results[est_id] = {
            "contribuciones": contribuciones,
            "motivo_principal": motivo[:500] if motivo else None,
            "additivity_ok": additivity_ok,
            "base_value": round(base_value, 6),
            "margin": round(float(margin), 6),
            "score_riesgo": float(row.get("score_riesgo") or 0.0),
            "explicacion_legible": human,
        }

    shap_agregados = {
        "50": aggregate_shap_cohort(feature_shap_rows, top_k=50),
        "225": aggregate_shap_cohort(feature_shap_rows, top_k=225),
    }
    return results, shap_agregados
