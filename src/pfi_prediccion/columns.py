"""Esquema de columnas de ml.vw_siniestros_accidente_ml."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

VIEW_COLUMNS: list[str] = [
    "id_accidente",
    "id_trabajador",
    "id_empleador",
    "id_establecimiento",
    "fecha_hora_accidente",
    "dias_demora_denuncia",
    "anio_accidente",
    "mes_accidente",
    "trimestre_accidente",
    "dia_semana_accidente",
    "hora_accidente",
    "temporada_argentina",
    "sexo_trabajador",
    "edad_trabajador",
    "tramo_edad_trabajador",
    "estado_civil_trabajador",
    "actividad_ciuo_trabajador",
    "antiguedad_empleador_meses",
    "antiguedad_trabajador_establecimiento_meses",
    "horas_semanales_trabajador",
    "id_tarea_nomina_trabajador",
    "id_tipo_turno_trabajador",
    "cantidad_capitas",
    "actividad_ciiu_empleador",
    "nivel_seguridad_empleador",
    "actividad_ciiu_establecimiento",
    "actividad_ciiu_rev4_principal",
    "frecuencia_visita_ciiu_meses",
    "id_tipo_establecimiento",
    "flag_establecimiento_principal",
    "nivel_seguridad_establecimiento",
    "antiguedad_establecimiento_meses",
    "id_provincia_establecimiento",
    "codigo_postal_establecimiento",
    "flag_coordenadas_validas",
    "latitud_establecimiento",
    "longitud_establecimiento",
    "flag_riesgo_higienico",
    "dotacion_establecimiento",
    "id_provincia_ocurrencia",
    "codigo_postal_ocurrencia",
    "id_subtipo_siniestro",
    "id_modalidad_denuncia",
    "gravedad",
    "diagnostico_oms",
    "naturaleza_lesion",
    "zona_afectada",
    "porcentaje_incapacidad_estimada",
    "flag_actividad_habitual",
    "flag_cronico",
    "flag_demanda_judicial",
    "antiguedad_puesto_meses",
    "dias_ilt",
    "agente_causante",
    "forma_accidente",
    "flag_ocurrencia_via_publica",
    "flag_pese_vigente",
    "visitas_planificadas_12m",
    "visitas_realizadas_12m",
    "siniestros_establecimiento_12m",
    "siniestros_empleador_12m",
    "siniestros_trabajador_24m",
]


UNIVERSE_COLUMNS: list[str] = [
    "id_establecimiento",
    "id_empleador",
    "cantidad_capitas",
    "actividad_ciiu_empleador",
    "nivel_seguridad_empleador",
    "actividad_ciiu_establecimiento",
    "actividad_ciiu_rev4_principal",
    "frecuencia_visita_ciiu_meses",
    "id_tipo_establecimiento",
    "flag_establecimiento_principal",
    "nivel_seguridad_establecimiento",
    "antiguedad_establecimiento_meses",
    "id_provincia_establecimiento",
    "codigo_postal_establecimiento",
    "flag_coordenadas_validas",
    "latitud_establecimiento",
    "longitud_establecimiento",
    "flag_riesgo_higienico",
]


PREVENCION_COLUMNS: list[str] = [
    "id_establecimiento",
    "periodo",
    "anio",
    "mes",
    "visitas_planificadas_mes",
    "visitas_realizadas_mes",
]


def read_ssms_csv(path: Path, min_columns: int = 10) -> pd.DataFrame:
    """Lee un export de SSMS sin encabezados (prueba ;, tab y ,)."""
    for sep in (";", "\t", ","):
        try:
            df = pd.read_csv(path, sep=sep, encoding="utf-8-sig", low_memory=False, header=None)
            if df.shape[1] >= min_columns:
                return df
        except pd.errors.ParserError:
            continue
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def _has_valid_header(columns: pd.Index) -> bool:
    normalized = {str(c).strip().lower() for c in columns}
    return "fecha_hora_accidente" in normalized or "id_accidente" in normalized


def normalize_accidents_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if not _has_valid_header(out.columns):
        if len(out.columns) != len(VIEW_COLUMNS):
            raise ValueError(
                f"Se esperaban {len(VIEW_COLUMNS)} columnas sin encabezado SSMS, "
                f"pero el archivo tiene {len(out.columns)}."
            )
        out.columns = VIEW_COLUMNS

    out.columns = [str(c).strip() for c in out.columns]
    out = out.replace({"NULL": pd.NA, "null": pd.NA, "": pd.NA})

    if "fecha_hora_accidente" in out.columns:
        out["fecha_hora_accidente"] = pd.to_datetime(out["fecha_hora_accidente"])

    return out


def _has_universe_header(columns: pd.Index) -> bool:
    normalized = {str(c).strip().lower() for c in columns}
    return "id_establecimiento" in normalized and "id_empleador" in normalized


def normalize_universe_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    if not _has_universe_header(out.columns):
        if len(out.columns) != len(UNIVERSE_COLUMNS):
            raise ValueError(
                f"Se esperaban {len(UNIVERSE_COLUMNS)} columnas de universo, "
                f"pero el archivo tiene {len(out.columns)}."
            )
        out.columns = UNIVERSE_COLUMNS

    out.columns = [str(c).strip() for c in out.columns]
    out = out.replace({"NULL": pd.NA, "null": pd.NA, "": pd.NA})
    out = out.drop_duplicates(subset=["id_establecimiento"], keep="first")
    return out


def normalize_prevencion_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    normalized = {str(c).strip().lower() for c in out.columns}
    if "id_establecimiento" not in normalized or "periodo" not in normalized:
        if len(out.columns) != len(PREVENCION_COLUMNS):
            raise ValueError(
                f"Se esperaban {len(PREVENCION_COLUMNS)} columnas de prevención, "
                f"pero el archivo tiene {len(out.columns)}."
            )
        out.columns = PREVENCION_COLUMNS

    out.columns = [str(c).strip() for c in out.columns]
    out = out.replace({"NULL": pd.NA, "null": pd.NA, "": pd.NA})
    return out
