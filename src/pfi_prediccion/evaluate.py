from __future__ import annotations

import json
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import average_precision_score, brier_score_loss, precision_recall_curve

from .config import (
    CAPACITY_CRITICAL,
    CAPACITY_MONTHLY,
    CAPACITY_QUARTERLY,
    HOLDOUT_YEAR,
    HORIZON_1M,
    HORIZON_3M,
    MODEL_PIPELINE_PATH,
    QUARTERLY_CUTOFFS,
    REPORTS_MODEL_DIR,
    REPORTS_RANKING_DIR,
    TARGET_COLUMN,
    VISIT_COOLDOWN_MONTHS,
    ensure_dirs,
    model_pipeline_path,
    target_column_for_horizon,
)
from .features import ciiu_seccion
from .inference import predict_blended_batched


TOP_K_VALUES = [50, 100, 200, 225, 500, 675, 1000, 2000]
TOP_K_PER_MONTH = [50, 100, 200, 225]


def recall_at_top_k(y_true: np.ndarray, y_prob: np.ndarray, k: int) -> dict:
    n = len(y_true)
    k = min(k, n)
    if k == 0:
        return {"k": k, "recall": 0.0, "precision": 0.0, "lift": 0.0, "positives_in_top": 0}

    order = np.argsort(-y_prob)
    top_idx = order[:k]
    positives_top = int(y_true[top_idx].sum())
    total_positives = int(y_true.sum())
    base_rate = total_positives / n if n else 0.0
    precision = positives_top / k
    recall = positives_top / total_positives if total_positives else 0.0
    lift = precision / base_rate if base_rate > 0 else 0.0

    return {
        "k": k,
        "recall": float(recall),
        "precision": float(precision),
        "lift": float(lift),
        "positives_in_top": positives_top,
        "total_positives": total_positives,
    }


def top_k_per_month(
    scored: pd.DataFrame,
    target_col: str = TARGET_COLUMN,
    k_values: list[int] | None = None,
) -> dict:
    """Métricas top-K por mes (operación real: N visitas/mes)."""
    k_values = k_values or TOP_K_PER_MONTH
    if "periodo" not in scored.columns:
        raise ValueError("Se requiere columna periodo en scored.")

    monthly: list[dict] = []
    for periodo, group in scored.groupby("periodo", sort=True):
        valid = group[group[target_col].notna()]
        if valid.empty:
            continue
        y_true = valid[target_col].to_numpy(dtype=int)
        y_prob = valid["score_riesgo"].to_numpy()
        row = {
            "periodo": str(periodo),
            "filas": len(valid),
            "positivos": int(y_true.sum()),
        }
        for k in k_values:
            m = recall_at_top_k(y_true, y_prob, k)
            row[f"precision_at_{k}"] = m["precision"]
            row[f"recall_at_{k}"] = m["recall"]
        monthly.append(row)

    summary: dict[str, float] = {}
    for k in k_values:
        prec_col = f"precision_at_{k}"
        rec_col = f"recall_at_{k}"
        summary[f"mean_precision_at_{k}_per_month"] = float(
            np.mean([r[prec_col] for r in monthly if r["filas"] >= k]) if monthly else 0.0
        )
        summary[f"mean_recall_at_{k}_per_month"] = float(
            np.mean([r[rec_col] for r in monthly if r["filas"] >= k]) if monthly else 0.0
        )

    return {"months": monthly, "summary": summary}


def _quarterly_cutoffs_for_year(year: int) -> list[str]:
    return [f"{year}-{m}" for m in QUARTERLY_CUTOFFS]


