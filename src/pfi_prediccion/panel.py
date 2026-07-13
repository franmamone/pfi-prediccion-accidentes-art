from __future__ import annotations

import numpy as np
import pandas as pd

from .config import PANEL_END, PANEL_START, TARGET_COLUMN
from .features import enrich_panel_features

PANEL_LAST_FEATURE_MONTH = pd.Period(PANEL_END, freq="M")
PANEL_START_MONTH = pd.Period(PANEL_START, freq="M")

CONTEXT_COLUMNS = [
    "id_empleador",
    "actividad_ciiu_empleador",
    "actividad_ciiu_empleador_nombre",
    "actividad_ciiu_establecimiento",
    "actividad_ciiu_establecimiento_nombre",
    "actividad_ciiu_rev4_principal",
    "actividad_ciiu_rev4_nombre",
    "actividad_grupo_nombre",
    "cantidad_capitas",
    "nivel_seguridad_empleador",
    "nivel_seguridad_establecimiento",
    "id_tipo_establecimiento",
    "flag_establecimiento_principal",
    "antiguedad_establecimiento_meses",
    "id_provincia_establecimiento",
    "codigo_postal_establecimiento",
    "flag_coordenadas_validas",
    "latitud_establecimiento",
    "longitud_establecimiento",
    "flag_riesgo_higienico",
    "dotacion_establecimiento",
    "frecuencia_visita_ciiu_meses",
    "visitas_planificadas_12m",
    "visitas_realizadas_12m",
    "flag_pese_vigente",
]

# Solo disponibles en filas de accidente (merge_asof); el resto viene del universo.
DYNAMIC_CONTEXT_COLUMNS = [
    "visitas_planificadas_12m",
    "visitas_realizadas_12m",
    "flag_pese_vigente",
]

UNIVERSE_STATIC_COLUMNS = [c for c in CONTEXT_COLUMNS if c not in DYNAMIC_CONTEXT_COLUMNS]


def _prepare_accidents(accidents: pd.DataFrame) -> pd.DataFrame:
    df = accidents.copy()
    df["fecha_hora_accidente"] = pd.to_datetime(df["fecha_hora_accidente"])
    df["periodo"] = df["fecha_hora_accidente"].dt.to_period("M")
    return df.sort_values(["id_establecimiento", "fecha_hora_accidente"])


def _months_since_last_accident(counts: pd.Series) -> pd.Series:
    arr = counts.to_numpy(dtype=float)
    out = np.full(len(arr), np.nan)
    last = -1
    for i, value in enumerate(arr):
        if value > 0:
            last = i
        if last >= 0:
            out[i] = float(i - last)
    return pd.Series(out, index=counts.index)


def _build_grid(
    accidents: pd.DataFrame,
    universe: pd.DataFrame | None,
) -> pd.DataFrame:
    periods = pd.period_range(PANEL_START_MONTH, PANEL_LAST_FEATURE_MONTH, freq="M")

    if universe is not None and not universe.empty:
        est_ids = universe["id_establecimiento"].dropna().unique()
        idx = pd.MultiIndex.from_product(
            [est_ids, periods], names=["id_establecimiento", "periodo_key"]
        )
        panel = idx.to_frame(index=False)
    else:
        first_accident = accidents.groupby("id_establecimiento")["periodo"].min()
        chunks: list[pd.DataFrame] = []
        for eid, start in first_accident.items():
            start = max(start, PANEL_START_MONTH)
            est_periods = pd.period_range(start, PANEL_LAST_FEATURE_MONTH, freq="M")
            if len(est_periods) == 0:
                continue
            chunks.append(
                pd.DataFrame(
                    {
                        "id_establecimiento": eid,
                        "periodo_key": est_periods,
                    }
                )
            )
        panel = pd.concat(chunks, ignore_index=True)

    panel["periodo"] = panel["periodo_key"].astype(str)
    return panel


