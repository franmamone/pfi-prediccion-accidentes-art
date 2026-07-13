from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from .config import LEAKAGE_COLUMNS, REPORTS_DIR, ensure_dirs


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


def run_eda(accidents: pd.DataFrame, output_dir: Path | None = None) -> dict:
    ensure_dirs()
    output_dir = Path(output_dir or REPORTS_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    df = accidents.copy()
    df["fecha_hora_accidente"] = pd.to_datetime(df["fecha_hora_accidente"])

    nulls = _null_summary(df)
    nulls.to_csv(output_dir / "eda_nulos_por_columna.csv", index=False)

    # Distribuciones clave
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
        counts = df[col].fillna("NULL").value_counts().head(15)
        counts.to_csv(output_dir / f"eda_dist_{col}.csv", header=["n"])

    # Gráficos
    sns.set_theme(style="whitegrid")

    fig, ax = plt.subplots(figsize=(8, 4))
    df["anio_accidente"].value_counts().sort_index().plot(kind="bar", ax=ax, color="#2f6fed")
    ax.set_title("Accidentes por año")
    ax.set_xlabel("Año")
    ax.set_ylabel("Cantidad")
    fig.tight_layout()
    fig.savefig(output_dir / "eda_accidentes_por_anio.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    top_formas = df["forma_accidente"].fillna("NULL").value_counts().head(10)
    top_formas.plot(kind="barh", ax=ax, color="#1f9d55")
    ax.set_title("Top 10 formas de accidente")
    fig.tight_layout()
    fig.savefig(output_dir / "eda_top_formas_accidente.png", dpi=150)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 4))
    df["dotacion_establecimiento"].fillna(-1).clip(lower=-1).value_counts().head(10).plot(
        kind="bar", ax=ax, color="#f08c00"
    )
    ax.set_title("Distribución dotación (top 10 valores)")
    fig.tight_layout()
    fig.savefig(output_dir / "eda_dotacion.png", dpi=150)
    plt.close(fig)

    leakage_present = sorted(LEAKAGE_COLUMNS.intersection(df.columns))
    return {
        "filas": len(df),
        "columnas": len(df.columns),
        "periodo_min": str(df["fecha_hora_accidente"].min()),
        "periodo_max": str(df["fecha_hora_accidente"].max()),
        "columnas_alto_nulo": nulls.head(15).to_dict(orient="records"),
        "columnas_leakage_documentadas": leakage_present,
        "reportes_en": str(output_dir),
    }
