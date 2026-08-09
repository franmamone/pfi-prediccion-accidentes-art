from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REPORTS_DIR = REPO_ROOT / "reports"
MODELS_DIR = REPO_ROOT / "models"

# Subcarpetas de artefactos generados (ver reports/README.md)
REPORTS_EDA_DIR = REPORTS_DIR / "eda"
REPORTS_MODEL_DIR = REPORTS_DIR / "modelo"
REPORTS_RANKING_DIR = REPORTS_DIR / "ranking"
REPORTS_SHAP_DIR = REPORTS_DIR / "shap"
REPORTS_DATASET_DIR = REPORTS_DIR / "dataset"
REPORTS_CONTEXT_DIR = REPORTS_DATASET_DIR / "contexto_2022_2025"
REPORTS_TRAIN_DIR = REPORTS_DATASET_DIR / "entrenamiento_2022_2023"
REPORTS_HOLDOUT_DIR = REPORTS_DATASET_DIR / "desempeno_holdout_2025"
REPORTS_LEGACY_DIR = REPORTS_DIR / "legacy"

ACCIDENTS_PARQUET = RAW_DIR / "accidentes_ml.parquet"
UNIVERSE_PARQUET = RAW_DIR / "establecimientos_universo.parquet"
PREVENCION_PARQUET = RAW_DIR / "prevencion_establecimiento_mes.parquet"
NOMINA_PARQUET = RAW_DIR / "nomina_establecimiento_mes.parquet"
PANEL_PARQUET = PROCESSED_DIR / "panel_establecimiento_mes.parquet"

MODEL_PIPELINE_1M_PATH = MODELS_DIR / "model_pipeline_1m.joblib"
MODEL_PIPELINE_3M_PATH = MODELS_DIR / "model_pipeline_3m.joblib"
MODEL_PIPELINE_COLD_PATH = MODELS_DIR / "model_pipeline_cold.joblib"
MODEL_PIPELINE_WARM_PATH = MODELS_DIR / "model_pipeline_warm.joblib"
MODEL_XGBOOST_PATH = MODELS_DIR / "xgboost_model.json"
MODEL_THRESHOLD_PATH = MODELS_DIR / "threshold.json"
# Alias: por defecto el modelo mensual.
MODEL_PIPELINE_PATH = MODEL_PIPELINE_1M_PATH

ML_VIEW = "ml.vw_siniestros_accidente_ml"

# Columnas del accidente que NO deben usarse como features predictivas (post-evento / leakage).
LEAKAGE_COLUMNS = frozenset(
    {
        "id_accidente",
        "fecha_hora_accidente",
        "dias_demora_denuncia",
        "gravedad",
        "diagnostico_oms",
        "naturaleza_lesion",
        "zona_afectada",
        "porcentaje_incapacidad_estimada",
        "flag_actividad_habitual",
        "flag_cronico",
        "flag_demanda_judicial",
        "dias_ilt",
        "agente_causante",
        "forma_accidente",
        "id_subtipo_siniestro",
        "id_modalidad_denuncia",
        "flag_ocurrencia_via_publica",
        "id_trabajador",
        "sexo_trabajador",
        "edad_trabajador",
        "tramo_edad_trabajador",
        "estado_civil_trabajador",
        "actividad_ciuo_trabajador",
        "horas_semanales_trabajador",
        "id_tarea_nomina_trabajador",
        "id_tipo_turno_trabajador",
        "antiguedad_trabajador_establecimiento_meses",
        "antiguedad_puesto_meses",
        "siniestros_trabajador_24m",
    }
)

TARGET_COLUMN_1M = "target_accidente_mes_siguiente"
TARGET_COLUMN_3M = "target_accidente_3m"
TARGET_COLUMN = TARGET_COLUMN_1M

PANEL_START = "2022-01"
# Último mes de features con accidentes disponibles hasta 2025-12:
# - 1m: se puede evaluar hasta 2025-11 (target = 2025-12)
# - 3m: se puede evaluar hasta 2025-09 (target = 2025-10..12)
PANEL_END = "2025-11"
DATA_END = "2025-12"

TRAIN_YEARS = (2022, 2023)
CALIBRATION_YEAR = 2024
HOLDOUT_YEAR = 2025
TEST_YEAR = HOLDOUT_YEAR  # alias usado en explain.py