def top_k_per_quarter_non_overlapping(
    scored: pd.DataFrame,
    target_col: str,
    year: int,
    k_values: list[int] | None = None,
) -> dict:
    """Evaluación trimestral no solapada en cortes 03/06/09/12."""
    k_values = k_values or [150, CAPACITY_QUARTERLY, CAPACITY_CRITICAL * 3]
    rows: list[dict] = []
    for cutoff in _quarterly_cutoffs_for_year(year):
        group = scored[scored["periodo"] == cutoff]
        valid = group[group[target_col].notna()]
        if valid.empty:
            continue
        # Un establecimiento por corte
        valid = valid.drop_duplicates("id_establecimiento", keep="first")
        y_true = valid[target_col].to_numpy(dtype=int)
        y_prob = valid["score_riesgo"].to_numpy()
        row = {
            "cutoff": cutoff,
            "filas": len(valid),
            "positivos": int(y_true.sum()),
            "establecimientos_unicos": int(valid["id_establecimiento"].nunique()),
        }
        for k in k_values:
            m = recall_at_top_k(y_true, y_prob, k)
            row[f"precision_at_{k}"] = m["precision"]
            row[f"recall_at_{k}"] = m["recall"]
            row[f"positives_in_top_{k}"] = m["positives_in_top"]
        rows.append(row)

    summary: dict[str, float] = {}
    for k in k_values:
        vals = [r[f"precision_at_{k}"] for r in rows if r["filas"] >= min(k, 1)]
        summary[f"mean_precision_at_{k}_per_quarter"] = float(np.mean(vals)) if vals else 0.0
    return {"quarters": rows, "summary": summary, "year": year}


def compare_visit_baseline(
    panel: pd.DataFrame,
    scored: pd.DataFrame,
    target_col: str,
    k: int = CAPACITY_MONTHLY,
) -> dict:
    """Compara visitas reales vs ranking modelo vs historial vs azar (mismo volumen)."""
    df = scored.merge(
        panel[
            [
                c
                for c in (
                    "id_establecimiento",
                    "periodo",
                    "visitas_realizadas_mes",
                    "accidentes_empleador_3m",
                    "accidentes_12m",
                )
                if c in panel.columns
            ]
        ],
        on=["id_establecimiento", "periodo"],
        how="left",
    )
    df = df[df[target_col].notna()].copy()
    df[target_col] = df[target_col].astype(int)

    months = []
    for periodo, g in df.groupby("periodo", sort=True):
        base_rate = float(g[target_col].mean()) if len(g) else 0.0
        row = {"periodo": str(periodo), "filas": len(g), "base_rate": base_rate}

        # Visitas reales
        if "visitas_realizadas_mes" in g.columns:
            visited = g[g["visitas_realizadas_mes"].fillna(0) > 0]
            row["visitas_n"] = int(len(visited))
            row["visitas_precision"] = (
                float(visited[target_col].mean()) if len(visited) else None
            )
        else:
            row["visitas_n"] = 0
            row["visitas_precision"] = None

        # Modelo top-k
        top = g.nlargest(min(k, len(g)), "score_riesgo")
        row["modelo_precision"] = float(top[target_col].mean()) if len(top) else None

        # Historial: accidentes_12m > 0, tomar top-k por accidentes_12m
        if "accidentes_12m" in g.columns:
            hist = g.sort_values("accidentes_12m", ascending=False).head(min(k, len(g)))
            row["historial_precision"] = float(hist[target_col].mean()) if len(hist) else None
        else:
            row["historial_precision"] = None

        # Azar
        rand = g.sample(n=min(k, len(g)), random_state=abs(hash(str(periodo))) % (2**31))
        row["azar_precision"] = float(rand[target_col].mean()) if len(rand) else None
        months.append(row)

    def _mean(key: str) -> float | None:
        vals = [m[key] for m in months if m.get(key) is not None]
        return float(np.mean(vals)) if vals else None

    return {
        "k": k,
        "months": months,
        "summary": {
            "mean_visitas_precision": _mean("visitas_precision"),
            "mean_modelo_precision": _mean("modelo_precision"),
            "mean_historial_precision": _mean("historial_precision"),
            "mean_azar_precision": _mean("azar_precision"),
            "nota": (
                "Comparación de focalización, no efecto causal: una visita puede "
                "haber prevenido el accidente que se evalúa."
            ),
        },
    }