def _rolling_accident_features(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.sort_values(["id_establecimiento", "periodo_key"]).copy()
    g = out.groupby("id_establecimiento", sort=False)["accidentes_en_mes"]

    out["accidentes_3m"] = g.transform(lambda s: s.rolling(3, min_periods=1).sum()).astype(int)
    out["accidentes_6m"] = g.transform(lambda s: s.rolling(6, min_periods=1).sum()).astype(int)
    out["accidentes_12m"] = g.transform(lambda s: s.rolling(12, min_periods=1).sum()).astype(int)
    out["accidentes_total_previos"] = g.transform("cumsum").astype(int)
    out[TARGET_COLUMN] = g.shift(-1).fillna(0).gt(0).astype(int)
    out["meses_desde_ultimo_accidente"] = g.transform(_months_since_last_accident)
    return out


def _attach_dynamic_accident_context(
    panel: pd.DataFrame, accidents: pd.DataFrame
) -> pd.DataFrame:
    """Visitas/PESE desde el último accidente conocido (solo establecimientos con siniestros)."""
    dyn_cols = [c for c in DYNAMIC_CONTEXT_COLUMNS if c in accidents.columns]
    if not dyn_cols:
        return panel

    est_with_acc = accidents["id_establecimiento"].unique()
    subset = panel[panel["id_establecimiento"].isin(est_with_acc)][
        ["id_establecimiento", "periodo", "periodo_key"]
    ].copy()
    subset["mes_fin"] = subset["periodo_key"].dt.to_timestamp(how="end")

    acc_cols = ["fecha_hora_accidente", *dyn_cols]
    acc_by_est = {
        eid: grp.sort_values("fecha_hora_accidente")
        for eid, grp in accidents.groupby("id_establecimiento", sort=False)
    }

    chunks: list[pd.DataFrame] = []
    for eid, left_grp in subset.groupby("id_establecimiento", sort=False):
        left_sorted = left_grp.sort_values("mes_fin")
        right_grp = acc_by_est.get(eid)
        if right_grp is None or right_grp.empty:
            chunks.append(left_sorted[["id_establecimiento", "periodo"]])
            continue
        merged = pd.merge_asof(
            left_sorted,
            right_grp[acc_cols],
            left_on="mes_fin",
            right_on="fecha_hora_accidente",
            direction="backward",
        )
        chunks.append(merged[["id_establecimiento", "periodo", *dyn_cols]])

    context = pd.concat(chunks, ignore_index=True)
    return panel.merge(context, on=["id_establecimiento", "periodo"], how="left")


def _attach_accident_context(panel: pd.DataFrame, accidents: pd.DataFrame) -> pd.DataFrame:
    """Contexto completo desde accidentes (modo sin universo, ~3k establecimientos)."""
    month_grid = panel[["id_establecimiento", "periodo", "periodo_key"]].copy()
    month_grid["mes_fin"] = month_grid["periodo_key"].dt.to_timestamp(how="end")

    acc_cols = ["fecha_hora_accidente"] + [c for c in CONTEXT_COLUMNS if c in accidents.columns]
    acc_by_est = {
        eid: grp.sort_values("fecha_hora_accidente")
        for eid, grp in accidents.groupby("id_establecimiento", sort=False)
    }

    chunks: list[pd.DataFrame] = []
    for eid, left_grp in month_grid.groupby("id_establecimiento", sort=False):
        left_sorted = left_grp.sort_values("mes_fin")
        right_grp = acc_by_est.get(eid)
        if right_grp is None or right_grp.empty:
            chunks.append(left_sorted[["id_establecimiento", "periodo"]])
            continue
        merged = pd.merge_asof(
            left_sorted,
            right_grp[acc_cols],
            left_on="mes_fin",
            right_on="fecha_hora_accidente",
            direction="backward",
        )
        keep = ["id_establecimiento", "periodo"] + [
            c for c in CONTEXT_COLUMNS if c in merged.columns
        ]
        chunks.append(merged[keep])

    context = pd.concat(chunks, ignore_index=True)
    return panel.drop(
        columns=[c for c in CONTEXT_COLUMNS if c in panel.columns], errors="ignore"
    ).merge(context, on=["id_establecimiento", "periodo"], how="left")


def _attach_universe_context(panel: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    static_cols = ["id_establecimiento"] + [
        c for c in UNIVERSE_STATIC_COLUMNS if c in universe.columns
    ]
    if "id_empleador" in universe.columns and "id_empleador" not in static_cols:
        static_cols.append("id_empleador")

    uni = universe[static_cols].drop_duplicates("id_establecimiento")
    return panel.drop(
        columns=[c for c in static_cols if c != "id_establecimiento" and c in panel.columns],
        errors="ignore",
    ).merge(uni, on="id_establecimiento", how="left")


def _attach_empleador_rolling_features(panel: pd.DataFrame, accidents: pd.DataFrame) -> pd.DataFrame:
    """Agregados mensuales de accidentes a nivel empleador (sin leakage de T+1)."""
    if "id_empleador" not in panel.columns:
        return panel

    emp_acc = accidents[["id_empleador", "periodo"]].copy()
    emp_acc["periodo_key"] = emp_acc["periodo"]
    emp_monthly = (
        emp_acc.groupby(["id_empleador", "periodo_key"], as_index=False)
        .size()
        .rename(columns={"size": "accidentes_empleador_en_mes"})
    )

    emp_panel = panel[["id_establecimiento", "id_empleador", "periodo_key"]].drop_duplicates()
    emp_panel = emp_panel.merge(emp_monthly, on=["id_empleador", "periodo_key"], how="left")
    emp_panel["accidentes_empleador_en_mes"] = emp_panel["accidentes_empleador_en_mes"].fillna(0)

    g = emp_panel.groupby("id_empleador", sort=False)["accidentes_empleador_en_mes"]
    emp_panel["accidentes_empleador_3m"] = g.transform(
        lambda s: s.rolling(3, min_periods=1).sum()
    ).astype(int)
    emp_panel["accidentes_empleador_6m"] = g.transform(
        lambda s: s.rolling(6, min_periods=1).sum()
    ).astype(int)
    emp_panel["accidentes_empleador_12m"] = g.transform(
        lambda s: s.rolling(12, min_periods=1).sum()
    ).astype(int)

    keep = [
        "id_empleador",
        "periodo_key",
        "accidentes_empleador_3m",
        "accidentes_empleador_6m",
        "accidentes_empleador_12m",
    ]
    return panel.merge(
        emp_panel[keep].drop_duplicates(["id_empleador", "periodo_key"]),
        on=["id_empleador", "periodo_key"],
        how="left",
    )


def _months_since_last_event(flag_series: pd.Series) -> pd.Series:
    arr = flag_series.to_numpy(dtype=float)
    out = np.full(len(arr), np.nan)
    last = -1
    for i, value in enumerate(arr):
        if value > 0:
            last = i
        if last >= 0:
            out[i] = float(i - last)
    return pd.Series(out, index=flag_series.index)


def _attach_prevencion_mes(panel: pd.DataFrame, prevencion: pd.DataFrame) -> pd.DataFrame:
    """Une visitas mensuales y calcula rolling 12m + meses desde última visita."""
    prev = prevencion.copy()
    if "periodo_key" not in prev.columns:
        prev["periodo_key"] = pd.PeriodIndex(prev["periodo"], freq="M")

    prev = prev[
        [
            "id_establecimiento",
            "periodo_key",
            "visitas_planificadas_mes",
            "visitas_realizadas_mes",
        ]
    ].drop_duplicates(["id_establecimiento", "periodo_key"])

    out = panel.merge(prev, on=["id_establecimiento", "periodo_key"], how="left")
    out["visitas_planificadas_mes"] = out["visitas_planificadas_mes"].fillna(0).astype(int)
    out["visitas_realizadas_mes"] = out["visitas_realizadas_mes"].fillna(0).astype(int)

    g = out.groupby("id_establecimiento", sort=False)
    out["visitas_planificadas_12m_prev"] = g["visitas_planificadas_mes"].transform(
        lambda s: s.rolling(12, min_periods=1).sum()
    ).astype(int)
    out["visitas_realizadas_12m_prev"] = g["visitas_realizadas_mes"].transform(
        lambda s: s.rolling(12, min_periods=1).sum()
    ).astype(int)
    out["meses_desde_ultima_visita"] = g["visitas_realizadas_mes"].transform(
        _months_since_last_event
    )
    return out


NOMINA_FEATURE_COLUMNS = [
    "dotacion_nomina_mes",
    "edad_promedio",
    "pct_mayores_50",
    "pct_mujeres",
    "antiguedad_promedio_meses",
    "pct_antiguedad_menor_6m",
    "tareas_distintas",
    "pct_en_tarea_principal",
]


def _attach_nomina_mes(panel: pd.DataFrame, nomina: pd.DataFrame) -> pd.DataFrame:
    """Une agregados de nómina vigente al cierre de cada mes."""
    nom = nomina.copy()
    if "periodo_key" not in nom.columns:
        nom["periodo_key"] = pd.PeriodIndex(nom["periodo"], freq="M")

    nom_cols = [
        c
        for c in NOMINA_FEATURE_COLUMNS
        if c in nom.columns and c not in {"id_establecimiento", "periodo_key"}
    ]
    nom = nom[["id_establecimiento", "periodo_key", *nom_cols]].drop_duplicates(
        ["id_establecimiento", "periodo_key"]
    )

    out = panel.merge(nom, on=["id_establecimiento", "periodo_key"], how="left")
    if "dotacion_nomina_mes" in out.columns:
        out["dotacion_nomina_mes"] = out["dotacion_nomina_mes"].fillna(0).astype(int)
    for col in nom_cols:
        if col == "dotacion_nomina_mes":
            continue
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    return out


def build_establishment_month_panel(
    accidents: pd.DataFrame,
    universe: pd.DataFrame | None = None,
    prevencion: pd.DataFrame | None = None,
    nomina: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Panel establecimiento × mes con target prospectivo T+1."""
    df = _prepare_accidents(accidents)
    if df.empty:
        raise ValueError("El dataset de accidentes está vacío.")

    print(f"[panel] Construyendo grilla...", flush=True)
    panel = _build_grid(df, universe)

    monthly_counts = (
        df.groupby(["id_establecimiento", "periodo"], as_index=False)
        .size()
        .rename(columns={"size": "accidentes_en_mes"})
    )
    monthly_counts["periodo_key"] = monthly_counts["periodo"]

    panel = panel.merge(
        monthly_counts[["id_establecimiento", "periodo_key", "accidentes_en_mes"]],
        on=["id_establecimiento", "periodo_key"],
        how="left",
    )
    panel["accidentes_en_mes"] = panel["accidentes_en_mes"].fillna(0).astype(int)
    panel["anio"] = panel["periodo_key"].dt.year
    panel["mes"] = panel["periodo_key"].dt.month

    print(f"[panel] {len(panel):,} filas — calculando features temporales...", flush=True)
    panel = _rolling_accident_features(panel)

    if universe is not None and not universe.empty:
        print(f"[panel] Uniendo universo ({universe['id_establecimiento'].nunique():,} establecimientos)...", flush=True)
        panel = _attach_universe_context(panel, universe)
        print("[panel] Contexto dinámico desde accidentes...", flush=True)
        panel = _attach_dynamic_accident_context(panel, df)
    else:
        print("[panel] Contexto desde accidentes...", flush=True)
        panel = _attach_accident_context(panel, df)

    if "id_empleador" not in panel.columns and "id_empleador" in df.columns:
        emp_map = df.groupby("id_establecimiento")["id_empleador"].first().reset_index()
        panel = panel.merge(emp_map, on="id_establecimiento", how="left")

    print("[panel] Agregados por empleador...", flush=True)
    panel = _attach_empleador_rolling_features(panel, df)

    if prevencion is not None and not prevencion.empty:
        print(f"[panel] Uniendo prevención ({len(prevencion):,} filas visitas×mes)...", flush=True)
        panel = _attach_prevencion_mes(panel, prevencion)

    if nomina is not None and not nomina.empty:
        print(f"[panel] Uniendo nómina ({len(nomina):,} filas est×mes)...", flush=True)
        panel = _attach_nomina_mes(panel, nomina)

    panel["periodo_objetivo"] = (panel["periodo_key"] + 1).astype(str)
    panel = panel.drop(columns=["periodo_key"])
    panel = enrich_panel_features(panel)
    print(f"[panel] Listo: {len(panel):,} filas.", flush=True)
    return panel.reset_index(drop=True)


def panel_summary(panel: pd.DataFrame) -> dict:
    positives = int(panel[TARGET_COLUMN].sum())
    return {
        "filas": len(panel),
        "establecimientos": panel["id_establecimiento"].nunique(),
        "positivos": positives,
        "tasa_positiva": positives / len(panel) if len(panel) else 0.0,
        "periodo_min": panel["periodo"].min(),
        "periodo_max": panel["periodo"].max(),
    }
