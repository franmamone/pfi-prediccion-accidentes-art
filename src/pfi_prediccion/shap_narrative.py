"""Traducción de valores SHAP a motivos legibles en español."""

from __future__ import annotations

from collections import defaultdict

import numpy as np
import pandas as pd

from .features import ciiu_seccion

THEME_LABELS = {
    "historial": "Historial de accidentes",
    "prevencion": "Prevención y visitas",
    "tamano": "Tamaño / dotación",
    "rubro": "Rubro de actividad (CIIU)",
    "planta": "Composición de la plantilla",
    "establecimiento": "Características del establecimiento",
    "temporal": "Estacionalidad / período",
    "otros": "Otros factores",
}

CIIU_SECCION_NOMBRES: dict[str, str] = {
    "01": "Agricultura",
    "02": "Silvicultura",
    "03": "Pesca",
    "05": "Extracción de petróleo y gas",
    "06": "Minería",
    "07": "Minería metalífera",
    "08": "Otras minas",
    "09": "Servicios de apoyo minero",
    "10": "Elaboración de alimentos",
    "11": "Bebidas y tabaco",
    "12": "Textiles",
    "13": "Prendas de vestir",
    "14": "Cuero y calzado",
    "15": "Madera y corcho",
    "16": "Papel y cartón",
    "17": "Impresión",
    "18": "Medios audiovisuales",
    "19": "Coque y refinación",
    "20": "Química",
    "21": "Farmacéutica",
    "22": "Caucho y plástico",
    "23": "Minerales no metálicos",
    "24": "Metalurgia básica",
    "25": "Productos de metal",
    "26": "Tecnología y electrónica",
    "27": "Maquinaria y equipo",
    "28": "Maquinaria especial",
    "29": "Vehículos automotores",
    "30": "Otros equipos de transporte",
    "31": "Muebles",
    "32": "Otras manufacturas",
    "33": "Reparación de maquinaria",
    "35": "Energía eléctrica y gas",
    "36": "Agua",
    "37": "Saneamiento",
    "38": "Gestión de residuos",
    "39": "Descontaminación",
    "41": "Construcción de edificios",
    "42": "Ingeniería civil",
    "43": "Construcción especializada",
    "45": "Comercio mayorista",
    "46": "Comercio mayorista (agentes)",
    "47": "Comercio minorista",
    "49": "Transporte terrestre",
    "50": "Transporte marítimo",
    "51": "Transporte aéreo",
    "52": "Depósito y logística",
    "53": "Correo y mensajería",
    "55": "Hoteles y restaurantes",
    "56": "Servicios de comida",
    "58": "Edición",
    "59": "Audiovisual",
    "60": "Telecomunicaciones",
    "61": "Telecomunicaciones",
    "62": "Tecnología de la información",
    "63": "Servicios de información",
    "64": "Servicios financieros",
    "65": "Seguros",
    "66": "Auxiliares financieros",
    "68": "Inmobiliario",
    "69": "Servicios jurídicos y contables",
    "70": "Administración de empresas",
    "71": "Arquitectura e ingeniería",
    "72": "Investigación y desarrollo",
    "73": "Publicidad",
    "74": "Otros servicios profesionales",
    "75": "Servicios veterinarios",
    "77": "Alquiler",
    "78": "Empleo",
    "79": "Agencias de viaje",
    "80": "Seguridad e investigación",
    "81": "Servicios para edificios",
    "82": "Servicios administrativos",
    "84": "Administración pública",
    "85": "Educación",
    "86": "Salud",
    "87": "Residencias de cuidado",
    "88": "Servicios sociales",
    "90": "Artes y espectáculos",
    "91": "Bibliotecas y museos",
    "92": "Juegos y apuestas",
    "93": "Deportes y recreación",
    "94": "Asociaciones",
    "95": "Reparación de efectos personales",
    "96": "Otros servicios personales",
    "97": "Hogares privados",
    "99": "Organizaciones extraterritoriales",
    "NA": "rubro no informado",
}


def _capitas_tramo(capitas) -> tuple[str, str]:
    if capitas is None or (isinstance(capitas, float) and np.isnan(capitas)) or capitas <= 0:
        return "sin_dato", "sin cápitas declaradas"
    c = int(capitas)
    if c <= 10:
        return "chica", f"empresa chica ({c} cápitas)"
    if c <= 50:
        return "pequena", f"empresa pequeña ({c} cápitas)"
    if c <= 200:
        return "mediana", f"empresa mediana ({c} cápitas)"
    return "grande", f"empresa grande ({c:,} cápitas)".replace(",", ".")


def _seccion_label(code) -> str:
    sec = ciiu_seccion(code)
    nombre = CIIU_SECCION_NOMBRES.get(sec, f"sección CIIU {sec}")
    return f"{nombre} (sección {sec})"


def _es_construccion(code) -> bool:
    sec = ciiu_seccion(code)
    return sec in {"41", "42", "43"}


def _base_feature_name(preprocessed_name: str) -> str:
    if preprocessed_name.startswith("num__"):
        return preprocessed_name[5:]
    if preprocessed_name.startswith("cat__"):
        return preprocessed_name[5:]
    return preprocessed_name


