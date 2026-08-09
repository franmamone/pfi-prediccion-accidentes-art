"""Genera figuras PNG de la encuesta de user research (hito 50%).

Lee el Excel de respuestas de Google Forms, elimina filas duplicadas exactas
y escribe gráficos en docs/figures/encuesta/.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "figures" / "encuesta"
DEFAULT_XLSX = Path(
    r"c:\Users\FranciscoDanteMamone\Documents\UADE\Tesis\50%"
    r"\Encuesta sobre Prevención y Seguridad Laboral  (Respuestas).xlsx"
)

COLORS = {
    "primary": "#1d4ed8",
    "secondary": "#0f766e",
    "accent": "#b45309",
    "muted": "#64748b",
    "soft": "#94a3b8",
    "danger": "#b91c1c",
    "ok": "#15803d",
    "bg": "#f8fafc",
    "bar": ["#1d4ed8", "#0f766e", "#b45309", "#475569", "#0369a1", "#a16207"],
}

COL_SECTOR = "¿En qué sector trabajas actualmente?"
COL_SIZE = "¿Cuál es el tamaño aproximado de la empresa o establecimiento en el que trabajas?"
COL_ART = (
    "¿Sabes qué Aseguradora de Riesgos del Trabajo (ART) tiene tu empresa "
    "y si realizan auditorías preventivas en tu lugar de trabajo?"
)
COL_CAP = (
    "En tu experiencia, las capacitaciones o medidas de seguridad en tu empresa "
    "se implementan principalmente..."
)
COL_LIKERT = (
    "Del 1 al 5, ¿qué tan preparada creés que está tu empresa para anticiparse "
    "a un accidente laboral antes de que ocurra?"
)
COL_ACC = (
    "¿Alguna vez vos o un compañero de tu sector sufrieron un accidente laboral "
    "o enfermedad profesional en tu trabajo actual?"
)
COL_CHANGE = (
    'Si respondiste "Sí" a la pregunta anterior, ¿notaste que la empresa o la ART '
    "implementaran cambios operativos profundos para evitar que vuelva a suceder?"
)

SECTOR_CANON = {
    "Comercio / Oficinas / Tecnología": "Comercio / oficinas / tecnología",
    "Salud / Educación": "Salud / educación",
    "Construcción": "Construcción",
    "Industria / Manufactura / Logística": "Industria / manufactura / logística",
    "Agro / Minería / Petróleo": "Agro / minería / petróleo",
}

SIZE_ORDER = [
    "Menos de 10 empleados (Microempresa)",
    "Entre 10 y 50 empleados (Pequeña empresa)",
    "Entre 51 y 200 empleados (Mediana empresa)",
    "Más de 200 empleados (Gran empresa / Multinacional)",
]
SIZE_LABELS = {
    "Menos de 10 empleados (Microempresa)": "Micro (<10)",
    "Entre 10 y 50 empleados (Pequeña empresa)": "Pequeña (10–50)",
    "Entre 51 y 200 empleados (Mediana empresa)": "Mediana (51–200)",
    "Más de 200 empleados (Gran empresa / Multinacional)": "Grande (>200)",
}

ART_ORDER = [
    "No tengo idea qué ART me cubre ni si hacen prevención.",
    "Sé cuál es la ART, pero nunca vi que hicieran auditorías o inspecciones.",
    "Sí, sé cuál es y vienen a auditar de forma regular.",
]
ART_LABELS = {
    ART_ORDER[0]: "No conoce ART\nni prevención",
    ART_ORDER[1]: "Conoce ART,\nsin auditorías visibles",
    ART_ORDER[2]: "Conoce ART y\nauditorías regulares",
}

CAP_ORDER = [
    "Solo de forma reactiva, después de que ocurre un incidente o accidente",
    "Solo al momento de ingresar a la empresa (inducción)",
    "De forma proactiva y planificada durante todo el año",
]
CAP_LABELS = {
    CAP_ORDER[0]: "Reactiva\n(post-incidente)",
    CAP_ORDER[1]: "Solo inducción\nde ingreso",
    CAP_ORDER[2]: "Proactiva\ny planificada",
}

CHANGE_ORDER = [
    "No, todo siguió exactamente igual",
    "Se tomaron medidas mínimas (ej. una charla o poner un cartel)",
    "Sí, se rediseñaron los procesos y mejoró la seguridad",
]
CHANGE_LABELS = {
    CHANGE_ORDER[0]: "Sin cambios",
    CHANGE_ORDER[1]: "Medidas mínimas",
    CHANGE_ORDER[2]: "Rediseño / mejora\nprofunda",
}


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": COLORS["bg"],
            "axes.edgecolor": "#cbd5e1",
            "axes.labelcolor": "#0f172a",
            "text.color": "#0f172a",
            "xtick.color": "#334155",
            "ytick.color": "#334155",
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.titlesize": 13,
            "axes.titleweight": "semibold",
            "axes.grid": False,
        }
    )


def load(path: Path) -> pd.DataFrame:
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    before = len(df)
    df = df.drop_duplicates()
    print(f"Filas: {before} → {len(df)} tras eliminar duplicados exactas")
    return df


def _annotate_bars(ax, bars, total: int, horizontal: bool = False) -> None:
    for bar in bars:
        if horizontal:
            w = bar.get_width()
            if w <= 0:
                continue
            pct = 100.0 * w / total
            ax.text(
                w + max(total * 0.01, 0.3),
                bar.get_y() + bar.get_height() / 2,
                f"{int(w)} ({pct:.0f}%)",
                va="center",
                ha="left",
                fontsize=10,
                color="#0f172a",
            )
        else:
            h = bar.get_height()
            if h <= 0:
                continue
            pct = 100.0 * h / total
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                h + max(total * 0.015, 0.2),
                f"{int(h)}\n({pct:.0f}%)",
                ha="center",
                va="bottom",
                fontsize=9.5,
                color="#0f172a",
            )


def bar_counts(
    labels: list[str],
    counts: list[int],
    title: str,
    outfile: Path,
    *,
    horizontal: bool = False,
    colors: list[str] | None = None,
) -> None:
    total = sum(counts) or 1
    palette = colors or (COLORS["bar"] * ((len(labels) // len(COLORS["bar"])) + 1))[: len(labels)]
    fig_w = 8.2 if not horizontal else 8.6
    fig_h = 4.8 if not horizontal else max(3.8, 0.55 * len(labels) + 1.5)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    if horizontal:
        y = np.arange(len(labels))
        bars = ax.barh(y, counts, color=palette, height=0.62, edgecolor="white", linewidth=0.8)
        ax.set_yticks(y)
        ax.set_yticklabels(labels)
        ax.invert_yaxis()
        ax.set_xlabel("Respuestas")
        ax.set_xlim(0, max(counts) * 1.28 if counts else 1)
        _annotate_bars(ax, bars, total, horizontal=True)
    else:
        x = np.arange(len(labels))
        bars = ax.bar(x, counts, color=palette, width=0.68, edgecolor="white", linewidth=0.8)
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_ylabel("Respuestas")
        ax.set_ylim(0, max(counts) * 1.28 if counts else 1)
        _annotate_bars(ax, bars, total, horizontal=False)
    ax.set_title(title)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    fig.text(0.99, 0.01, f"n = {total}", ha="right", va="bottom", fontsize=9, color=COLORS["muted"])
    fig.tight_layout()
    outfile.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outfile, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("wrote", outfile.relative_to(REPO))


def donut(labels: list[str], counts: list[int], title: str, outfile: Path, colors: list[str]) -> None:
    total = sum(counts) or 1
    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    wedges, *_ = ax.pie(
        counts,
        colors=colors,
        startangle=90,
        wedgeprops=dict(width=0.42, edgecolor="white", linewidth=1.5),
    )
    ax.set_title(title)
    legend = [f"{lab}: {c} ({100 * c / total:.0f}%)" for lab, c in zip(labels, counts)]
    ax.legend(wedges, legend, loc="center left", bbox_to_anchor=(1.02, 0.5), frameon=False, fontsize=10)
    ax.text(0, 0, f"n = {total}", ha="center", va="center", fontsize=12, fontweight="semibold")
    fig.tight_layout()
    outfile.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outfile, dpi=180, bbox_inches="tight")
    plt.close(fig)
    print("wrote", outfile.relative_to(REPO))


def sector_series(df: pd.DataFrame) -> tuple[list[str], list[int]]:
    s = df[COL_SECTOR].astype(str).str.strip()
    mapped = s.map(lambda x: SECTOR_CANON.get(x, "Otros"))
    vc = mapped.value_counts()
    order = list(SECTOR_CANON.values()) + ["Otros"]
    labels = [k for k in order if k in vc.index]
    counts = [int(vc[k]) for k in labels]
    return labels, counts


def size_series(df: pd.DataFrame) -> tuple[list[str], list[int]]:
    s = df[COL_SIZE]
    labels, counts = [], []
    for key in SIZE_ORDER:
        n = int((s == key).sum())
        if n:
            labels.append(SIZE_LABELS[key])
            counts.append(n)
    n_na = int(s.isna().sum())
    if n_na:
        labels.append("Sin dato")
        counts.append(n_na)
    return labels, counts


def ordered_series(
    series: pd.Series, order: list[str], labels_map: dict[str, str]
) -> tuple[list[str], list[int]]:
    labels, counts = [], []
    for key in order:
        n = int((series == key).sum())
        labels.append(labels_map[key])
        counts.append(n)
    return labels, counts


def main() -> None:
    _style()
    xlsx = DEFAULT_XLSX
    if not xlsx.exists():
        raise SystemExit(f"No se encontró el Excel: {xlsx}")
    df = load(xlsx)

    lab, cnt = sector_series(df)
    bar_counts(
        lab,
        cnt,
        "P1. Sector laboral de los encuestados",
        OUT / "p1_sector.png",
        horizontal=True,
        colors=[
            COLORS["primary"],
            COLORS["secondary"],
            COLORS["accent"],
            "#475569",
            "#0369a1",
            COLORS["soft"],
        ],
    )

    lab, cnt = size_series(df)
    bar_counts(
        lab,
        cnt,
        "P2. Tamaño del establecimiento / empresa",
        OUT / "p2_tamanio.png",
        colors=[COLORS["secondary"], COLORS["primary"], COLORS["accent"], "#475569", COLORS["soft"]],
    )

    lab, cnt = ordered_series(df[COL_ART], ART_ORDER, ART_LABELS)
    bar_counts(
        lab,
        cnt,
        "P3. Conocimiento de la ART y visibilidad de auditorías",
        OUT / "p3_art.png",
        colors=[COLORS["danger"], COLORS["accent"], COLORS["ok"]],
    )

    lab, cnt = ordered_series(df[COL_CAP], CAP_ORDER, CAP_LABELS)
    bar_counts(
        lab,
        cnt,
        "P4. Momento en que se implementan capacitaciones / medidas",
        OUT / "p4_capacitaciones.png",
        colors=[COLORS["danger"], COLORS["accent"], COLORS["ok"]],
    )

    lik = df[COL_LIKERT].astype(int)
    lab = ["1\nNada\npreparada", "2", "3", "4", "5\nMuy\npreparada"]
    cnt = [int((lik == i).sum()) for i in range(1, 6)]
    bar_counts(
        lab,
        cnt,
        "P5. Preparación percibida para anticipar un accidente (escala 1–5)",
        OUT / "p5_preparacion.png",
        colors=["#b91c1c", "#c2410c", "#a16207", "#0f766e", "#15803d"],
    )

    acc = df[COL_ACC].astype(str).str.strip().str.lower()
    yes = int(acc.str.startswith("si").sum())
    no = int((~acc.str.startswith("si")).sum())
    donut(
        ["Sí (propio o compañero)", "No"],
        [yes, no],
        "P6. ¿Hubo accidente laboral o enfermedad profesional en el trabajo actual?",
        OUT / "p6_accidente.png",
        colors=[COLORS["danger"], COLORS["secondary"]],
    )

    mask_yes = acc.str.startswith("si")
    sub = df.loc[mask_yes, COL_CHANGE]
    labels, counts = [], []
    for key in CHANGE_ORDER:
        labels.append(CHANGE_LABELS[key])
        counts.append(int((sub == key).sum()))
    bar_counts(
        labels,
        counts,
        "P7. Cambios tras el accidente (solo quienes respondieron «Sí» en P6)",
        OUT / "p7_cambios.png",
        colors=[COLORS["danger"], COLORS["accent"], COLORS["ok"]],
    )

    mean_l = float(lik.mean())
    low = float((lik <= 2).mean() * 100)
    art_weak = float((~df[COL_ART].astype(str).str.contains("regular", case=False, na=False)).mean() * 100)
    reactive = float((df[COL_CAP] == CAP_ORDER[0]).mean() * 100)
    deep = int((sub == CHANGE_ORDER[2]).sum())
    none_or_min = int((sub.isin(CHANGE_ORDER[:2])).sum())
    print("--- RESUMEN ---")
    print(f"n={len(df)}")
    print(f"likert_mean={mean_l:.2f} pct_1_2={low:.1f}")
    print(f"art_sin_auditoria_regular_pct={art_weak:.1f}")
    print(f"capacitacion_reactiva_pct={reactive:.1f}")
    print(f"con_accidente={yes} deep={deep} none_or_min={none_or_min}")


if __name__ == "__main__":
    main()
