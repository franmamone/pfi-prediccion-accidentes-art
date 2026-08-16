"""Genera figuras PNG de la encuesta de user research (hito 50%).

Lee el CSV de respuestas de Google Forms (n=156) y escribe gráficos en
docs/figures/encuesta/.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "figures" / "encuesta"
DEFAULT_CSV = REPO / "data" / "raw" / "encuesta" / "encuesta_prevencion_seguridad.csv"
DOWNLOADS_CSV = Path(
    r"c:\Users\FranciscoDanteMamone\Downloads"
    r"\Encuesta sobre Prevención y Seguridad Laboral .csv"
    r"\Encuesta sobre Prevención y Seguridad Laboral .csv"
)
DEFAULT_XLSX = Path(
    r"c:\Users\FranciscoDanteMamone\Documents\UADE\Tesis\50%"
    r"\Encuesta sobre Prevención y Seguridad Laboral  (Respuestas).xlsx"
)

NAVY = "#1e3a5f"
TEAL = "#0f766e"
AMBER = "#c2410c"
SLATE = "#475569"
SKY = "#0369a1"
OK = "#15803d"
DANGER = "#b91c1c"
MUTED = "#64748b"
INK = "#0f172a"
GRID = "#e2e8f0"

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
    "Menos de 10 empleados (Microempresa)": "Micro\n(<10)",
    "Entre 10 y 50 empleados (Pequeña empresa)": "Pequeña\n(10-50)",
    "Entre 51 y 200 empleados (Mediana empresa)": "Mediana\n(51-200)",
    "Más de 200 empleados (Gran empresa / Multinacional)": "Grande\n(>200)",
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


def _col(df: pd.DataFrame, needle: str) -> str:
    for c in df.columns:
        if needle.lower() in c.lower():
            return c
    raise KeyError(needle)


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#cbd5e1",
            "axes.labelcolor": INK,
            "text.color": INK,
            "xtick.color": "#334155",
            "ytick.color": "#334155",
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.titlesize": 12.5,
            "axes.titleweight": "bold",
            "axes.titlepad": 10,
            "axes.grid": False,
        }
    )


def load(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path, encoding="utf-8-sig")
    else:
        df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]
    before = len(df)
    df = df.drop_duplicates()
    print(f"Filas: {before} -> {len(df)} tras eliminar duplicados exactos")
    return df


def _round_bar(ax, bar, color: str) -> None:
    x, y = bar.get_xy()
    w, h = bar.get_width(), bar.get_height()
    bar.set_visible(False)
    pad = min(abs(w), abs(h)) * 0.18
    ax.add_patch(
        FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle=f"round,pad=0,rounding_size={pad}",
            linewidth=0,
            facecolor=color,
            mutation_aspect=0.6,
        )
    )


def bar_counts(
    labels: list[str],
    counts: list[int],
    title: str,
    outfile: Path,
    *,
    horizontal: bool = False,
    colors: list[str] | None = None,
    ylabel: str | None = None,
    extra_note: str | None = None,
) -> None:
    total = sum(counts) or 1
    palette = colors or [NAVY, TEAL, AMBER, SLATE, SKY, MUTED]
    palette = (palette * ((len(labels) // len(palette)) + 1))[: len(labels)]
    fig_w = 8.4 if not horizontal else 8.8
    fig_h = 4.9 if not horizontal else max(3.9, 0.58 * len(labels) + 1.7)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_axisbelow(True)
    if horizontal:
        ax.xaxis.grid(True, color=GRID, linewidth=0.9, zorder=0)
        y = np.arange(len(labels))
        bars = ax.barh(y, counts, color=palette, height=0.62, zorder=2)
        for bar, col in zip(bars, palette):
            _round_bar(ax, bar, col)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=10.5)
        ax.invert_yaxis()
        ax.set_xlabel("Respuestas")
        ax.set_xlim(0, max(counts) * 1.32 if counts else 1)
        for bar, cnt in zip(bars, counts):
            pct = 100.0 * cnt / total
            ax.text(
                cnt + max(total * 0.012, 0.4),
                bar.get_y() + bar.get_height() / 2,
                f"{cnt}   {pct:.0f}%",
                va="center",
                ha="left",
                fontsize=10,
                color=INK,
                fontweight="normal",
            )
    else:
        ax.yaxis.grid(True, color=GRID, linewidth=0.9, zorder=0)
        x = np.arange(len(labels))
        bars = ax.bar(x, counts, color=palette, width=0.64, zorder=2)
        for bar, col in zip(bars, palette):
            _round_bar(ax, bar, col)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=10)
        ax.set_ylabel(ylabel or "Respuestas")
        ax.set_ylim(0, max(counts) * 1.30 if counts else 1)
        for bar, cnt in zip(bars, counts):
            pct = 100.0 * cnt / total
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                cnt + max(total * 0.02, 0.25),
                f"{cnt}\n{pct:.0f}%",
                ha="center",
                va="bottom",
                fontsize=9.5,
                color=INK,
            )
    ax.set_title(title)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")
    ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
    note = extra_note or f"n = {total}"
    fig.text(0.99, 0.012, note, ha="right", va="bottom", fontsize=9, color=MUTED)
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    outfile.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outfile, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print("wrote", outfile.relative_to(REPO))


def donut(labels: list[str], counts: list[int], title: str, outfile: Path, colors: list[str]) -> None:
    total = sum(counts) or 1
    fig, ax = plt.subplots(figsize=(7.6, 5.0))
    wedges, *_ = ax.pie(
        counts,
        colors=colors,
        startangle=90,
        counterclock=False,
        wedgeprops=dict(width=0.46, edgecolor="white", linewidth=2.4),
    )
    ax.set_title(title)
    legend = [f"{lab}:  {c}  ({100 * c / total:.0f}%)" for lab, c in zip(labels, counts)]
    ax.legend(
        wedges,
        legend,
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        frameon=False,
        fontsize=10.5,
    )
    ax.text(0, 0.08, str(total), ha="center", va="center", fontsize=22, fontweight="bold", color=NAVY)
    ax.text(0, -0.18, "respuestas", ha="center", va="center", fontsize=9.5, color=MUTED)
    fig.tight_layout()
    outfile.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outfile, dpi=220, bbox_inches="tight")
    plt.close(fig)
    print("wrote", outfile.relative_to(REPO))


def sector_series(df: pd.DataFrame) -> tuple[list[str], list[int]]:
    s = df[_col(df, "sector")].astype(str).str.strip()
    mapped = s.map(lambda x: SECTOR_CANON.get(x, "Otros"))
    vc = mapped.value_counts()
    labels = [str(k) for k in vc.index]
    counts = [int(v) for v in vc.values]
    return labels, counts


def size_series(df: pd.DataFrame) -> tuple[list[str], list[int]]:
    s = df[_col(df, "tamaño")]
    labels, counts = [], []
    for key in SIZE_ORDER:
        n = int((s == key).sum())
        if n:
            labels.append(SIZE_LABELS[key])
            counts.append(n)
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
    src = next((p for p in (DEFAULT_CSV, DOWNLOADS_CSV, DEFAULT_XLSX) if p.exists()), None)
    if src is None:
        raise SystemExit("No se encontró el archivo de encuesta.")
    print("fuente", src)
    df = load(src)
    n = len(df)

    col_art = _col(df, "Aseguradora")
    col_cap = _col(df, "capacitaciones")
    col_lik = _col(df, "preparada")
    col_acc = _col(df, "enfermedad profesional")
    col_chg = _col(df, "cambios operativos")

    lab, cnt = sector_series(df)
    bar_counts(
        lab,
        cnt,
        "P1. Sector laboral de los encuestados",
        OUT / "p1_sector.png",
        horizontal=True,
        colors=[NAVY, TEAL, AMBER, SLATE, SKY, MUTED],
    )

    lab, cnt = size_series(df)
    bar_counts(
        lab,
        cnt,
        "P2. Tamaño del establecimiento / empresa",
        OUT / "p2_tamanio.png",
        colors=[TEAL, NAVY, AMBER, SLATE, MUTED],
    )

    lab, cnt = ordered_series(df[col_art], ART_ORDER, ART_LABELS)
    bar_counts(
        lab,
        cnt,
        "P3. Conocimiento de la ART y visibilidad de auditorías",
        OUT / "p3_art.png",
        colors=[DANGER, AMBER, OK],
    )

    lab, cnt = ordered_series(df[col_cap], CAP_ORDER, CAP_LABELS)
    bar_counts(
        lab,
        cnt,
        "P4. Momento en que se implementan capacitaciones / medidas",
        OUT / "p4_capacitaciones.png",
        colors=[DANGER, AMBER, OK],
    )

    lik = pd.to_numeric(df[col_lik], errors="coerce").dropna().astype(int)
    lab = ["1\nNada\npreparada", "2", "3", "4", "5\nMuy\npreparada"]
    cnt = [int((lik == i).sum()) for i in range(1, 6)]
    mean_l = float(lik.mean())
    bar_counts(
        lab,
        cnt,
        "P5. Preparación percibida para anticipar un accidente (escala 1-5)",
        OUT / "p5_preparacion.png",
        colors=["#b91c1c", "#c2410c", "#a16207", "#0f766e", "#15803d"],
        extra_note=f"n = {len(lik)}    media = {mean_l:.2f}",
    )

    acc = df[col_acc].astype(str).str.strip().str.lower()
    yes = int(acc.str.startswith("si").sum())
    no = int((~acc.str.startswith("si")).sum())
    donut(
        ["Sí (propio o compañero)", "No"],
        [yes, no],
        "P6. Accidente laboral o enfermedad profesional en el trabajo actual",
        OUT / "p6_accidente.png",
        colors=[DANGER, TEAL],
    )

    mask_yes = acc.str.startswith("si")
    sub = df.loc[mask_yes, col_chg]
    sub = sub[~sub.astype(str).str.contains("No aplica", na=False)]
    labels, counts = [], []
    for key in CHANGE_ORDER:
        labels.append(CHANGE_LABELS[key])
        counts.append(int((sub == key).sum()))
    bar_counts(
        labels,
        counts,
        "P7. Cambios tras el accidente (quienes respondieron «Sí» en P6)",
        OUT / "p7_cambios.png",
        colors=[DANGER, AMBER, OK],
        extra_note=f"n = {len(sub)}  (submuestra P6 = Sí)",
    )

    low = float((lik <= 2).mean() * 100)
    art_weak = float((~df[col_art].astype(str).str.contains("regular", case=False, na=False)).mean() * 100)
    reactive = float((df[col_cap] == CAP_ORDER[0]).mean() * 100)
    induccion = float((df[col_cap] == CAP_ORDER[1]).mean() * 100)
    deep = int((sub == CHANGE_ORDER[2]).sum())
    none_or_min = int((sub.isin(CHANGE_ORDER[:2])).sum())
    print("--- RESUMEN ---")
    print(f"n={n}")
    print(f"likert_mean={mean_l:.2f} pct_1_2={low:.1f}")
    print(f"art_sin_auditoria_regular_pct={art_weak:.1f}")
    print(f"capacitacion_reactiva_pct={reactive:.1f} induccion_pct={induccion:.1f}")
    print(f"con_accidente={yes} p7_n={len(sub)} deep={deep} none_or_min={none_or_min}")


if __name__ == "__main__":
    main()