def evaluate_with_cooldown(
    scored: pd.DataFrame,
    panel: pd.DataFrame,
    target_col: str,
    k: int = CAPACITY_CRITICAL,
    cooldown_months: int = VISIT_COOLDOWN_MONTHS,
) -> dict:
    """Top-K excluyendo visitados recientemente (cooldown)."""
    cols = ["id_establecimiento", "periodo", "meses_desde_ultima_visita"]
    cols = [c for c in cols if c in panel.columns]
    df = scored.merge(panel[cols], on=["id_establecimiento", "periodo"], how="left")
    df = df[df[target_col].notna()].copy()
    df[target_col] = df[target_col].astype(int)

    months = []
    for periodo, g in df.groupby("periodo", sort=True):
        eligible = g.copy()
        if "meses_desde_ultima_visita" in eligible.columns:
            # Elegible si nunca visitado (NaN) o última visita hace >= cooldown meses
            m = eligible["meses_desde_ultima_visita"]
            eligible = eligible[m.isna() | (m >= cooldown_months)]
        if eligible.empty:
            continue
        top = eligible.nlargest(min(k, len(eligible)), "score_riesgo")
        months.append(
            {
                "periodo": str(periodo),
                "elegibles": len(eligible),
                "precision": float(top[target_col].mean()) if len(top) else None,
            }
        )
    vals = [m["precision"] for m in months if m["precision"] is not None]
    return {
        "k": k,
        "cooldown_months": cooldown_months,
        "mean_precision": float(np.mean(vals)) if vals else None,
        "months": months,
    }


def sector_coverage(scored: pd.DataFrame, panel: pd.DataFrame, k: int = CAPACITY_CRITICAL) -> dict:
    if "actividad_ciiu_establecimiento" not in panel.columns:
        return {}
    df = scored.merge(
        panel[["id_establecimiento", "periodo", "actividad_ciiu_establecimiento"]],
        on=["id_establecimiento", "periodo"],
        how="left",
    )
    df["sector"] = df["actividad_ciiu_establecimiento"].map(ciiu_seccion)
    cover: dict[str, list[int]] = {}
    for _, g in df.groupby("periodo"):
        top = g.nlargest(min(k, len(g)), "score_riesgo")
        counts = top["sector"].value_counts()
        for sec, n in counts.items():
            cover.setdefault(str(sec), []).append(int(n))
    return {sec: {"mean_in_topk": float(np.mean(v)), "months": len(v)} for sec, v in cover.items()}


