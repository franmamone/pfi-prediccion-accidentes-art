"""Reportes separados por propósito: contexto, entrenamiento y holdout."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

from .config import (
    CAPACITY_CRITICAL,
    CAPACITY_MONTHLY,
    CAPACITY_QUARTERLY,
    HOLDOUT_YEAR,
    REPORTS_CONTEXT_DIR,
    REPORTS_DATASET_DIR,
    REPORTS_HOLDOUT_DIR,
    REPORTS_MODEL_DIR,
    REPORTS_RANKING_DIR,
    REPORTS_TRAIN_DIR,
    TARGET_COLUMN_1M,
    TARGET_COLUMN_3M,
    TRAIN_YEARS,
    ensure_dirs,
)
from .features import ciiu_seccion


# Los códigos de la fuente corresponden a divisiones CIIU Rev. 3 (dos dígitos).
# No son "secciones": las secciones son letras y agrupan varias divisiones.
CIIU_DIVISION_LABELS: dict[str, str] = {
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
    "NA": "Sin actividad informada",
}


def ciiu_division_label(code: object) -> str:
    division = ciiu_seccion(code)
    name = CIIU_DIVISION_LABELS.get(division, "Actividad no catalogada")
    return f"Div. {division} — {name}" if division != "NA" else name


def _period_range(df: pd.DataFrame, date_col: str) -> str:
    dates = pd.to_datetime(df[date_col], errors="coerce").dropna()
    if dates.empty:
        return "período sin determinar"
    return f"{dates.min():%Y-%m} a {dates.max():%Y-%m}"


def _save_fig(fig: plt.Figure, path: Path, caption: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.text(0.01, 0.005, caption, ha="left", va="bottom", fontsize=8, color="#555555")
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def _label_bars(ax: plt.Axes, fmt: str = "{:,.0f}") -> None:
    for patch in ax.patches:
        value = patch.get_width() if patch.get_width() >= patch.get_height() else patch.get_height()
        if not np.isfinite(value):
            continue
        if patch.get_width() >= patch.get_height():
            ax.text(
                patch.get_x() + patch.get_width(),
                patch.get_y() + patch.get_height() / 2,
                f" {fmt.format(value)}",
                va="center",
                fontsize=8,
            )
        else:
            ax.text(
                patch.get_x() + patch.get_width() / 2,
                patch.get_y() + patch.get_height(),
                f" {fmt.format(value)}",
                ha="center",
                va="bottom",
                fontsize=8,
            )


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def _context_charts(accidents: pd.DataFrame, panel: pd.DataFrame | None, output_dir: Path) -> list[dict]:
    generated: list[dict] = []
    df = accidents.copy()
    df["fecha_hora_accidente"] = pd.to_datetime(df["fecha_hora_accidente"], errors="coerce")
    df = df[df["fecha_hora_accidente"].notna()].copy()
    df["periodo"] = df["fecha_hora_accidente"].dt.to_period("M").astype(str)
    df["anio"] = df["fecha_hora_accidente"].dt.year
    df["mes_calendario"] = df["fecha_hora_accidente"].dt.month
    period = _period_range(df, "fecha_hora_accidente")
    source = f"Fuente: accidentes ART · {period} · n={len(df):,}"

    annual = df.groupby("anio").size()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    colors = ["#2f6fed"] * len(annual)
    if len(colors):
        colors[-1] = "#74a3ff"
    bars = ax.bar(annual.index.astype(str), annual.values, color=colors)
    if len(bars):
        bars[-1].set_hatch("//")
    ax.set_title("Accidentes denunciados por año")
    ax.set_xlabel("Año del accidente")
    ax.set_ylabel("Cantidad de accidentes")
    _label_bars(ax)
    path = output_dir / "contexto_accidentes_por_anio.png"
    _save_fig(fig, path, source + " · 2025 es parcial (hasta noviembre; barra tramada).")
    generated.append({"archivo": str(path), "proposito": "Contexto", "periodo": period})

    monthly = df.groupby("periodo").size()
    rolling = monthly.rolling(3, min_periods=1).mean()
    fig, ax = plt.subplots(figsize=(12, 4.8))
    x = np.arange(len(monthly))
    ax.plot(x, monthly.values, marker="o", markersize=3, linewidth=1, label="Accidentes del mes")
    ax.plot(x, rolling.values, linewidth=2, label="Promedio móvil 3 meses")
    tick_step = max(1, len(monthly) // 12)
    ax.set_xticks(x[::tick_step], monthly.index[::tick_step], rotation=45, ha="right")
    ax.set_title("Evolución mensual de accidentes denunciados")
    ax.set_xlabel("Mes del accidente")
    ax.set_ylabel("Cantidad de accidentes")
    ax.legend()
    ax.grid(alpha=0.25)
    path = output_dir / "contexto_accidentes_por_mes.png"
    _save_fig(fig, path, source + " · El último mes disponible puede estar incompleto.")
    generated.append({"archivo": str(path), "proposito": "Contexto", "periodo": period})

    if "forma_accidente" in df.columns:
        forms = df["forma_accidente"].fillna("Sin dato").value_counts().head(10).sort_values()
        pct = 100 * forms / len(df)
        labels = [textwrap.fill(str(v), 48) for v in forms.index]
        fig, ax = plt.subplots(figsize=(11, 6))
        ax.barh(labels, pct.values, color="#1f9d55")
        ax.set_title("Formas de accidente más frecuentes")
        ax.set_xlabel("Porcentaje de accidentes (%)")
        ax.set_ylabel("Forma del accidente")
        for i, (p, n) in enumerate(zip(pct.values, forms.values)):
            ax.text(p, i, f" {p:.1f}% (n={n:,})", va="center", fontsize=8)
        path = output_dir / "contexto_formas_accidente.png"
        _save_fig(fig, path, source + " · Describe mecanismos observados; no representa riesgo relativo.")
        generated.append({"archivo": str(path), "proposito": "Contexto", "periodo": period})

    if "dotacion_establecimiento" in df.columns:
        dot = pd.to_numeric(df["dotacion_establecimiento"], errors="coerce")
        labels = pd.Series("Sin dato", index=df.index, dtype="object")
        labels[dot.eq(0)] = "0 registrado"
        labels[dot.between(1, 5)] = "1–5"
        labels[dot.between(6, 10)] = "6–10"
        labels[dot.between(11, 50)] = "11–50"
        labels[dot.between(51, 200)] = "51–200"
        labels[dot.gt(200)] = "201+"
        order = ["Sin dato", "0 registrado", "1–5", "6–10", "11–50", "51–200", "201+"]
        counts = labels.value_counts().reindex(order, fill_value=0)
        fig, ax = plt.subplots(figsize=(9, 4.8))
        ax.bar(counts.index, counts.values, color=["#adb5bd", "#e8590c"] + ["#f08c00"] * 5)
        ax.set_title("Accidentes según dotación registrada del establecimiento")
        ax.set_xlabel("Dotación registrada")
        ax.set_ylabel("Cantidad de accidentes")
        ax.tick_params(axis="x", rotation=20)
        _label_bars(ax)
        path = output_dir / "contexto_dotacion_accidentes.png"
        _save_fig(
            fig,
            path,
            source
            + " · La unidad es accidente, no establecimiento único. “0 registrado” puede incluir fallas de cruce de nómina.",
        )
        generated.append({"archivo": str(path), "proposito": "Calidad/contexto", "periodo": period})

    if "edad_trabajador" in df.columns:
        age = pd.to_numeric(df["edad_trabajador"], errors="coerce")
        valid_age = age[age.between(16, 75)]
        fig, ax = plt.subplots(figsize=(9, 4.8))
        ax.hist(valid_age, bins=np.arange(15, 77, 3), color="#5c7cfa", edgecolor="white")
        if not valid_age.empty:
            median = float(valid_age.median())
            ax.axvline(median, color="#c92a2a", linestyle="--", label=f"Mediana: {median:.0f} años")
            ax.legend()
        ax.set_title("Edad de las personas accidentadas")
        ax.set_xlabel("Edad (años)")
        ax.set_ylabel("Cantidad de accidentes")
        path = output_dir / "contexto_edad_accidentados.png"
        _save_fig(
            fig,
            path,
            source
            + f" · Edades válidas 16–75: n={len(valid_age):,}; describe accidentados, no tasa de riesgo por edad.",
        )
        generated.append({"archivo": str(path), "proposito": "Contexto", "periodo": period})

    if "gravedad" in df.columns:
        gravity = df["gravedad"].fillna("Sin dato").value_counts().head(10).sort_values()
        pct = 100 * gravity / len(df)
        fig, ax = plt.subplots(figsize=(9, 5))
        ax.barh([textwrap.fill(str(v), 40) for v in gravity.index], pct.values, color="#e03131")
        ax.set_title("Gravedad registrada de las lesiones")
        ax.set_xlabel("Porcentaje de accidentes (%)")
        ax.set_ylabel("Gravedad")
        for i, (p, n) in enumerate(zip(pct.values, gravity.values)):
            ax.text(p, i, f" {p:.1f}% (n={n:,})", va="center", fontsize=8)
        path = output_dir / "contexto_gravedad_accidentes.png"
        _save_fig(fig, path, source + " · Variable posterior al accidente; no se usa para predecir.")
        generated.append({"archivo": str(path), "proposito": "Contexto", "periodo": period})

    # La provincia de ocurrencia trae nombres y mucha más cobertura que el ID del establecimiento.
    if "id_provincia_ocurrencia" in df.columns:
        province = df["id_provincia_ocurrencia"].fillna("Sin dato").astype(str).value_counts().head(12).sort_values()
        pct_missing = 100 * df["id_provincia_ocurrencia"].isna().mean()
        fig, ax = plt.subplots(figsize=(9, 5.5))
        ax.barh(province.index, province.values, color="#1098ad")
        ax.set_title("Accidentes por provincia de ocurrencia")
        ax.set_xlabel("Cantidad de accidentes")
        ax.set_ylabel("Provincia")
        _label_bars(ax)
        path = output_dir / "contexto_accidentes_por_provincia_ocurrencia.png"
        _save_fig(
            fig,
            path,
            source + f" · Se usa provincia de ocurrencia (nombre informado); faltantes: {pct_missing:.1f}%.",
        )
        generated.append({"archivo": str(path), "proposito": "Contexto", "periodo": period})

    if "actividad_ciiu_establecimiento" in df.columns:
        division = df["actividad_ciiu_establecimiento"].map(ciiu_division_label)
        counts = division.value_counts().head(12).sort_values()
        fig, ax = plt.subplots(figsize=(11, 6))
        ax.barh([textwrap.fill(v, 45) for v in counts.index], counts.values, color="#2b8a3e")
        ax.set_title("Accidentes por división CIIU Rev. 3")
        ax.set_xlabel("Cantidad de accidentes")
        ax.set_ylabel("División de actividad")
        _label_bars(ax)
        path = output_dir / "contexto_accidentes_por_division_ciiu.png"
        _save_fig(
            fig,
            path,
            source + " · Volumen absoluto: sectores grandes pueden concentrar más casos sin tener mayor tasa.",
        )
        generated.append({"archivo": str(path), "proposito": "Contexto", "periodo": period})

        seasonal = (
            df.assign(ciiu_division=division)
            .groupby(["ciiu_division", "mes_calendario"], observed=True)
            .size()
            .unstack(fill_value=0)
        )
        top_divisions = division.value_counts().head(10).index
        seasonal = seasonal.reindex(top_divisions).fillna(0)
        seasonal_pct = seasonal.div(seasonal.sum(axis=1).replace(0, np.nan), axis=0) * 100
        fig, ax = plt.subplots(figsize=(11, 6))
        sns.heatmap(seasonal_pct, cmap="YlOrRd", ax=ax, linewidths=0.2, cbar_kws={"label": "% del sector"})
        ax.set_title("Estacionalidad de accidentes dentro de cada división CIIU")
        ax.set_xlabel("Mes calendario")
        ax.set_ylabel("División CIIU Rev. 3")
        ax.set_xticklabels(["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"])
        path = output_dir / "contexto_estacionalidad_ciiu.png"
        _save_fig(
            fig,
            path,
            source + " · Cada fila suma 100%; permite comparar estacionalidad sin confundirla con tamaño del sector.",
        )
        generated.append({"archivo": str(path), "proposito": "Contexto", "periodo": period})

    if "id_empleador" in df.columns:
        employers = df["id_empleador"].value_counts()
        top = employers.head(15)
        cumulative = 100 * top.cumsum() / len(df)
        fig, ax = plt.subplots(figsize=(10, 5))
        x = np.arange(1, len(top) + 1)
        ax.bar(x, top.values, color="#495057", label="Accidentes")
        ax.set_xlabel("Empleadores ordenados por accidentes (ID anonimizado)")
        ax.set_ylabel("Cantidad de accidentes")
        ax.set_xticks(x)
        ax2 = ax.twinx()
        ax2.plot(x, cumulative.values, color="#c92a2a", marker="o", label="% acumulado")
        ax2.set_ylabel("Participación acumulada del total (%)")
        ax.set_title("Concentración de accidentes en los principales empleadores")
        lines, labels = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines + lines2, labels + labels2, loc="upper right")
        path = output_dir / "contexto_concentracion_empleadores.png"
        _save_fig(fig, path, source + " · Se muestra concentración; los identificadores permanecen anonimizados.")
        generated.append({"archivo": str(path), "proposito": "Contexto", "periodo": period})

    if panel is not None and {"visitas_realizadas_mes", "periodo"}.issubset(panel.columns):
        visits = panel.groupby("periodo").agg(
            registros_realizados=("visitas_realizadas_mes", "sum"),
            establecimientos=("visitas_realizadas_mes", lambda x: int((x > 0).sum())),
        )
        q1, q3 = visits["registros_realizados"].quantile([0.25, 0.75])
        limit = q3 + 3 * (q3 - q1)
        visits["anomalia"] = visits["registros_realizados"] > limit
        x = np.arange(len(visits))
        fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True, height_ratios=[1, 1.4])
        axes[0].plot(x, visits["registros_realizados"], color="#1971c2", marker="o", markersize=3)
        anomalies = visits[visits["anomalia"]]
        axes[0].scatter(
            [visits.index.get_loc(i) for i in anomalies.index],
            anomalies["registros_realizados"],
            color="#c92a2a",
            label="Carga atípica",
            zorder=4,
        )
        for label, row in anomalies.iterrows():
            axes[0].annotate(
                f"{label}: {int(row['registros_realizados']):,}",
                (visits.index.get_loc(label), row["registros_realizados"]),
                xytext=(4, 5),
                textcoords="offset points",
                fontsize=8,
            )
        axes[0].set_title("Registros de prevención por mes asignado en la fuente")
        axes[0].set_ylabel("Registros")
        axes[0].legend()
        typical = visits["registros_realizados"].mask(visits["anomalia"])
        axes[1].plot(x, typical, color="#1971c2", marker="o", markersize=3, label="Visitas registradas")
        axes[1].plot(
            x,
            visits["establecimientos"].mask(visits["anomalia"]),
            color="#2f9e44",
            linestyle="--",
            label="Establecimientos con ≥1 registro",
        )
        axes[1].set_ylabel("Cantidad (sin cargas atípicas)")
        axes[1].set_xlabel("Mes asignado")
        axes[1].legend()
        step = max(1, len(visits) // 12)
        axes[1].set_xticks(x[::step], visits.index[::step], rotation=45, ha="right")
        path = output_dir / "contexto_prevencion_y_anomalias.png"
        _save_fig(
            fig,
            path,
            "Fuente: panel ART 2022–2025 · La vista vigente agrupa realizadas por FechaHoraVisita "
            "(fecha planificada), no por FechaHoraRealizada. Los picos se tratan como cargas masivas.",
        )
        generated.append({"archivo": str(path), "proposito": "Calidad/contexto", "periodo": "2022–2025"})

        _write_json(
            output_dir / "contexto_prevencion_anomalias.json",
            {
                "criterio": "Q3 + 3×IQR sobre registros realizados por mes asignado",
                "limit": float(limit),
                "anomalias": anomalies.reset_index().to_dict(orient="records"),
                "limitacion": (
                    "visitas_realizadas_mes está agrupada por FechaHoraVisita en la exportación vigente; "
                    "para actividad operativa real debe reagruparse por FechaHoraRealizada."
                ),
            },
        )

    return generated


def _capitas_band(values: pd.Series) -> pd.Series:
    capitas = pd.to_numeric(values, errors="coerce")
    result = pd.Series("Sin dato/0", index=values.index, dtype="object")
    result[capitas.between(1, 10)] = "1–10"
    result[capitas.between(11, 50)] = "11–50"
    result[capitas.between(51, 200)] = "51–200"
    result[capitas.gt(200)] = "201+"
    return result


def _training_charts(panel: pd.DataFrame, output_dir: Path) -> tuple[list[dict], dict]:
    generated: list[dict] = []
    train = panel[panel["anio"].isin(TRAIN_YEARS)].copy()
    if train.empty:
        return generated, {}
    train["periodo"] = train["periodo"].astype(str)
    period = f"{min(TRAIN_YEARS)}–{max(TRAIN_YEARS)}"
    targets = {
        "1 mes": TARGET_COLUMN_1M,
        "3 meses": TARGET_COLUMN_3M,
    }

    monthly_rows: list[pd.DataFrame] = []
    for label, target in targets.items():
        valid = train[train[target].notna()]
        agg = valid.groupby("periodo")[target].agg(filas="size", positivos="sum")
        agg["tasa_pct"] = 100 * agg["positivos"] / agg["filas"]
        agg["horizonte"] = label
        monthly_rows.append(agg.reset_index())
    monthly = pd.concat(monthly_rows, ignore_index=True)

    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    for label, group in monthly.groupby("horizonte", sort=False):
        axes[0].plot(group["periodo"], group["positivos"], marker="o", markersize=3, label=label)
        axes[1].plot(group["periodo"], group["tasa_pct"], marker="o", markersize=3, label=label)
    axes[0].set_title("Targets positivos en los datos de entrenamiento")
    axes[0].set_ylabel("Establecimiento-mes positivos")
    axes[0].legend(title="Horizonte")
    axes[1].set_ylabel("Tasa positiva (%)")
    axes[1].set_xlabel("Mes de features")
    axes[1].legend(title="Horizonte")
    for ax in axes:
        ax.tick_params(axis="x", rotation=45)
        ax.grid(alpha=0.25)
    path = output_dir / "entrenamiento_targets_por_mes.png"
    _save_fig(
        fig,
        path,
        f"Fuente: panel establecimiento×mes · entrenamiento {period} · 35.505 establecimientos por mes.",
    )
    generated.append({"archivo": str(path), "proposito": "Entrenamiento", "periodo": period})

    if "dotacion_nomina_mes" in train.columns:
        positive = pd.to_numeric(train["dotacion_nomina_mes"], errors="coerce").gt(0)
        coverage = train.assign(_positive=positive).groupby("periodo")["_positive"].mean() * 100
        fig, ax = plt.subplots(figsize=(11, 4.5))
        ax.plot(coverage.index, coverage.values, color="#099268", marker="o", markersize=3)
        ax.set_title("Filas de entrenamiento con dotación nominal positiva")
        ax.set_xlabel("Mes de features")
        ax.set_ylabel("Filas con dotación > 0 (%)")
        ax.tick_params(axis="x", rotation=45)
        ax.grid(alpha=0.25)
        path = output_dir / "entrenamiento_dotacion_nomina_positiva.png"
        _save_fig(
            fig,
            path,
            f"Fuente: panel {period} · Cero puede significar dotación cero o ausencia de cruce; no se denomina cobertura.",
        )
        generated.append({"archivo": str(path), "proposito": "Entrenamiento/calidad", "periodo": period})

    if "cantidad_capitas" in train.columns:
        train["tramo_capitas"] = _capitas_band(train["cantidad_capitas"])
        order = ["1–10", "11–50", "51–200", "201+", "Sin dato/0"]
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), sharey=False)
        for ax, (label, target) in zip(axes, targets.items()):
            valid = train[train[target].notna()]
            stats = valid.groupby("tramo_capitas", observed=True)[target].agg(tasa="mean", n="size").reindex(order)
            values = 100 * stats["tasa"]
            ax.bar(values.index, values.values, color="#364fc7")
            ax.set_title(f"Target a {label}")
            ax.set_xlabel("Cápitas declaradas")
            ax.set_ylabel("Tasa positiva (%)")
            ax.tick_params(axis="x", rotation=20)
            for i, (value, n) in enumerate(zip(values.values, stats["n"].fillna(0).values)):
                if np.isfinite(value):
                    ax.text(i, value, f"{value:.2f}%\nn={int(n):,}", ha="center", va="bottom", fontsize=8)
        fig.suptitle("Tasa observada en entrenamiento por tamaño del empleador")
        path = output_dir / "entrenamiento_tasa_por_capitas.png"
        _save_fig(
            fig,
            path,
            f"Fuente: panel {period} · Asociación descriptiva; cápitas es un proxy estático y no implica causalidad.",
        )
        generated.append({"archivo": str(path), "proposito": "Entrenamiento", "periodo": period})

    if "visitas_realizadas_mes" in train.columns:
        visits = train.groupby("periodo").agg(
            registros=("visitas_realizadas_mes", "sum"),
            establecimientos=("visitas_realizadas_mes", lambda x: int((x > 0).sum())),
        )
        fig, ax = plt.subplots(figsize=(11, 4.5))
        ax.plot(visits.index, visits["registros"], marker="o", label="Registros realizados")
        ax.plot(visits.index, visits["establecimientos"], linestyle="--", label="Establecimientos con ≥1")
        ax.set_title("Prevención presente en los datos de entrenamiento")
        ax.set_xlabel("Mes asignado en la fuente")
        ax.set_ylabel("Cantidad")
        ax.tick_params(axis="x", rotation=45)
        ax.legend()
        ax.grid(alpha=0.25)
        path = output_dir / "entrenamiento_prevencion_por_mes.png"
        _save_fig(
            fig,
            path,
            f"Fuente: panel {period} · Registros realizados agrupados por mes planificado en la exportación vigente.",
        )
        generated.append({"archivo": str(path), "proposito": "Entrenamiento", "periodo": period})

    summary = {
        "periodo": period,
        "filas": int(len(train)),
        "establecimientos_unicos": int(train["id_establecimiento"].nunique()),
        "meses": int(train["periodo"].nunique()),
        "targets": {
            label: {
                "columna": target,
                "filas_evaluables": int(train[target].notna().sum()),
                "positivos": int(train[target].sum(skipna=True)),
                "tasa_positiva": float(train[target].mean()),
            }
            for label, target in targets.items()
        },
        "dotacion_nomina_positiva_pct": (
            float(100 * pd.to_numeric(train["dotacion_nomina_mes"], errors="coerce").gt(0).mean())
            if "dotacion_nomina_mes" in train.columns
            else None
        ),
        "nota": "Este es el subconjunto que ajusta los parámetros del modelo. 2024 calibra el umbral y 2025 evalúa.",
    }
    _write_json(output_dir / "entrenamiento_resumen.json", summary)
    return generated, summary


def _monthly_topk(scored: pd.DataFrame, target: str, k: int) -> pd.DataFrame:
    rows = []
    for period, group in scored.groupby("periodo", sort=True):
        valid = group[group[target].notna()]
        if valid.empty:
            continue
        top = valid.nlargest(min(k, len(valid)), "score_riesgo")
        rows.append(
            {
                "periodo": str(period),
                "seleccionados": int(len(top)),
                "positivos": int(top[target].sum()),
                "precision": float(top[target].mean()),
                "positivos_totales": int(valid[target].sum()),
            }
        )
    return pd.DataFrame(rows)


def _condition_metrics(
    scored: pd.DataFrame,
    panel: pd.DataFrame,
    target: str,
    k: int,
    periods: set[str] | None = None,
) -> dict[str, list[dict]]:
    feature_cols = [
        "id_establecimiento",
        "periodo",
        "accidentes_total_previos",
        "cantidad_capitas",
        "dotacion_nomina_mes",
        "actividad_ciiu_establecimiento",
    ]
    merged = scored.merge(panel[feature_cols], on=["id_establecimiento", "periodo"], how="left")
    if periods:
        merged = merged[merged["periodo"].isin(periods)].copy()
    merged["historial"] = np.where(
        pd.to_numeric(merged["accidentes_total_previos"], errors="coerce").fillna(0).gt(0),
        "Con accidentes previos",
        "Sin accidentes previos",
    )
    merged["nomina"] = np.where(
        pd.to_numeric(merged["dotacion_nomina_mes"], errors="coerce").fillna(0).gt(0),
        "Dotación nominal > 0",
        "Dotación nominal = 0",
    )
    merged["capitas"] = _capitas_band(merged["cantidad_capitas"])
    merged["actividad"] = merged["actividad_ciiu_establecimiento"].map(ciiu_division_label)

    selected_parts = []
    for _, group in merged.groupby("periodo", sort=True):
        valid = group[group[target].notna()]
        if valid.empty:
            continue
        selected_parts.append(valid.nlargest(min(k, len(valid)), "score_riesgo"))
    selected = pd.concat(selected_parts, ignore_index=True) if selected_parts else merged.iloc[0:0]

    result: dict[str, list[dict]] = {}
    for column in ("historial", "nomina", "capitas", "actividad"):
        base = merged.groupby(column, dropna=False)[target].agg(base_rate="mean", universo="size")
        chosen = selected.groupby(column, dropna=False)[target].agg(precision="mean", seleccionados="size", positivos="sum")
        stats = chosen.join(base, how="left")
        stats["lift"] = stats["precision"] / stats["base_rate"].replace(0, np.nan)
        stats = stats.reset_index().rename(columns={column: "condicion"})
        if column == "actividad":
            stats = stats[stats["seleccionados"] >= 50].nlargest(10, "seleccionados")
        result[column] = stats.to_dict(orient="records")
    return result


def _plot_conditions(
    metrics: dict[str, list[dict]],
    path: Path,
    horizon: str,
    k: int,
    cadence: str,
) -> None:
    groups = [
        ("historial", "Historial de accidentes"),
        ("nomina", "Dotación nominal"),
        ("capitas", "Tamaño por cápitas"),
        ("actividad", "Divisiones CIIU con más seleccionados"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    for ax, (key, title) in zip(axes.flat, groups):
        data = pd.DataFrame(metrics.get(key, []))
        if data.empty:
            ax.set_visible(False)
            continue
        data = data.sort_values("precision")
        labels = [textwrap.fill(str(v), 36) for v in data["condicion"]]
        values = 100 * data["precision"]
        ax.barh(labels, values, color="#1971c2")
        ax.set_title(title)
        ax.set_xlabel(f"Precisión dentro del top-{k} global (%)")
        for i, (value, n) in enumerate(zip(values, data["seleccionados"])):
            ax.text(value, i, f" {value:.1f}% · n={int(n):,}", va="center", fontsize=8)
        ax.set_xlim(0, min(100, max(10, float(values.max()) * 1.35)))
    fig.suptitle(f"Desempeño del ranking {horizon} por condición — holdout {HOLDOUT_YEAR}")
    _save_fig(
        fig,
        path,
        f"Fuente: scored holdout {HOLDOUT_YEAR} + panel · Selección top-{k} global {cadence}; "
        "la precisión de subgrupos pequeños debe interpretarse con cautela.",
    )


def _holdout_charts(panel: pd.DataFrame, output_dir: Path) -> tuple[list[dict], dict]:
    generated: list[dict] = []
    summary: dict = {"holdout_year": HOLDOUT_YEAR, "horizons": {}}

    for horizon, target in (("1m", TARGET_COLUMN_1M), ("3m", TARGET_COLUMN_3M)):
        scored_path = REPORTS_RANKING_DIR / f"scored_panel_holdout_{HOLDOUT_YEAR}_{horizon}.csv"
        if not scored_path.exists():
            continue
        scored = pd.read_csv(scored_path, sep=";")
        scored["periodo"] = scored["periodo"].astype(str)
        scored[target] = pd.to_numeric(scored[target], errors="coerce")

        monthly_50 = _monthly_topk(scored, target, CAPACITY_CRITICAL)
        monthly_225 = _monthly_topk(scored, target, CAPACITY_MONTHLY)
        fig, ax = plt.subplots(figsize=(10.5, 4.8))
        ax.plot(
            monthly_50["periodo"],
            100 * monthly_50["precision"],
            marker="o",
            label=f"Top-{CAPACITY_CRITICAL} (críticos)",
        )
        ax.plot(
            monthly_225["periodo"],
            100 * monthly_225["precision"],
            marker="s",
            label=f"Top-{CAPACITY_MONTHLY} (capacidad mensual)",
        )
        ax.axhline(
            100 * monthly_50["precision"].mean(),
            color="#1971c2",
            linestyle=":",
            alpha=0.7,
            label=f"Media top-{CAPACITY_CRITICAL}: {monthly_50['precision'].mean():.1%}",
        )
        ax.axhline(
            100 * monthly_225["precision"].mean(),
            color="#e8590c",
            linestyle=":",
            alpha=0.7,
            label=f"Media top-{CAPACITY_MONTHLY}: {monthly_225['precision'].mean():.1%}",
        )
        ax.set_ylim(0, 100)
        ax.set_title(f"Precisión operativa mensual — horizonte {horizon}, holdout {HOLDOUT_YEAR}")
        ax.set_xlabel("Mes de features")
        ax.set_ylabel("Establecimientos seleccionados con accidente (%)")
        ax.tick_params(axis="x", rotation=45)
        ax.legend(fontsize=8, ncols=2)
        ax.grid(alpha=0.25)
        path = output_dir / f"holdout_{HOLDOUT_YEAR}_precision_mensual_{horizon}.png"
        _save_fig(
            fig,
            path,
            f"Fuente: scored holdout {HOLDOUT_YEAR} {horizon} · "
            f"top-{CAPACITY_CRITICAL} y top-{CAPACITY_MONTHLY} recalculados dentro de cada mes.",
        )
        generated.append({"archivo": str(path), "proposito": "Desempeño holdout", "periodo": str(HOLDOUT_YEAR)})

        fig, ax = plt.subplots(figsize=(9, 4.8))
        negatives = scored.loc[scored[target] == 0, "score_riesgo"]
        positives = scored.loc[scored[target] == 1, "score_riesgo"]
        bins = np.linspace(0, 1, 41)
        ax.hist(negatives, bins=bins, density=True, alpha=0.55, label="Sin accidente", color="#74c0fc")
        ax.hist(positives, bins=bins, density=True, alpha=0.55, label="Con accidente", color="#ff6b6b")
        ax.set_title(f"Distribución del score — horizonte {horizon}, holdout {HOLDOUT_YEAR}")
        ax.set_xlabel("Score de prioridad (no interpretar como probabilidad calibrada)")
        ax.set_ylabel("Densidad dentro de cada clase")
        ax.legend()
        path = output_dir / f"holdout_{HOLDOUT_YEAR}_score_{horizon}.png"
        _save_fig(
            fig,
            path,
            f"Fuente: scored holdout {HOLDOUT_YEAR} {horizon} · "
            f"positivos={int((scored[target] == 1).sum()):,}; negativos={int((scored[target] == 0).sum()):,}.",
        )
        generated.append({"archivo": str(path), "proposito": "Desempeño holdout", "periodo": str(HOLDOUT_YEAR)})

        condition_k = CAPACITY_MONTHLY
        condition_periods: set[str] | None = None
        cadence = "de cada mes"
        quarterly_summary = None
        if horizon == "3m":
            quarter_path = REPORTS_RANKING_DIR / "top_k_per_quarter_3m.json"
            if quarter_path.exists():
                quarter_data = json.loads(quarter_path.read_text(encoding="utf-8"))
                quarters = pd.DataFrame(quarter_data.get("quarters", []))
                if not quarters.empty:
                    condition_k = CAPACITY_QUARTERLY
                    condition_periods = set(quarters["cutoff"].astype(str))
                    cadence = "de cada corte trimestral evaluable"
                    fig, ax = plt.subplots(figsize=(8, 4.8))
                    x = np.arange(len(quarters))
                    width = 0.36
                    ax.bar(
                        x - width / 2,
                        100 * quarters["precision_at_150"],
                        width,
                        label="Top-150 crítico trimestral",
                    )
                    ax.bar(
                        x + width / 2,
                        100 * quarters["precision_at_675"],
                        width,
                        label="Top-675 capacidad trimestral",
                    )
                    ax.set_xticks(x, quarters["cutoff"])
                    ax.set_ylim(0, 100)
                    ax.set_title(
                        f"Precisión en cortes trimestrales — 3m, holdout {HOLDOUT_YEAR}",
                        pad=42,
                    )
                    ax.set_xlabel("Mes de corte")
                    ax.set_ylabel("Precisión (%)")
                    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncols=2)
                    for container in ax.containers:
                        ax.bar_label(container, fmt="%.1f%%", fontsize=8)
                    path = output_dir / f"holdout_{HOLDOUT_YEAR}_precision_trimestral_3m.png"
                    _save_fig(
                        fig,
                        path,
                        "Fuente: top_k_per_quarter_3m.json · Cortes no solapados evaluables: marzo y junio; "
                        "septiembre no se evalúa porque faltan tres meses futuros completos.",
                    )
                    generated.append(
                        {"archivo": str(path), "proposito": "Desempeño holdout", "periodo": str(HOLDOUT_YEAR)}
                    )
                    quarterly_summary = quarter_data.get("summary")

        conditions = _condition_metrics(
            scored,
            panel,
            target,
            condition_k,
            periods=condition_periods,
        )
        path = output_dir / f"holdout_{HOLDOUT_YEAR}_precision_por_condicion_{horizon}.png"
        _plot_conditions(conditions, path, horizon, condition_k, cadence)
        generated.append({"archivo": str(path), "proposito": "Desempeño holdout", "periodo": str(HOLDOUT_YEAR)})

        metrics_path = REPORTS_MODEL_DIR / f"evaluation_metrics_{horizon}.json"
        calibration = {}
        if metrics_path.exists():
            metrics_json = json.loads(metrics_path.read_text(encoding="utf-8"))
            calibration = metrics_json.get("calibration", {})
            reliability = calibration.get("reliability", [])
            if reliability:
                cal = pd.DataFrame(reliability)
                fig, ax = plt.subplots(figsize=(6, 5))
                ax.plot([0, 1], [0, 1], linestyle="--", color="#868e96", label="Calibración perfecta")
                ax.plot(
                    cal["mean_predicted"],
                    cal["fraction_positive"],
                    marker="o",
                    color="#7048e8",
                    label="Modelo",
                )
                ax.set_title(f"Calibración del score — {horizon}, holdout {HOLDOUT_YEAR}")
                ax.set_xlabel("Score medio predicho")
                ax.set_ylabel("Frecuencia observada de accidente")
                ax.legend()
                ax.grid(alpha=0.25)
                path = output_dir / f"holdout_{HOLDOUT_YEAR}_calibracion_{horizon}.png"
                _save_fig(
                    fig,
                    path,
                    f"Fuente: evaluation_metrics_{horizon}.json · Brier={calibration.get('brier_score', float('nan')):.4f}. "
                    "El score se usa para ordenar prioridad, no como probabilidad comunicable.",
                )
                generated.append(
                    {"archivo": str(path), "proposito": "Desempeño holdout", "periodo": str(HOLDOUT_YEAR)}
                )

        summary["horizons"][horizon] = {
            "target": target,
            "filas": int(len(scored)),
            "positivos": int(scored[target].sum()),
            "meses": int(scored["periodo"].nunique()),
            f"precision_media_top_{CAPACITY_CRITICAL}": float(monthly_50["precision"].mean()),
            f"precision_media_top_{CAPACITY_MONTHLY}": float(monthly_225["precision"].mean()),
            f"condiciones_top_{condition_k}": conditions,
            "cortes_condiciones": sorted(condition_periods) if condition_periods else "todos los meses",
            "precision_trimestral": quarterly_summary,
            "calibration": calibration,
        }

    baseline_by_horizon: dict[str, dict] = {}
    for horizon in ("1m", "3m"):
        baseline_path = REPORTS_MODEL_DIR / f"baseline_comparison_{horizon}.json"
        if not baseline_path.exists():
            continue
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        values = baseline.get("summary", {})
        baseline_by_horizon[horizon] = {"k": int(baseline.get("k", 0)), "summary": values}
    if baseline_by_horizon:
        fig, axes = plt.subplots(1, len(baseline_by_horizon), figsize=(12, 5), sharey=True)
        if len(baseline_by_horizon) == 1:
            axes = [axes]
        for ax, (horizon, baseline) in zip(axes, baseline_by_horizon.items()):
            values = baseline["summary"]
            labels, precision = [], []
            for key, label in (
                ("mean_modelo_precision", "Modelo"),
                ("mean_historial_precision", "Historial"),
                ("mean_visitas_precision", "Visitas registradas"),
                ("mean_azar_precision", "Azar"),
            ):
                if values.get(key) is not None:
                    labels.append(label)
                    precision.append(100 * values[key])
            bars = ax.bar(labels, precision, color=["#1971c2", "#495057", "#2f9e44", "#adb5bd"])
            ax.set_title(f"{horizon} · K={baseline['k']} por mes")
            ax.set_xlabel("Estrategia")
            ax.tick_params(axis="x", rotation=20)
            ax.bar_label(bars, fmt="%.1f%%", fontsize=8)
        axes[0].set_ylabel("Precisión media mensual (%)")
        fig.suptitle(f"Comparación de focalización a igual capacidad dentro de cada horizonte — {HOLDOUT_YEAR}")
        path = output_dir / f"holdout_{HOLDOUT_YEAR}_comparacion_estrategias.png"
        _save_fig(
            fig,
            path,
            "Fuente: baseline_comparison_1m/3m · 1m usa K=225; 3m usa K=675. "
            "Comparación de focalización, no estimación causal del efecto de las visitas.",
        )
        generated.append({"archivo": str(path), "proposito": "Desempeño holdout", "periodo": str(HOLDOUT_YEAR)})

    _write_json(output_dir / f"holdout_{HOLDOUT_YEAR}_resumen.json", summary)
    return generated, summary


def run_dataset_reports(
    accidents: pd.DataFrame,
    panel: pd.DataFrame | None = None,
    output_dir: Path | None = None,
) -> dict:
    """Genera reportes sin mezclar contexto, entrenamiento y evaluación."""
    ensure_dirs()
    base_dir = Path(output_dir or REPORTS_DATASET_DIR)
    if base_dir.resolve() == REPORTS_DATASET_DIR.resolve():
        context_dir = REPORTS_CONTEXT_DIR
        train_dir = REPORTS_TRAIN_DIR
        holdout_dir = REPORTS_HOLDOUT_DIR
    else:
        context_dir = base_dir / "contexto_2022_2025"
        train_dir = base_dir / "entrenamiento_2022_2023"
        holdout_dir = base_dir / "desempeno_holdout_2025"
    for directory in (base_dir, context_dir, train_dir, holdout_dir):
        directory.mkdir(parents=True, exist_ok=True)

    sns.set_theme(style="whitegrid")
    generated = _context_charts(accidents, panel, context_dir)
    training_summary: dict = {}
    holdout_summary: dict = {}
    if panel is not None and not panel.empty:
        training_files, training_summary = _training_charts(panel, train_dir)
        holdout_files, holdout_summary = _holdout_charts(panel, holdout_dir)
        generated.extend(training_files)
        generated.extend(holdout_files)

    index = {
        "criterio": {
            "contexto": "2022–2025 para describir el problema; 2025 puede estar incompleto.",
            "entrenamiento": "Solo 2022–2023: datos que ajustan los parámetros del modelo.",
            "calibracion": "2024 calibra el umbral; no se presenta como desempeño final.",
            "holdout": "Solo 2025: evaluación fuera de muestra.",
        },
        "graficos": generated,
        "resumen_entrenamiento": training_summary,
        "resumen_holdout": holdout_summary,
        "advertencias": [
            "Volumen absoluto no equivale a riesgo: usar tasas cuando exista denominador.",
            "Dotación cero puede mezclar un cero real con ausencia de cruce.",
            "Prevención vigente agrupa realizadas por fecha planificada; los picos de enero son cargas masivas.",
            "El score ordena prioridad y no debe presentarse como probabilidad calibrada.",
        ],
    }
    index_path = base_dir / "reports_chart_index.json"
    _write_json(index_path, index)
    return {
        "output_dir": str(base_dir),
        "contexto_dir": str(context_dir),
        "entrenamiento_dir": str(train_dir),
        "holdout_dir": str(holdout_dir),
        "graficos_generados": len(generated),
        "indice": str(index_path),
    }