# Capacidad operativa de referencia. La ART realiza ~7.500 visitas/año
# (verificado en ART_CORE 2022-2024): campaña anual concentrada en Q1 (miles)
# y régimen estable ~270-330/mes el resto del año. 225/mes ≈ ritmo estable.
CAPACITY_CRITICAL = 50
CAPACITY_MONTHLY = 225
CAPACITY_QUARTERLY = 675
VISIT_COOLDOWN_MONTHS = 3

HORIZON_1M = "1m"
HORIZON_3M = "3m"

# Curva de acierto histórico (precision@K, media por mes en holdout 2025).
# Fuente: reports/modelo/evaluation_metrics_{1m|3m}.json → top_k_per_month.
# Debe mantenerse en sync con AciertoHistoricoLookup en apps/api/Program.cs.
PRECISION_AT_K = {
    HORIZON_3M: [
        (50, 0.935),
        (100, 0.881),
        (200, 0.807),
        (225, 0.790),
        (300, 0.735),
        (400, 0.681),
        (500, 0.637),
        (675, 0.575),
        (1000, 0.495),
    ],
    HORIZON_1M: [
        (50, 0.764),
        (100, 0.671),
        (200, 0.540),
        (225, 0.515),
        (300, 0.453),
        (400, 0.394),
        (500, 0.354),
        (675, 0.302),
        (1000, 0.243),
    ],
}

# Umbrales de banda por acierto histórico (precision@K del tramo).
# Criterio: la criticidad depende de cuánto acierta el modelo en ese tramo.
# Escala única (independiente del horizonte):
#   Crítico ≥80% · Alto ≥60% · Medio ≥30% · Bajo <30%.
# Nota: en el horizonte mensual el mejor tramo (top-50) alcanza ~76%, por lo
# que puede no haber "crítico" en 1m; sí los hay en el trimestral (≥80%).
BAND_ACCURACY_THRESHOLDS = {
    HORIZON_3M: {"critico": 0.80, "alto": 0.60, "medio": 0.30},
    HORIZON_1M: {"critico": 0.80, "alto": 0.60, "medio": 0.30},
}


def precision_at_rank(rank: int, horizon: str = HORIZON_1M) -> float | None:
    """Acierto histórico (precision@K) del tramo al que pertenece ``rank``.

    Devuelve la precisión del primer tramo cuyo tope K es >= rank; None si
    ``rank`` cae fuera del último tramo evaluado (top-1000).
    """
    tabla = PRECISION_AT_K.get(horizon, PRECISION_AT_K[HORIZON_1M])
    for k, prec in tabla:
        if rank <= k:
            return prec
    return None


def banda_por_acierto(rank: int, horizon: str = HORIZON_1M) -> str:
    """Banda operativa según el acierto histórico del tramo de ``rank``.

    critico/alto/medio/bajo por umbrales de precisión (ver
    ``BAND_ACCURACY_THRESHOLDS``). Fuera del top-1000 evaluado → 'bajo'.
    """
    prec = precision_at_rank(rank, horizon)
    if prec is None:
        return "bajo"
    th = BAND_ACCURACY_THRESHOLDS.get(horizon, BAND_ACCURACY_THRESHOLDS[HORIZON_1M])
    if prec >= th["critico"]:
        return "critico"
    if prec >= th["alto"]:
        return "alto"
    if prec >= th["medio"]:
        return "medio"
    return "bajo"

# Cortes trimestrales no solapados: features al cierre del mes indicado.
QUARTERLY_CUTOFFS = ("03", "06", "09", "12")


def model_pipeline_path(horizon: str = HORIZON_1M) -> Path:
    if horizon == HORIZON_3M:
        return MODEL_PIPELINE_3M_PATH
    return MODEL_PIPELINE_1M_PATH


def target_column_for_horizon(horizon: str = HORIZON_1M) -> str:
    if horizon == HORIZON_3M:
        return TARGET_COLUMN_3M
    return TARGET_COLUMN_1M


def load_env() -> None:
    load_dotenv(REPO_ROOT / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "si", "sí"}


def ensure_dirs() -> None:
    for path in (
        RAW_DIR,
        PROCESSED_DIR,
        REPORTS_DIR,
        REPORTS_EDA_DIR,
        REPORTS_MODEL_DIR,
        REPORTS_RANKING_DIR,
        REPORTS_SHAP_DIR,
        REPORTS_DATASET_DIR,
        REPORTS_CONTEXT_DIR,
        REPORTS_TRAIN_DIR,
        REPORTS_HOLDOUT_DIR,
        REPORTS_LEGACY_DIR,
        MODELS_DIR,
    ):
        path.mkdir(parents=True, exist_ok=True)
