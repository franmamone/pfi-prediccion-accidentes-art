"""Genera figuras PNG de la encuesta de user research (hito 50%).

Lee el Excel/CSV de respuestas de Google Forms y escribe gr\'aficos en
docs/figures/encuesta/.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "figures" / "encuesta"
DEFAULT_CSV = REPO / "data" / "raw" / "encuesta" / "encuesta_prevencion_seguridad.csv"
DEFAULT_XLSX_REPO = REPO / "data" / "raw" / "encuesta" / "encuesta_respuestas.xlsx"
DOWNLOADS_CSV = Path(
    r"c:\Users\FranciscoDanteMamone\Downloads"
    r"\Encuesta sobre Prevención y Seguridad Laboral .csv"
    r"\Encuesta sobre Prevención y Seguridad Laboral .csv"
)
DEFAULT_XLSX = Path(
    r"c:\Users\FranciscoDanteMamone\Documents\UADE\Tesis"
    r"\Encuesta sobre Prevención y Seguridad Laboral  (Respuestas).xlsx"
)

INDIGO = "#4F46E5"
CYAN = "#06B6D4"
AMBER = "#F59E0B"
ROSE = "#F43F5E"
VIOLET = "#8B5CF6"
EMERALD = "#10B981"
SKY = "#3B82F6"
PINK = "#EC4899"
OK = "#10B981"
DANGER = "#F43F5E"
MUTED = "#64748B"
INK = "#0F172A"
GRID = "#E2E8F0"
FUN = [INDIGO, CYAN, AMBER, ROSE, VIOLET, EMERALD, SKY, PINK]
KAPPA = 0.5522847498

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


def _pixel_scale(ax) -> tuple[float, float]:
    ax.figure.canvas.draw()
    origin = ax.transData.transform((0.0, 0.0))
    ux = ax.transData.transform((1.0, 0.0))
    uy = ax.transData.transform((0.0, 1.0))
    return abs(ux[0] - origin[0]), abs(uy[1] - origin[1])


def _circle_radii(ax, thickness: float, *, perp_is_y: bool) -> tuple[float, float]:
    ppx, ppy = _pixel_scale(ax)
    r_px = min(11.0, 0.22 * abs(thickness) * (ppy if perp_is_y else ppx))
    return r_px / max(ppx, 1e-9), r_px / max(ppy, 1e-9)


def _rounded_rect(x: float, y: float, w: float, h: float, rx: float, ry: float, color: str) -> PathPatch:
    if w < 0:
        x, w = x + w, -w
    if h < 0:
        y, h = y + h, -h
    rx = min(rx, w / 2)
    ry = min(ry, h / 2)
    x0, y0, x1, y1 = x, y, x + w, y + h
    k = KAPPA
    verts = [
        (x0 + rx, y0),
        (x1 - rx, y0),
        (x1 - rx + k * rx, y0),
        (x1, y0 + ry - k * ry),
        (x1, y0 + ry),
        (x1, y1 - ry),
        (x1, y1 - ry + k * ry),
        (x1 - rx + k * rx, y1),
        (x1 - rx, y1),
        (x0 + rx, y1),
        (x0 + rx - k * rx, y1),
        (x0, y1 - ry + k * ry),
        (x0, y1 - ry),
        (x0, y0 + ry),
        (x0, y0 + ry - k * ry),
        (x0 + rx - k * rx, y0),
        (x0 + rx, y0),
    ]
    codes = [
        MplPath.MOVETO,
        MplPath.LINETO,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.LINETO,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.LINETO,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.LINETO,
        MplPath.CURVE4,
        MplPath.CURVE4,
        MplPath.CURVE4,
    ]
    return PathPatch(MplPath(verts, codes), facecolor=color, edgecolor="none", linewidth=0, zorder=2, clip_on=True)


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
    palette = colors or FUN
    palette = (palette * ((len(labels) // len(palette)) + 1))[: len(labels)]
    fig_w = 8.4 if not horizontal else 8.8
    fig_h = 4.9 if not horizontal else max(3.9, 0.58 * len(labels) + 1.7)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_axisbelow(True)
    ax.set_title(title)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#cbd5e1")
    ax.spines["bottom"].set_color("#cbd5e1")
    if horizontal:
        height = 0.70
        y = np.arange(len(labels), dtype=float)
        ax.xaxis.grid(True, color=GRID, linewidth=0.9, zorder=0)
        ax.set_yticks(y)
        ax.set_yticklabels(labels, fontsize=10.5)
        ax.set_xlabel("Respuestas")
        ax.set_xlim(0, max(counts) * 1.32 if counts else 1)
        ax.set_ylim(len(labels) - 0.38, -0.62)
        fig.tight_layout(rect=(0, 0.03, 1, 1))
        rx, ry = _circle_radii(ax, height, perp_is_y=True)
        for yi, cnt, col in zip(y, counts, palette):
            ax.add_patch(_rounded_rect(0.0, yi - height / 2, float(cnt), height, rx, ry, col))
        for yi, cnt in zip(y, counts):
            pct = 100.0 * cnt / total
            ax.text(
                cnt + max(total * 0.012, 0.4),
                yi,
                f"{cnt}   {pct:.0f}%",
                va="center",
                ha="left",
                fontsize=10,
                color=INK,
            )
    else:
        width = 0.72
        x = np.arange(len(labels), dtype=float)
        ax.yaxis.grid(True, color=GRID, linewidth=0.9, zorder=0)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=10)
        ax.set_ylabel(ylabel or "Respuestas")
        ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        ax.set_ylim(0, max(counts) * 1.30 if counts else 1)
        ax.set_xlim(-0.62, len(labels) - 0.38)
        fig.tight_layout(rect=(0, 0.03, 1, 1))
        rx, ry = _circle_radii(ax, width, perp_is_y=False)
        for xi, cnt, col in zip(x, counts, palette):
            ax.add_patch(_rounded_rect(xi - width / 2, 0.0, width, float(cnt), rx, ry, col))
        for xi, cnt in zip(x, counts):
            pct = 100.0 * cnt / total
            ax.text(
                xi,
                cnt + max(total * 0.02, 0.25),
                f"{cnt}\n{pct:.0f}%",
                ha="center",
                va="bottom",
                fontsize=9.5,
                color=INK,
            )
    note = extra_note or f"n = {total}"
    fig.text(0.99, 0.012, note, ha="right", va="bottom", fontsize=9, color=MUTED)
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
    ax.text(0, 0.08, str(total), ha="center", va="center", fontsize=22, fontweight="bold", color=INDIGO)
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
    src = next(
        (p for p in (DEFAULT_XLSX, DEFAULT_XLSX_REPO, DEFAULT_CSV, DOWNLOADS_CSV) if p.exists()),
        None,
    )
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
        colors=FUN,
    )

    lab, cnt = size_series(df)
    bar_counts(
        lab,
        cnt,
        "P2. Tamaño del establecimiento / empresa",
        OUT / "p2_tamanio.png",
        colors=[EMERALD, INDIGO, AMBER, SKY],
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
        colors=["#F43F5E", "#FB7185", "#FBBF24", "#34D399", "#059669"],
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
        colors=[ROSE, CYAN],
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
