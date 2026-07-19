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

# Etiquetas CIIU Rev.3 (división 2 dígitos), alineadas con apps/web/src/ciiu.ts
# y dataset_reports.CIIU_DIVISION_LABELS. No usar Rev.4 aquí: los códigos del panel son Rev.3.
CIIU_SECCION_NOMBRES: dict[str, str] = {
    "01": "Agricultura y ganadería",
    "02": "Silvicultura",
    "05": "Pesca",
    "10": "Extracción de carbón",
    "11": "Extracción de petróleo y gas",
    "12": "Extracción de uranio",
    "13": "Extracción de minerales metalíferos",
    "14": "Explotación de otras minas",
    "15": "Alimentos y bebidas",
    "16": "Tabaco",
    "17": "Textiles",
    "18": "Prendas de vestir",
    "19": "Cuero y calzado",
    "20": "Madera",
    "21": "Papel",
    "22": "Edición e impresión",
    "23": "Coque y refinación de petróleo",
    "24": "Productos químicos",
    "25": "Caucho y plástico",
    "26": "Minerales no metálicos",
    "27": "Metales comunes",
    "28": "Productos elaborados de metal",
    "29": "Maquinaria y equipo",
    "30": "Maquinaria de oficina",
    "31": "Maquinaria y aparatos eléctricos",
    "32": "Radio, TV y comunicaciones",
    "33": "Instrumentos médicos y de precisión",
    "34": "Vehículos automotores",
    "35": "Otros equipos de transporte",
    "36": "Muebles y otras manufacturas",
    "37": "Reciclamiento",
    "40": "Electricidad y gas",
    "41": "Captación y distribución de agua",
    "45": "Construcción",
    "50": "Venta y reparación de vehículos",
    "51": "Comercio mayorista",
    "52": "Comercio minorista",
    "55": "Hoteles y restaurantes",
    "60": "Transporte terrestre",
    "61": "Transporte por agua",
    "62": "Transporte aéreo",
    "63": "Servicios auxiliares de transporte",
    "64": "Correo y telecomunicaciones",
    "65": "Intermediación financiera",
    "66": "Seguros",
    "67": "Servicios auxiliares financieros",
    "70": "Actividades inmobiliarias",
    "71": "Alquiler de maquinaria y equipo",
    "72": "Informática",
    "73": "Investigación y desarrollo",
    "74": "Servicios empresariales",
    "75": "Administración pública y defensa",
    "80": "Enseñanza",
    "85": "Servicios sociales y de salud",
    "90": "Saneamiento y gestión de residuos",
    "91": "Actividades asociativas",
    "92": "Actividades culturales y deportivas",
    "93": "Otros servicios",
    "95": "Hogares con servicio doméstico",
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
    nombre = CIIU_SECCION_NOMBRES.get(sec, f"división CIIU {sec}")
    return f"{nombre} (div. {sec})"


def _es_construccion(code) -> bool:
    # CIIU Rev.3: construcción = división 45 (no 41–43 de Rev.4).
    return ciiu_seccion(code) == "45"


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
