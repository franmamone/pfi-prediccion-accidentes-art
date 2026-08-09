"""Features derivadas del panel (sin leakage)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def ciiu_seccion(code) -> str:
    if pd.isna(code):
        return "NA"
    text = str(code).strip()
    if not text or text.lower() == "nan":
        return "NA"
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 2:
        return digits[:2]
    return "NA"


# Agrupación por división CIIU Rev.3 (2 dígitos) a un rubro legible para la UI.
# Cubre las secciones A–Q para minimizar la bolsa "Otros".
SECTOR_LABELS = {
    # A: Agricultura, ganadería, caza y silvicultura
    "01": "Agro",
    "02": "Agro",
    # B: Pesca
    "05": "Agro",
    # C: Explotación de minas y canteras
    "10": "Minería",
    "11": "Minería",
    "12": "Minería",
    "13": "Minería",
    "14": "Minería",
    # D: Industria manufacturera
    "15": "Industria",
    "16": "Industria",
    "17": "Industria",
    "18": "Industria",
    "19": "Industria",
    "20": "Industria",
    "21": "Industria",
    "22": "Industria",
    "23": "Industria",
    "24": "Industria",
    "25": "Industria",
    "26": "Industria",
    "27": "Industria",
    "28": "Industria",
    "29": "Industria",
    "30": "Industria",
    "31": "Industria",
    "32": "Industria",
    "33": "Industria",
    "34": "Industria",
    "35": "Industria",
    "36": "Industria",
    "37": "Industria",
    # E: Suministro de electricidad, gas y agua
    "40": "Energía y agua",
    "41": "Energía y agua",
    # F: Construcción
    "45": "Construcción",
    # G: Comercio
    "50": "Comercio",
    "51": "Comercio",
    "52": "Comercio",
    # H: Hoteles y restaurantes
    "55": "Hotelería y gastronomía",
    # I: Transporte, almacenamiento y comunicaciones
    "60": "Transporte",
    "61": "Transporte",
    "62": "Transporte",
    "63": "Transporte",
    "64": "Transporte",
    # J: Intermediación financiera
    "65": "Finanzas",
    "66": "Finanzas",
    "67": "Finanzas",
    # K: Actividades inmobiliarias, empresariales y de alquiler
    "70": "Servicios empresariales",
    "71": "Servicios empresariales",
    "72": "Servicios empresariales",
    "73": "Servicios empresariales",
    "74": "Servicios empresariales",
    # L: Administración pública y defensa
    "75": "Administración pública",
    # M: Enseñanza
    "80": "Enseñanza",
    # N: Servicios sociales y de salud
    "85": "Salud",
    # O: Otras actividades de servicios comunitarios, sociales y personales
    "90": "Servicios comunitarios",
    "91": "Servicios comunitarios",
    "92": "Servicios comunitarios",
    "93": "Servicios comunitarios",
    # P: Hogares privados con servicio doméstico
    "95": "Servicio doméstico",
    # Q: Organizaciones y órganos extraterritoriales
    "99": "Organismos extraterritoriales",
}


def sector_label(code) -> str:
    """Rubro legible a partir de un código CIIU o de una sección de 2 dígitos."""
    sec = ciiu_seccion(code)
    return SECTOR_LABELS.get(sec, "Otros")


def enrich_panel_features(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()

    out["ciiu_seccion"] = out["actividad_ciiu_establecimiento"].map(ciiu_seccion)

    # Visitas: preferir datos mensuales de prevención; si no, fallback accidente.
    if "visitas_planificadas_12m_prev" in out.columns:
        out["visitas_planificadas_12m"] = out["visitas_planificadas_12m_prev"].fillna(
            out.get("visitas_planificadas_12m")
        )
        out["visitas_realizadas_12m"] = out["visitas_realizadas_12m_prev"].fillna(
            out.get("visitas_realizadas_12m")
        )
        out = out.drop(
            columns=["visitas_planificadas_12m_prev", "visitas_realizadas_12m_prev"],
            errors="ignore",
        )

    if "visitas_planificadas_12m" in out.columns and "visitas_realizadas_12m" in out.columns:
        planned = pd.to_numeric(out["visitas_planificadas_12m"], errors="coerce").fillna(0)
        done = pd.to_numeric(out["visitas_realizadas_12m"], errors="coerce").fillna(0)
        out["ratio_visitas_realizadas"] = np.where(planned > 0, done / planned, np.nan)
        out["brecha_visitas"] = planned - done
    else:
        out["ratio_visitas_realizadas"] = np.nan
        out["brecha_visitas"] = np.nan

    if "accidentes_3m" in out.columns and "accidentes_6m" in out.columns:
        prev_3m = out["accidentes_6m"] - out["accidentes_3m"]
        out["tendencia_accidentes_3m"] = out["accidentes_3m"] - prev_3m
    else:
        out["tendencia_accidentes_3m"] = 0

    out["flag_alto_riesgo_historico"] = (out.get("accidentes_12m", 0) >= 3).astype(int)
    out["flag_sin_historial_accidente"] = (out.get("accidentes_total_previos", 0) == 0).astype(int)

    def _num_col(df: pd.DataFrame, col: str) -> pd.Series:
        if col in df.columns:
            return pd.to_numeric(df[col], errors="coerce")
        return pd.Series(np.nan, index=df.index, dtype=float)

    dotacion = _num_col(out, "dotacion_establecimiento")
    capitas = _num_col(out, "cantidad_capitas")
    exposicion = dotacion.fillna(capitas).fillna(0).clip(lower=0)

    if "dotacion_establecimiento" in out.columns:
        out["log_dotacion"] = np.log1p(
            pd.to_numeric(out["dotacion_establecimiento"], errors="coerce").fillna(0).clip(lower=0)
        )
    else:
        out["log_dotacion"] = np.log1p(exposicion)

    out["tasa_accidentes_12m_exposicion"] = np.where(
        exposicion > 0,
        out.get("accidentes_12m", 0) / exposicion,
        np.nan,
    )
    out["accidentes_por_capita_12m"] = np.where(
        capitas.fillna(0) > 0,
        out.get("accidentes_12m", 0) / capitas,
        np.nan,
    )

    if "dotacion_nomina_mes" in out.columns:
        nomina_dot = pd.to_numeric(out["dotacion_nomina_mes"], errors="coerce").fillna(0)
        out["ratio_dotacion_nomina_capitas"] = np.where(
            capitas.fillna(0) > 0,
            nomina_dot / capitas,
            np.nan,
        )
        out["pct_mayores_50"] = pd.to_numeric(out.get("pct_mayores_50"), errors="coerce")
        out["pct_en_tarea_principal"] = pd.to_numeric(
            out.get("pct_en_tarea_principal"), errors="coerce"
        )

    if "meses_desde_ultimo_accidente" in out.columns:
        out["meses_desde_ultimo_accidente"] = out["meses_desde_ultimo_accidente"].fillna(999)

    if "meses_desde_ultima_visita" in out.columns:
        out["meses_desde_ultima_visita"] = out["meses_desde_ultima_visita"].fillna(999)

    out["mes_sin"] = np.sin(2 * np.pi * out["mes"] / 12)
    out["mes_cos"] = np.cos(2 * np.pi * out["mes"] / 12)

    return out
