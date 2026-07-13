"""Gráficos de reporte sobre accidentes, panel y desempeño del modelo."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from .config import REPORTS_DIR, TARGET_COLUMN, ensure_dirs
from .features import ciiu_seccion

CIIU_SECCION_LABELS: dict[str, str] = {
    "41": "Construcción edificios",
    "42": "Ingeniería civil",
    "43": "Construcción especializada",
    "45": "Comercio mayorista",
    "46": "Comercio mayorista",
    "47": "Comercio minorista",
    "49": "Transporte",
    "52": "Depósito y logística",
    "55": "Hoteles y restaurantes",
    "62": "Tecnología",
    "86": "Salud",
    "NA": "Sin rubro",
}


def _capitas_tramo(capitas: pd.Series) -> pd.Series:
    c = pd.to_numeric(capitas, errors="coerce")
    out = pd.Series("sin dato", index=c.index, dtype="string")
    out[c.between(1, 10)] = "1-10 chica"
    out[c.between(11, 50)] = "11-50 pequeña"
    out[c.between(51, 200)] = "51-200 mediana"
    out[c > 200] = "201+ grande"
    return out


def _save_fig(fig: plt.Figure, path: Path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def _chart_catalog() -> list[dict]:
    """Catálogo de gráficos (existentes + nuevos) con qué muestra cada uno."""
    return [
        {
            "archivo": "eda_accidentes_por_anio.png",
            "origen": "EDA accidentes",
            "que_muestra": "Volumen de accidentes denunciados por año (2022-2024).",
            "para_que_sirve": "Ver tendencia temporal y que el período está balanceado.",
        },
        {
            "archivo": "eda_top_formas_accidente.png",
            "origen": "EDA accidentes",
            "que_muestra": "Las 10 formas de accidente más frecuentes (caídas, golpes, etc.).",
            "para_que_sirve": "Entender mecanismos dominantes de lesión en la cartera.",
        },
        {
            "archivo": "eda_dotacion.png",
            "origen": "EDA accidentes",
            "que_muestra": "Valores más repetidos de dotación al momento del accidente.",
            "para_que_sirve": "Detectar muchos ceros o valores atípicos en exposición.",
        },
        {
            "archivo": "report_accidentes_por_mes.png",
            "origen": "Reporte dataset",
            "que_muestra": "Accidentes por mes calendario.",
            "para_que_sirve": "Estacionalidad y meses con más/menos siniestros.",
        },
        {
            "archivo": "report_edad_trabajador.png",
            "origen": "Reporte dataset",
            "que_muestra": "Distribución de edad del trabajador accidentado.",
            "para_que_sirve": "Perfil demográfico de la población en riesgo.",
        },
        {
            "archivo": "report_ciiu_seccion.png",
            "origen": "Reporte dataset",
            "que_muestra": "Top secciones CIIU (2 dígitos) por cantidad de accidentes.",
            "para_que_sirve": "Rubros con más siniestros en volumen absoluto.",
        },
        {
            "archivo": "report_gravedad_accidente.png",
            "origen": "Reporte dataset",
            "que_muestra": "Distribución de gravedad de las lesiones.",
            "para_que_sirve": "Severidad típica; no se usa para predecir (evita leakage).",
        },
        {
            "archivo": "report_panel_eventos_por_mes.png",
            "origen": "Reporte panel",
            "que_muestra": "Establecimientos×mes con accidente el mes siguiente (target=1).",
            "para_que_sirve": "Volumen de eventos positivos que el modelo intenta predecir.",
        },
        {
            "archivo": "report_panel_tasa_positiva_mes.png",
            "origen": "Reporte panel",
            "que_muestra": "Porcentaje de filas panel con target positivo por mes.",
            "para_que_sirve": "Desbalance temporal; ~0,9% en promedio en universo completo.",
        },
        {
            "archivo": "report_nomina_cobertura_mes.png",
            "origen": "Reporte panel",
            "que_muestra": "Porcentaje de filas con dotación de nómina > 0 por mes.",
            "para_que_sirve": "Cobertura de la feature de nómina en el tiempo.",
        },
        {
            "archivo": "report_tasa_accidente_por_capitas.png",
            "origen": "Reporte panel",
            "que_muestra": "Tasa de accidente (target) por tramo de cápitas declaradas.",
            "para_que_sirve": "Relación tamaño de empresa vs riesgo observado.",
        },
        {
            "archivo": "report_visitas_prevencion_mes.png",
            "origen": "Reporte panel",
            "que_muestra": "Visitas realizadas (suma) vs establecimientos con al menos 1 visita ese mes.",
            "para_que_sirve": "Actividad real de prevención ART; no confundir con el top-50 del tablero.",
        },
        {
            "archivo": "report_accidentes_por_provincia.png",
            "origen": "Reporte dataset",
            "que_muestra": "Top provincias por cantidad de accidentes (id provincia establecimiento).",
            "para_que_sirve": "Concentración geográfica del riesgo observado.",
        },
        {
            "archivo": "report_panel_tasa_por_provincia.png",
            "origen": "Reporte panel",
            "que_muestra": "Tasa de accidente mes siguiente por provincia (top 12).",
            "para_que_sirve": "Comparar riesgo relativo entre provincias en el panel.",
        },
        {
            "archivo": "report_top_empleadores_accidentes.png",
            "origen": "Reporte dataset",
            "que_muestra": "Top 15 empleadores (id anonimizado) por accidentes en el período.",
            "para_que_sirve": "Concentración de siniestros en pocos empleadores.",
        },
        {
            "archivo": "report_heatmap_ciiu_mes.png",
            "origen": "Reporte dataset",
            "que_muestra": "Heatmap accidentes por sección CIIU × mes.",
            "para_que_sirve": "Estacionalidad y rubros críticos combinados.",
        },
        {
            "archivo": "model_evaluation.png",
            "origen": "Evaluación modelo",
            "que_muestra": "Curva precision-recall (PR-AUC) y recall@top-K global.",
            "para_que_sirve": "Calidad global del ranking y utilidad operativa top-K.",
        },
        {
            "archivo": "report_precision_top50_por_mes.png",
            "origen": "Evaluación modelo",
            "que_muestra": "Precision@50 por mes en test 2024.",
            "para_que_sirve": "Escenario real: si visitás 50 establecimientos/mes, ¿cuántos tenían accidente?",
        },
        {
            "archivo": "report_score_distribucion_test.png",
            "origen": "Evaluación modelo",
            "que_muestra": "Histograma de scores de riesgo en test 2024 (positivos vs negativos).",
            "para_que_sirve": "Separación del modelo entre clases en el holdout.",
        },
        {
            "archivo": "shap_summary.png",
            "origen": "SHAP",
            "que_muestra": "Importancia global de features (color = valor alto/bajo).",
            "para_que_sirve": "Qué variables usa el modelo en general.",
        },
        {
            "archivo": "shap_local_top_prediction.png",
            "origen": "SHAP",
            "que_muestra": "Drivers SHAP del caso con mayor score en la muestra.",
            "para_que_sirve": "Ejemplo de explicación local para un prevencionista.",
        },
    ]


def _accidents_charts(accidents: pd.DataFrame, output_dir: Path) -> list[str]:
    generated: list[str] = []
    df = accidents.copy()
    df["fecha_hora_accidente"] = pd.to_datetime(df["fecha_hora_accidente"])
    df["periodo_mes"] = df["fecha_hora_accidente"].dt.to_period("M").astype(str)

    sns.set_theme(style="whitegrid")

    fig, ax = plt.subplots(figsize=(10, 4))
    df.groupby("periodo_mes").size().sort_index().plot(kind="bar", ax=ax, color="#2f6fed")
    ax.set_title("Accidentes por mes")
    ax.set_xlabel("Período")
    ax.set_ylabel("Cantidad")
    ax.tick_params(axis="x", rotation=90, labelsize=7)
    path = output_dir / "report_accidentes_por_mes.png"
    _save_fig(fig, path)
    generated.append(path.name)

    if "edad_trabajador" in df.columns:
        edad = pd.to_numeric(df["edad_trabajador"], errors="coerce").dropna()
        edad = edad[(edad >= 16) & (edad <= 75)]
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.hist(edad, bins=30, color="#5c7cfa", edgecolor="white")
        ax.set_title("Edad del trabajador accidentado")
        ax.set_xlabel("Años")
        ax.set_ylabel("Frecuencia")
        path = output_dir / "report_edad_trabajador.png"
        _save_fig(fig, path)
        generated.append(path.name)

    if "actividad_ciiu_establecimiento" in df.columns:
        sec = df["actividad_ciiu_establecimiento"].map(ciiu_seccion)
        sec_label = sec.map(lambda s: CIIU_SECCION_LABELS.get(s, f"Sec. {s}"))
        top = sec_label.value_counts().head(12)
        fig, ax = plt.subplots(figsize=(9, 5))
        top.sort_values().plot(kind="barh", ax=ax, color="#1f9d55")
        ax.set_title("Accidentes por sección CIIU (top 12)")
        path = output_dir / "report_ciiu_seccion.png"
        _save_fig(fig, path)
        generated.append(path.name)

    if "gravedad" in df.columns:
        grav = df["gravedad"].fillna("Sin dato").value_counts().head(10)
        fig, ax = plt.subplots(figsize=(8, 4))
        grav.plot(kind="barh", ax=ax, color="#e03131")
        ax.set_title("Gravedad de la lesión (top 10)")
        path = output_dir / "report_gravedad_accidente.png"
        _save_fig(fig, path)
        generated.append(path.name)

    if "id_provincia_establecimiento" in df.columns:
        prov = (
            df["id_provincia_establecimiento"]
            .fillna("Sin dato")
            .astype(str)
            .value_counts()
            .head(12)
        )
        fig, ax = plt.subplots(figsize=(8, 5))
        prov.sort_values().plot(kind="barh", ax=ax, color="#1098ad")
        ax.set_title("Accidentes por provincia (establecimiento, top 12)")
        ax.set_xlabel("Cantidad")
        path = output_dir / "report_accidentes_por_provincia.png"
        _save_fig(fig, path)
        generated.append(path.name)

    if "id_empleador" in df.columns:
        top_emp = df["id_empleador"].value_counts().head(15)
        fig, ax = plt.subplots(figsize=(9, 5))
        labels = [f"...{e[-6:]}" for e in top_emp.index.astype(str)]
        ax.barh(labels, top_emp.values, color="#495057")
        ax.set_title("Top 15 empleadores por accidentes (id anonimizado)")
        ax.set_xlabel("Accidentes")
        ax.invert_yaxis()
        path = output_dir / "report_top_empleadores_accidentes.png"
        _save_fig(fig, path)
        generated.append(path.name)

    if "actividad_ciiu_establecimiento" in df.columns:
        tmp = df.copy()
        tmp["ciiu_sec"] = tmp["actividad_ciiu_establecimiento"].map(ciiu_seccion)
        tmp["ciiu_label"] = tmp["ciiu_sec"].map(
            lambda s: CIIU_SECCION_LABELS.get(s, f"Sec. {s}")
        )
        pivot = (
            tmp.groupby(["periodo_mes", "ciiu_label"], observed=True)
            .size()
            .unstack(fill_value=0)
        )
        top_secs = tmp["ciiu_label"].value_counts().head(10).index
        pivot = pivot.reindex(columns=top_secs, fill_value=0)
        if not pivot.empty:
            fig, ax = plt.subplots(figsize=(12, 6))
            sns.heatmap(pivot.T, cmap="YlOrRd", ax=ax, linewidths=0.2)
            ax.set_title("Accidentes por sección CIIU × mes (top 10 rubros)")
            ax.set_xlabel("Mes")
            ax.set_ylabel("Sección CIIU")
            path = output_dir / "report_heatmap_ciiu_mes.png"
            _save_fig(fig, path)
            generated.append(path.name)

    return generated


def _prevencion_validation(panel: pd.DataFrame) -> dict:
    """Estadísticas para validar el gráfico de visitas vs intuición operativa."""
    if not {"visitas_planificadas_mes", "visitas_realizadas_mes"}.issubset(panel.columns):
        return {}

    period_col = "periodo" if "periodo" in panel.columns else "periodo_key"
    df = panel.copy()
    if period_col == "periodo_key":
        df["periodo"] = df["periodo_key"].astype(str)

    monthly = df.groupby("periodo").agg(
        visitas_realizadas=("visitas_realizadas_mes", "sum"),
        visitas_planificadas=("visitas_planificadas_mes", "sum"),
        establecimientos_visitados=(
            "visitas_realizadas_mes",
            lambda s: int((s > 0).sum()),
        ),
        filas_panel=("id_establecimiento", "size"),
    )
    monthly = monthly.reset_index()

    spike = monthly.loc[monthly["visitas_realizadas"].idxmax()]
    typical = monthly[
        (monthly["periodo"] >= "2022-06") & (monthly["periodo"] <= "2023-12")
    ]

    return {
        "interpretacion": (
            "Cada barra/punto es la SUMA de visitas en toda la cartera (~35k establecimientos×mes), "
            "no el top-50 del tablero. En la práctica casi siempre coincide con "
            "'establecimientos con ≥1 visita' porque la mayoría tiene 0 o 1 visita por mes."
        ),
        "tablero_referencia_top_k": 50,
        "promedio_mensual": {
            "visitas_realizadas": round(float(monthly["visitas_realizadas"].mean()), 1),
            "establecimientos_visitados": round(
                float(monthly["establecimientos_visitados"].mean()), 1
            ),
            "filas_panel": int(monthly["filas_panel"].median()),
        },
        "periodo_2022_2023": {
            "visitas_realizadas_promedio": round(
                float(typical["visitas_realizadas"].mean()), 1
            ),
            "establecimientos_visitados_promedio": round(
                float(typical["establecimientos_visitados"].mean()), 1
            ),
        },
        "pico_mes": {
            "periodo": str(spike["periodo"]),
            "visitas_realizadas": int(spike["visitas_realizadas"]),
            "establecimientos_visitados": int(spike["establecimientos_visitados"]),
            "nota": (
                "Revisar calidad de datos si el pico es atípico "
                "(ej. carga masiva de fechas en un solo mes)."
            ),
        },
        "correlacion_visitas_vs_establecimientos": round(
            float(
                monthly["visitas_realizadas"].corr(monthly["establecimientos_visitados"])
            ),
            4,
        ),
        "detalle_mensual": monthly.to_dict(orient="records"),
    }


def _panel_charts(panel: pd.DataFrame, output_dir: Path) -> tuple[list[str], dict]:
    generated: list[str] = []
    prevencion_stats: dict = {}
    if panel.empty or TARGET_COLUMN not in panel.columns:
        return generated, prevencion_stats

    df = panel.copy()
    if "periodo" not in df.columns and "periodo_key" in df.columns:
        df["periodo"] = df["periodo_key"].astype(str)

    monthly = df.groupby("periodo").agg(
        filas=(TARGET_COLUMN, "size"),
        positivos=(TARGET_COLUMN, "sum"),
    )
    monthly["tasa_pct"] = 100 * monthly["positivos"] / monthly["filas"]

    fig, ax = plt.subplots(figsize=(10, 4))
    monthly["positivos"].plot(kind="bar", ax=ax, color="#f08c00")
    ax.set_title("Eventos positivos por mes (establecimiento×mes con accidente siguiente)")
    ax.set_ylabel("Cantidad")
    ax.tick_params(axis="x", rotation=90, labelsize=7)
    path = output_dir / "report_panel_eventos_por_mes.png"
    _save_fig(fig, path)
    generated.append(path.name)

    fig, ax = plt.subplots(figsize=(10, 4))
    monthly["tasa_pct"].plot(kind="line", ax=ax, marker="o", color="#ae3ec9")
    ax.set_title("Tasa de accidente mes siguiente (% del panel)")
    ax.set_ylabel("%")
    ax.tick_params(axis="x", rotation=90, labelsize=7)
    path = output_dir / "report_panel_tasa_positiva_mes.png"
    _save_fig(fig, path)
    generated.append(path.name)

    if "dotacion_nomina_mes" in df.columns:
        nom = pd.to_numeric(df["dotacion_nomina_mes"], errors="coerce").fillna(0) > 0
        cov = df.assign(_nom=nom).groupby("periodo")["_nom"].mean() * 100
        fig, ax = plt.subplots(figsize=(10, 4))
        cov.plot(kind="line", ax=ax, marker="o", color="#099268")
        ax.set_title("Cobertura de nómina (% filas con dotación > 0)")
        ax.set_ylabel("%")
        ax.tick_params(axis="x", rotation=90, labelsize=7)
        path = output_dir / "report_nomina_cobertura_mes.png"
        _save_fig(fig, path)
        generated.append(path.name)

    if "cantidad_capitas" in df.columns:
        tmp = df.copy()
        tmp["tramo_capitas"] = _capitas_tramo(tmp["cantidad_capitas"])
        order = ["1-10 chica", "11-50 pequeña", "51-200 mediana", "201+ grande", "sin dato"]
        rates = (
            tmp.groupby("tramo_capitas", observed=True)[TARGET_COLUMN]
            .mean()
            .reindex(order)
            * 100
        )
        fig, ax = plt.subplots(figsize=(8, 4))
        rates.plot(kind="bar", ax=ax, color="#364fc7")
        ax.set_title("Tasa de accidente por tramo de cápitas")
        ax.set_ylabel("% filas con target=1")
        ax.tick_params(axis="x", rotation=15)
        path = output_dir / "report_tasa_accidente_por_capitas.png"
        _save_fig(fig, path)
        generated.append(path.name)

    if "id_provincia_establecimiento" in df.columns:
        prov_rates = (
            df.assign(
                prov=df["id_provincia_establecimiento"].fillna("Sin dato").astype(str)
            )
            .groupby("prov", observed=True)[TARGET_COLUMN]
            .agg(tasa="mean", n="size")
        )
        prov_rates = prov_rates[prov_rates["n"] >= 500].sort_values("tasa", ascending=False).head(12)
        if not prov_rates.empty:
            fig, ax = plt.subplots(figsize=(8, 5))
            (prov_rates["tasa"] * 100).sort_values().plot(kind="barh", ax=ax, color="#7048e8")
            ax.set_title("Tasa accidente mes siguiente por provincia (top 12, n≥500)")
            ax.set_xlabel("% filas con target=1")
            path = output_dir / "report_panel_tasa_por_provincia.png"
            _save_fig(fig, path)
            generated.append(path.name)

    if {"visitas_planificadas_mes", "visitas_realizadas_mes"}.issubset(df.columns):
        prevencion_stats = _prevencion_validation(df)
        vis = df.groupby("periodo").agg(
            realizadas=("visitas_realizadas_mes", "sum"),
            establecimientos_visitados=(
                "visitas_realizadas_mes",
                lambda s: int((s > 0).sum()),
            ),
        )
        fig, ax = plt.subplots(figsize=(11, 4))
        ax.plot(
            vis.index,
            vis["realizadas"],
            marker="o",
            label="Visitas realizadas (suma)",
            color="#1971c2",
        )
        ax.plot(
            vis.index,
            vis["establecimientos_visitados"],
            marker="s",
            label="Establecimientos con ≥1 visita",
            color="#2f9e44",
            linestyle="--",
        )
        ax.axhline(50, color="#e03131", linestyle=":", linewidth=1.5, label="Top-50 tablero (ref.)")
        ax.set_title("Prevención ART por mes — visitas vs establecimientos visitados")
        ax.set_ylabel("Cantidad")
        ax.legend(loc="upper right", fontsize=8)
        ax.tick_params(axis="x", rotation=90, labelsize=7)
        path = output_dir / "report_visitas_prevencion_mes.png"
        _save_fig(fig, path)
        generated.append(path.name)

    return generated, prevencion_stats


def _model_charts(output_dir: Path) -> list[str]:
    generated: list[str] = []
    topk_path = output_dir / "top_k_per_month.json"
    if topk_path.exists():
        data = json.loads(topk_path.read_text(encoding="utf-8"))
        months = [m for m in data.get("months", []) if m.get("positivos", 0) > 0]
        if months:
            periodos = [m["periodo"] for m in months]
            prec = [m.get("precision_at_50", 0) for m in months]
            fig, ax = plt.subplots(figsize=(10, 4))
            ax.bar(periodos, prec, color="steelblue")
            ax.axhline(np.mean(prec), color="red", linestyle="--", label=f"media {np.mean(prec):.0%}")
            ax.set_ylim(0, 1)
            ax.set_title("Precision @ top-50 por mes (test 2024)")
            ax.set_ylabel("Precision")
            ax.legend()
            ax.tick_params(axis="x", rotation=90, labelsize=7)
            path = output_dir / "report_precision_top50_por_mes.png"
            _save_fig(fig, path)
            generated.append(path.name)

    scored_path = output_dir / "scored_panel_test_2024.csv"
    if scored_path.exists():
        scored = pd.read_csv(scored_path, sep=";")
        if {"score_riesgo", TARGET_COLUMN}.issubset(scored.columns):
            fig, ax = plt.subplots(figsize=(8, 4))
            neg = scored.loc[scored[TARGET_COLUMN] == 0, "score_riesgo"]
            pos = scored.loc[scored[TARGET_COLUMN] == 1, "score_riesgo"]
            ax.hist(neg, bins=50, alpha=0.6, label="Sin accidente", color="#74c0fc", density=True)
            ax.hist(pos, bins=50, alpha=0.6, label="Con accidente", color="#ff6b6b", density=True)
            ax.set_title("Distribución de score de riesgo (test 2024)")
            ax.set_xlabel("Score")
            ax.legend()
            path = output_dir / "report_score_distribucion_test.png"
            _save_fig(fig, path)
            generated.append(path.name)

    return generated


def run_dataset_reports(
    accidents: pd.DataFrame,
    panel: pd.DataFrame | None = None,
    output_dir: Path | None = None,
) -> dict:
    """Genera gráficos de dataset + índice explicativo en reports/."""
    ensure_dirs()
    output_dir = Path(output_dir or REPORTS_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("[reports] Generando gráficos de accidentes...", flush=True)
    new_files = _accidents_charts(accidents, output_dir)

    prevencion_stats: dict = {}
    if panel is not None and not panel.empty:
        print(f"[reports] Generando gráficos de panel ({len(panel):,} filas)...", flush=True)
        panel_files, prevencion_stats = _panel_charts(panel, output_dir)
        new_files.extend(panel_files)

    print("[reports] Gráficos de evaluación/modelo...", flush=True)
    new_files.extend(_model_charts(output_dir))

    catalog = _chart_catalog()
    index = {
        "graficos_generados_esta_corrida": new_files,
        "catalogo": catalog,
        "validacion_prevencion": prevencion_stats,
        "nota": "Los PNG de EDA/SHAP/evaluate se generan en sus propios pasos del pipeline.",
    }
    index_path = output_dir / "reports_chart_index.json"
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")

    if prevencion_stats:
        val_path = output_dir / "report_prevencion_validacion.json"
        val_path.write_text(
            json.dumps(prevencion_stats, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    return {
        "output_dir": str(output_dir),
        "graficos_nuevos": new_files,
        "indice": str(index_path),
        "validacion_prevencion": prevencion_stats.get("promedio_mensual"),
        "total_catalogo": len(catalog),
    }
