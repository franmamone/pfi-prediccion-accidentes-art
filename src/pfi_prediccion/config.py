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

ACCIDENTS_PARQUET = RAW_DIR / "accidentes_ml.parquet"
UNIVERSE_PARQUET = RAW_DIR / "establecimientos_universo.parquet"
PREVENCION_PARQUET = RAW_DIR / "prevencion_establecimiento_mes.parquet"
PANEL_PARQUET = PROCESSED_DIR / "panel_establecimiento_mes.parquet"

MODEL_PIPELINE_PATH = MODELS_DIR / "model_pipeline.joblib"
MODEL_PIPELINE_COLD_PATH = MODELS_DIR / "model_pipeline_cold.joblib"
MODEL_PIPELINE_WARM_PATH = MODELS_DIR / "model_pipeline_warm.joblib"
MODEL_XGBOOST_PATH = MODELS_DIR / "xgboost_model.json"
MODEL_THRESHOLD_PATH = MODELS_DIR / "threshold.json"

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

TARGET_COLUMN = "target_accidente_mes_siguiente"

PANEL_START = "2022-01"
PANEL_END = "2024-11"
TRAIN_YEARS = (2022, 2023)
VAL_YEAR = 2023  # mismo año que train: se usa solo para calibrar el umbral F2
TEST_YEAR = 2024


def load_env() -> None:
    load_dotenv(REPO_ROOT / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "si", "sí"}


def ensure_dirs() -> None:
    for path in (RAW_DIR, PROCESSED_DIR, REPORTS_DIR, MODELS_DIR):
        path.mkdir(parents=True, exist_ok=True)