def evaluate_model(
    panel: pd.DataFrame,
    reports_dir: Path | None = None,
    pipeline_path: Path | None = None,
    horizon: str = HORIZON_1M,
    target_column: str | None = None,
    holdout_year: int | None = None,
) -> dict:
    ensure_dirs()
    # Si se pasa reports_dir, todo va ahí; si no, métricas→modelo/ y scored→ranking/.
    custom_dir = Path(reports_dir) if reports_dir else None
    model_dir = custom_dir or REPORTS_MODEL_DIR
    ranking_dir = custom_dir or REPORTS_RANKING_DIR
    model_dir.mkdir(parents=True, exist_ok=True)
    ranking_dir.mkdir(parents=True, exist_ok=True)

    target_col = target_column or target_column_for_horizon(horizon)
    path = Path(pipeline_path or model_pipeline_path(horizon))
    if not path.exists():
        path = MODEL_PIPELINE_PATH
    artifact = joblib.load(path)
    threshold = float(artifact["threshold"])
    features = artifact["features"]

    year = holdout_year
    if year is None:
        # Preferir HOLDOUT_YEAR si hay filas evaluables; si no, año máximo disponible.
        if (panel["anio"] == HOLDOUT_YEAR).any() and panel.loc[
            panel["anio"] == HOLDOUT_YEAR, target_col
        ].notna().any():
            year = HOLDOUT_YEAR
        else:
            year = int(panel.loc[panel[target_col].notna(), "anio"].max())
            print(f"[evaluate] Usando año {year} como holdout (2025 no disponible).", flush=True)

    test_df = panel[(panel["anio"] == year) & panel[target_col].notna()].copy()
    test_df[target_col] = test_df[target_col].astype(int)
    X_test = test_df[features]
    y_test = test_df[target_col].to_numpy()

    print(f"[evaluate:{horizon}] Prediciendo holdout {year} ({len(X_test):,} filas)...", flush=True)
    y_prob = predict_blended_batched(artifact, X_test)

    top_k_metrics = [recall_at_top_k(y_test, y_prob, k) for k in TOP_K_VALUES]
    precision, recall, _ = precision_recall_curve(y_test, y_prob)
    pr_auc = float(average_precision_score(y_test, y_prob))

    # Calibración
    brier = float(brier_score_loss(y_test, y_prob)) if len(np.unique(y_test)) > 1 else None
    calib = {}
    if brier is not None and y_test.sum() > 10:
        frac_pos, mean_pred = calibration_curve(y_test, y_prob, n_bins=8, strategy="quantile")
        calib = {
            "brier_score": brier,
            "reliability": [
                {"mean_predicted": float(m), "fraction_positive": float(f)}
                for m, f in zip(mean_pred, frac_pos)
            ],
            "recomendacion_ui": (
                "Mostrar como score/prioridad, no como probabilidad, "
                "salvo que Brier/reliability sean aceptables."
            ),
        }

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    axes[0].plot(recall, precision, label=f"PR-AUC = {pr_auc:.3f}")
    axes[0].set_xlabel("Recall")
    axes[0].set_ylabel("Precisión")
    axes[0].set_title(f"Curva precisión-recall ({horizon}, holdout {year})")
    axes[0].legend()
    axes[0].grid(alpha=0.3)

    ks = [m["k"] for m in top_k_metrics]
    recalls = [m["recall"] for m in top_k_metrics]
    lifts = [m["lift"] for m in top_k_metrics]
    axes[1].bar(range(len(ks)), recalls, color="steelblue", alpha=0.8)
    axes[1].set_xticks(range(len(ks)))
    axes[1].set_xticklabels([str(k) for k in ks], rotation=45)
    axes[1].set_ylabel("Recall")
    axes[1].set_title("Recall @ top-K")
    for i, lift in enumerate(lifts):
        axes[1].text(i, recalls[i] + 0.01, f"×{lift:.1f}", ha="center", fontsize=8)

    fig.tight_layout()
    chart_path = model_dir / f"model_evaluation_{horizon}.png"
    fig.savefig(chart_path, dpi=120)
    plt.close(fig)

    scored = test_df[
        ["id_establecimiento", "periodo", "periodo_objetivo", target_col]
    ].copy()
    if "periodo_objetivo" not in scored.columns and "periodo_objetivo_1m" in test_df.columns:
        scored["periodo_objetivo"] = test_df["periodo_objetivo_1m"]
    scored["score_riesgo"] = y_prob
    scored["alerta"] = (y_prob >= threshold).astype(int)
    scored = scored.sort_values("score_riesgo", ascending=False)
    scored_path = ranking_dir / f"scored_panel_holdout_{year}_{horizon}.csv"
    scored.to_csv(scored_path, index=False, sep=";")

    per_month = top_k_per_month(scored, target_col=target_col)
    (ranking_dir / f"top_k_per_month_{horizon}.json").write_text(
        json.dumps(per_month, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    quarterly = None
    if horizon == HORIZON_3M:
        quarterly = top_k_per_quarter_non_overlapping(scored, target_col, year)
        (ranking_dir / f"top_k_per_quarter_{horizon}.json").write_text(
            json.dumps(quarterly, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    baseline = compare_visit_baseline(
        panel, scored, target_col, k=CAPACITY_MONTHLY if horizon == HORIZON_1M else CAPACITY_QUARTERLY
    )
    cooldown = evaluate_with_cooldown(scored, panel, target_col, k=CAPACITY_CRITICAL)
    coverage = sector_coverage(scored, panel, k=CAPACITY_CRITICAL)

    results = {
        "horizon": horizon,
        "target_column": target_col,
        "holdout_year": year,
        "test_rows": len(test_df),
        "pr_auc": pr_auc,
        "threshold": threshold,
        "dual_model": bool(artifact.get("dual_model")),
        "top_k_global": top_k_metrics,
        "top_k_per_month": per_month["summary"],
        "top_k_per_quarter": quarterly["summary"] if quarterly else None,
        "baseline_comparison": baseline["summary"],
        "cooldown": {
            "mean_precision": cooldown["mean_precision"],
            "cooldown_months": cooldown["cooldown_months"],
            "k": cooldown["k"],
        },
        "sector_coverage_top50": coverage,
        "calibration": calib,
        "capacity_reference": {
            "critical": CAPACITY_CRITICAL,
            "monthly": CAPACITY_MONTHLY,
            "quarterly": CAPACITY_QUARTERLY,
        },
        "chart_path": str(chart_path),
        "scored_path": str(scored_path),
    }

    out_metrics = model_dir / f"evaluation_metrics_{horizon}.json"
    out_metrics.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    (model_dir / f"baseline_comparison_{horizon}.json").write_text(
        json.dumps(baseline, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return results