def _theme_for_feature(base: str) -> str:
    if base.startswith("ciiu_seccion") or base.startswith("actividad_ciiu"):
        return "rubro"
    if any(
        k in base
        for k in (
            "accidentes_",
            "meses_desde_ultimo_accidente",
            "tendencia_accidentes",
            "flag_alto_riesgo_historico",
            "flag_sin_historial_accidente",
            "tasa_accidentes",
            "accidentes_por_capita",
        )
    ):
        return "historial"
    if any(
        k in base
        for k in (
            "visitas_",
            "ratio_visitas",
            "brecha_visitas",
            "meses_desde_ultima_visita",
        )
    ):
        return "prevencion"
    if any(
        k in base
        for k in (
            "cantidad_capitas",
            "log_dotacion",
            "dotacion_nomina",
            "dotacion_establecimiento",
            "ratio_dotacion",
        )
    ):
        return "tamano"
    if any(
        k in base
        for k in (
            "edad_promedio",
            "pct_mayores",
            "pct_mujeres",
            "antiguedad_promedio",
            "pct_antiguedad",
            "tareas_distintas",
            "pct_en_tarea",
        )
    ):
        return "planta"
    if any(
        k in base
        for k in (
            "antiguedad_establecimiento",
            "nivel_seguridad",
            "id_tipo_establecimiento",
            "flag_establecimiento",
            "id_provincia",
            "flag_coordenadas",
            "latitud_establecimiento",
            "longitud_establecimiento",
            "flag_riesgo_higienico",
            "frecuencia_visita_ciiu",
        )
    ):
        return "establecimiento"
    if base in {"anio", "mes", "mes_sin", "mes_cos"}:
        return "temporal"
    return "otros"


def _aggregate_shap_by_theme(feature_names: list[str], shap_row: np.ndarray) -> dict[str, float]:
    themes: dict[str, float] = defaultdict(float)
    for i, fn in enumerate(feature_names):
        theme = _theme_for_feature(_base_feature_name(fn))
        themes[theme] += float(shap_row[i])
    return dict(themes)


def _describe_historial(row: pd.Series) -> str:
    parts: list[str] = []
    a12 = row.get("accidentes_12m")
    if a12 is not None and not pd.isna(a12) and int(a12) > 0:
        parts.append(f"{int(a12)} accidente(s) en los últimos 12 meses")
    total = row.get("accidentes_total_previos")
    if total is not None and not pd.isna(total) and int(total) > 0:
        parts.append(f"{int(total)} accidente(s) acumulados previos")
    meses = row.get("meses_desde_ultimo_accidente")
    if meses is not None and not pd.isna(meses) and float(meses) < 900:
        parts.append(f"último accidente hace {int(float(meses))} mes(es)")
    if not parts:
        return "sin historial reciente de accidentes en el panel"
    return "; ".join(parts)


def _describe_prevencion(row: pd.Series) -> str:
    parts: list[str] = []
    plan = row.get("visitas_planificadas_12m")
    real = row.get("visitas_realizadas_12m")
    if plan is not None and not pd.isna(plan):
        p, r = int(plan or 0), int(real or 0) if real is not None and not pd.isna(real) else 0
        parts.append(f"{r}/{p} visitas realizadas en 12 meses")
    meses_vis = row.get("meses_desde_ultima_visita")
    if meses_vis is not None and not pd.isna(meses_vis) and float(meses_vis) < 900:
        parts.append(f"última visita hace {int(float(meses_vis))} mes(es)")
    ratio = row.get("ratio_visitas_realizadas")
    if ratio is not None and not pd.isna(ratio):
        parts.append(f"cumplimiento visitas {float(ratio):.0%}")
    if not parts:
        return "sin datos de visitas de prevención"
    return "; ".join(parts)


def _describe_tamano(row: pd.Series) -> str:
    _, etiqueta = _capitas_tramo(row.get("cantidad_capitas"))
    parts = [etiqueta]
    nomina = row.get("dotacion_nomina_mes")
    if nomina is not None and not pd.isna(nomina) and int(nomina) > 0:
        parts.append(f"dotación nómina {int(nomina):,}".replace(",", "."))
    dot = row.get("dotacion_establecimiento")
    if dot is not None and not pd.isna(dot) and int(dot) > 0:
        parts.append(f"dotación registrada {int(dot):,}".replace(",", "."))
    return "; ".join(parts)


