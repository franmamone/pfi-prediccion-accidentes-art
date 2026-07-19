from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from .config import LEAKAGE_COLUMNS, REPORTS_EDA_DIR, ensure_dirs


def _null_summary(df: pd.DataFrame) -> pd.DataFrame:
    summary = pd.DataFrame(
        {
            "columna": df.columns,
            "nulos": df.isna().sum().values,
            "pct_nulos": (df.isna().mean() * 100).round(2).values,
            "distintos": [df[col].nunique(dropna=True) for col in df.columns],
        }
    )
    return summary.sort_values("pct_nulos", ascending=False)


def _save(fig: plt.Figure, path: Path, caption: str) -> None:
    fig.text(0.01, 0.005, caption, fontsize=8, color="#555555")
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)


def run_eda(accidents: pd.DataFrame, output_dir: Path | None = None) -> dict:
    """EDA técnico de calidad; los gráficos narrativos viven en reports/dataset."""
    ensure_dirs()
    output_dir = Path(output_dir or REPORTS_EDA_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = accidents.copy()
    df["fecha_hora_accidente"] = pd.to_datetime(df["fecha_hora_accidente"], errors="coerce")
    valid_dates = df["fecha_hora_accidente"].dropna()
    period = (
        f"{valid_dates.min():%Y-%m} a {valid_dates.max():%Y-%m}"
        if not valid_dates.empty
        else "período sin determinar"
    )
    source = f"Fuente: accidentes ART · {period} · n={len(df):,}"

    nulls = _null_summary(df)
    nulls.to_csv(output_dir / "eda_nulos_por_columna.csv", index=False)

    key_cols = [
        "sexo_trabajador",
        "gravedad",
        "forma_accidente",
        "actividad_ciiu_establecimiento",
        "flag_coordenadas_validas",
        "dotacion_establecimiento",
    ]
    for col in key_cols:
        if col not in df.columns:
            continue
        counts = df[col].fillna("Sin dato").value_counts().head(15)
        counts.rename_axis(col).rename("n_accidentes").to_csv(
            output_dir / f"eda_dist_{col}.csv"
        )

    sns.set_theme(style="whitegrid")

    annual = df["fecha_hora_accidente"].dt.year.value_counts().sort_index()
    fig, ax = plt.subplots(figsize=(8, 4))
    bars = ax.bar(annual.index.astype("Int64").astype(str), annual.values, color="#2f6fed")
    if len(bars):
        bars[-1].set_hatch("//")
    ax.set_title("Accidentes denunciados por año")
    ax.set_xlabel("Año del accidente")
    ax.set_ylabel("Cantidad de accidentes")
    for bar, value in zip(bars, annual.values):
        ax.text(bar.get_x() + bar.get_width() / 2, value, f"{value:,}", ha="center", va="bottom", fontsize=8)
    _save(
        fig,
        output_dir / "eda_accidentes_por_anio.png",
        source + " · 2025 es parcial (hasta noviembre; barra tramada).",
    )

    if "forma_accidente" in df.columns:
        forms = df["forma_accidente"].fillna("Sin dato").value_counts().head(10).sort_values()
        pct = 100 * forms / len(df)
        fig, ax = plt.subplots(figsize=(11, 6))
        ax.barh(forms.index, pct.values, color="#1f9d55")
        ax.set_title("Formas de accidente más frecuentes")
        ax.set_xlabel("Porcentaje de accidentes (%)")
        ax.set_ylabel("Forma del accidente")
        for i, (p, n) in enumerate(zip(pct.values, forms.values)):
            ax.text(p, i, f" {p:.1f}% (n={n:,})", va="center", fontsize=8)
        _save(
            fig,
            output_dir / "eda_top_formas_accidente.png",
            source + " · Acumulado del período completo; no está separado por año.",
        )

    if "dotacion_establecimiento" in df.columns:
        dot = pd.to_numeric(df["dotacion_establecimiento"], errors="coerce")
        categories = pd.Series("Sin dato", index=df.index, dtype="object")
        categories[dot.eq(0)] = "0 registrado"
        categories[dot.between(1, 5)] = "1–5"
        categories[dot.between(6, 10)] = "6–10"
        categories[dot.between(11, 50)] = "11–50"
        categories[dot.between(51, 200)] = "51–200"
        categories[dot.gt(200)] = "201+"
        order = ["Sin dato", "0 registrado", "1–5", "6–10", "11–50", "51–200", "201+"]
        counts = categories.value_counts().reindex(order, fill_value=0)
        fig, ax = plt.subplots(figsize=(9, 4.5))
        ax.bar(counts.index, counts.values, color=["#adb5bd", "#e8590c"] + ["#f08c00"] * 5)
        ax.set_title("Accidentes según dotación registrada")
        ax.set_xlabel("Dotación del establecimiento")
        ax.set_ylabel("Cantidad de accidentes")
        ax.tick_params(axis="x", rotation=20)
        for i, value in enumerate(counts.values):
            ax.text(i, value, f"{value:,}", ha="center", va="bottom", fontsize=8)
        _save(
            fig,
            output_dir / "eda_dotacion.png",
            source
            + " · Cuenta accidentes, no establecimientos únicos; 0 puede representar ausencia de coincidencia de nómina.",
        )

    leakage_present = sorted(LEAKAGE_COLUMNS.intersection(df.columns))
    return {
        "filas": len(df),
        "columnas": len(df.columns),
        "periodo_min": str(valid_dates.min()) if not valid_dates.empty else None,
        "periodo_max": str(valid_dates.max()) if not valid_dates.empty else None,
        "columnas_alto_nulo": nulls.head(15).to_dict(orient="records"),
        "columnas_leakage_documentadas": leakage_present,
        "reportes_en": str(output_dir),
        "nota": "EDA de calidad. Los gráficos narrativos separados por período están en reports/dataset/.",
    }