def _describe_rubro(row: pd.Series) -> str:
    nombre_est = row.get("actividad_ciiu_establecimiento_nombre")
    nombre_rev4 = row.get("actividad_ciiu_rev4_nombre")
    nombre_emp = row.get("actividad_ciiu_empleador_nombre")
    grupo = row.get("actividad_grupo_nombre")
    ciiu_est = row.get("actividad_ciiu_establecimiento")
    ciiu_emp = row.get("actividad_ciiu_empleador")

    nombre = None
    for candidate in (nombre_est, nombre_rev4, nombre_emp):
        if candidate is not None and not pd.isna(candidate) and str(candidate).strip():
            nombre = str(candidate).strip()
            break

    if nombre:
        parts = [nombre]
        if grupo is not None and not pd.isna(grupo) and str(grupo).strip():
            parts.append(f"grupo {str(grupo).strip()}")
        base = " — ".join(parts) if len(parts) > 1 else parts[0]
        code = ciiu_est if pd.notna(ciiu_est) else ciiu_emp
        if _es_construccion(code):
            return f"{base} (sector construcción)"
        if pd.notna(code):
            return f"{base} (CIIU {code})"
        return base

    label = _seccion_label(ciiu_est if pd.notna(ciiu_est) else ciiu_emp)
    if _es_construccion(ciiu_est if pd.notna(ciiu_est) else ciiu_emp):
        return f"{label} — sector construcción"
    if pd.notna(ciiu_est):
        return f"{label} (CIIU establecimiento {ciiu_est})"
    return label


def _describe_planta(row: pd.Series) -> str:
    parts: list[str] = []
    edad = row.get("edad_promedio")
    if edad is not None and not pd.isna(edad):
        parts.append(f"edad promedio {float(edad):.0f} años")
    pct50 = row.get("pct_mayores_50")
    if pct50 is not None and not pd.isna(pct50):
        parts.append(f"{float(pct50):.0%} mayores de 50")
    ant = row.get("antiguedad_promedio_meses")
    if ant is not None and not pd.isna(ant):
        parts.append(f"antigüedad promedio {float(ant) / 12:.1f} años")
    if not parts:
        return "sin datos de nómina agregada"
    return "; ".join(parts)


def _describe_establecimiento(row: pd.Series) -> str:
    parts: list[str] = []
    ant = row.get("antiguedad_establecimiento_meses")
    if ant is not None and not pd.isna(ant):
        parts.append(f"antigüedad del local {int(float(ant))} meses")
    niv = row.get("nivel_seguridad_establecimiento")
    if niv is not None and not pd.isna(niv):
        parts.append(f"nivel seguridad {int(niv)}")
    if row.get("flag_riesgo_higienico") == 1:
        parts.append("riesgo higiénico")
    if not parts:
        return "características generales del establecimiento"
    return "; ".join(parts)


def _describe_temporal(row: pd.Series) -> str:
    return f"período {row.get('periodo', 'N/D')}"


_THEME_DESCRIBERS = {
    "historial": _describe_historial,
    "prevencion": _describe_prevencion,
    "tamano": _describe_tamano,
    "rubro": _describe_rubro,
    "planta": _describe_planta,
    "establecimiento": _describe_establecimiento,
    "temporal": _describe_temporal,
    "otros": lambda _row: "otros predictores del modelo",
}


def build_human_readable_explanation(
    row: pd.Series,
    feature_names: list[str],
    shap_row: np.ndarray,
    *,
    min_abs_shap: float = 0.01,
    max_drivers: int = 6,
) -> dict:
    """Agrupa SHAP por tema y arma motivos legibles en español."""
    theme_shap = _aggregate_shap_by_theme(feature_names, shap_row)
    tramo_codigo, tramo_etiqueta = _capitas_tramo(row.get("cantidad_capitas"))
    rubro_label = _describe_rubro(row)

    drivers: list[dict] = []
    for theme, shap_val in sorted(theme_shap.items(), key=lambda x: -abs(x[1])):
        if abs(shap_val) < min_abs_shap:
            continue
        describer = _THEME_DESCRIBERS.get(theme, _THEME_DESCRIBERS["otros"])
        drivers.append(
            {
                "tema": THEME_LABELS.get(theme, theme),
                "descripcion": describer(row),
                "shap_agrupado": round(shap_val, 4),
                "efecto": "aumenta_riesgo" if shap_val > 0 else "reduce_riesgo",
            }
        )

    drivers = drivers[:max_drivers]

    resumen_partes: list[str] = []
    for d in drivers:
        flecha = "↑" if d["efecto"] == "aumenta_riesgo" else "↓"
        resumen_partes.append(f"{d['tema']}: {d['descripcion']} ({flecha})")

    flags: list[str] = []
    if tramo_codigo in {"chica", "pequena"}:
        flags.append("empresa de tamaño reducido")
    if _es_construccion(row.get("actividad_ciiu_establecimiento")) or _es_construccion(
        row.get("actividad_ciiu_empleador")
    ):
        flags.append("sector construcción")

    perfil_riesgo = None
    if flags:
        perfil_riesgo = (
            f"Perfil destacado: {', '.join(flags)}. "
            "El modelo puede ponderar más el riesgo cuando coinciden tamaño y rubro."
        )

    return {
        "tramo_tamano": tramo_codigo,
        "tramo_tamano_etiqueta": tramo_etiqueta,
        "rubro": rubro_label,
        "es_construccion": _es_construccion(row.get("actividad_ciiu_establecimiento"))
        or _es_construccion(row.get("actividad_ciiu_empleador")),
        "motivos_por_tema": drivers,
        "resumen": "; ".join(resumen_partes) if resumen_partes else "Sin motivos dominantes en esta predicción.",
        "perfil_destacado": perfil_riesgo,
    }
