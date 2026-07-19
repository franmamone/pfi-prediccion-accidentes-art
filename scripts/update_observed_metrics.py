"""Actualiza outcomes maduros, precisión observada y cobertura operativa por cohorte.

Requiere --fuente-completa-hasta (YYYY-MM). Nunca convierte meses pendientes en cero.
"""

from __future__ import annotations

import argparse
import json
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import pyodbc

from _bootstrap import SRC  # noqa: F401

from pfi_prediccion.config import (
    CAPACITY_CRITICAL,
    CAPACITY_MONTHLY,
    PANEL_PARQUET,
    REPORTS_RANKING_DIR,
    target_column_for_horizon,
)

DEFAULT_CONN = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=PfiPrevencion;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)


def _add_months(periodo: str, months: int) -> str:
    year, month = map(int, periodo.split("-"))
    month += months
    while month > 12:
        month -= 12
        year += 1
    while month < 1:
        month += 12
        year -= 1
    return f"{year:04d}-{month:02d}"


def _periodo_le(a: str, b: str) -> bool:
    return a <= b


def _window_for_horizon(periodo: str, horizonte: str) -> tuple[str, str]:
    if horizonte == "3m":
        return _add_months(periodo, 1), _add_months(periodo, 3)
    return _add_months(periodo, 1), _add_months(periodo, 1)


def _maturity(ventana_fin: str, fuente: str) -> str:
    if _periodo_le(ventana_fin, fuente):
        return "maduro"
    # Si la ventana ya empezó pero no terminó → parcial
    return "parcial" if fuente >= _add_months(ventana_fin, -2) else "pendiente"


def _connect(conn_str: str) -> pyodbc.Connection:
    return pyodbc.connect(conn_str, autocommit=False)


def _cohort_window(activado: datetime, horizonte: str) -> tuple[date, date]:
    start = activado.date()
    months = 3 if horizonte == "3m" else 1
    # Ventana operativa: desde activación inclusive hasta activación + N meses.
    end_month = start.month + months
    end_year = start.year
    while end_month > 12:
        end_month -= 12
        end_year += 1
    last_day = monthrange(end_year, end_month)[1]
    # Fin = mismo día del mes N meses después, o último día del mes.
    day = min(start.day, last_day)
    end = date(end_year, end_month, day)
    return start, end


def update_outcomes_from_panel(
    conn: pyodbc.Connection,
    panel: pd.DataFrame,
    fuente: str,
) -> dict:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT i.Id, i.SnapshotId, i.IdEstablecimiento, i.Ranking, s.Periodo, s.Horizonte
        FROM app.RankingItems i
        INNER JOIN app.RankingSnapshots s ON s.Id = i.SnapshotId
        """
    )
    rows = cur.fetchall()
    if not rows:
        return {"outcomes": 0, "metricas": 0}

    panel_idx = panel.set_index(["id_establecimiento", "periodo"], drop=False)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    upserted = 0

    for item_id, snapshot_id, est_id, ranking, periodo, horizonte in rows:
        est_id = str(est_id).strip()
        periodo = str(periodo).strip()
        horizonte = str(horizonte).strip()
        ventana_ini, ventana_fin = _window_for_horizon(periodo, horizonte)
        estado = _maturity(ventana_fin, fuente)
        target_col = target_column_for_horizon(horizonte)
        cantidad = None
        outcome = None
        if estado == "maduro":
            key = (est_id, periodo)
            if key in panel_idx.index:
                val = panel_idx.loc[key, target_col]
                if isinstance(val, pd.Series):
                    val = val.iloc[0]
                if pd.notna(val):
                    outcome = int(val) >= 1
                    cantidad = int(val) if float(val) == int(val) else (1 if outcome else 0)
                else:
                    estado = "parcial"
            else:
                estado = "parcial"

        cur.execute(
            """
            MERGE app.RankingItemOutcomes AS t
            USING (SELECT ? AS RankingItemId) AS s
            ON t.RankingItemId = s.RankingItemId
            WHEN MATCHED THEN UPDATE SET
                SnapshotId = ?, PeriodoDecision = ?, Horizonte = ?,
                VentanaInicio = ?, VentanaFin = ?, Estado = ?,
                CantidadAccidentes = ?, OutcomeBinario = ?,
                FuenteCompletaHasta = ?, EvaluadoEn = ?
            WHEN NOT MATCHED THEN INSERT (
                RankingItemId, SnapshotId, PeriodoDecision, Horizonte,
                VentanaInicio, VentanaFin, Estado, CantidadAccidentes,
                OutcomeBinario, FuenteCompletaHasta, EvaluadoEn
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            item_id,
            snapshot_id,
            periodo,
            horizonte,
            ventana_ini,
            ventana_fin,
            estado,
            cantidad,
            outcome,
            fuente,
            now,
            item_id,
            snapshot_id,
            periodo,
            horizonte,
            ventana_ini,
            ventana_fin,
            estado,
            cantidad,
            outcome,
            fuente,
            now,
        )
        upserted += 1

    # Agregar métricas por snapshot/topK
    cur.execute("SELECT DISTINCT SnapshotId FROM app.RankingItemOutcomes")
    snapshot_ids = [int(r[0]) for r in cur.fetchall()]
    metricas = 0
    for snapshot_id in snapshot_ids:
        cur.execute(
            """
            SELECT o.Estado, i.Ranking, o.OutcomeBinario, o.VentanaInicio, o.VentanaFin
            FROM app.RankingItemOutcomes o
            INNER JOIN app.RankingItems i ON i.Id = o.RankingItemId
            WHERE o.SnapshotId = ?
            """,
            snapshot_id,
        )
        outcomes = cur.fetchall()
        if not outcomes:
            continue
        ventana_ini = outcomes[0][3]
        ventana_fin = outcomes[0][4]
        for top_k in (CAPACITY_CRITICAL, CAPACITY_MONTHLY):
            cohort = [r for r in outcomes if int(r[1]) <= top_k]
            denom = len(cohort)
            estados = {r[0] for r in cohort}
            if all(e == "maduro" for e in estados) and denom > 0:
                estado = "maduro"
                positivos = sum(1 for r in cohort if r[2] is True or r[2] == 1)
                precision = positivos / denom
            elif any(e == "maduro" for e in estados):
                estado = "parcial"
                positivos = None
                precision = None
            else:
                estado = "pendiente"
                positivos = None
                precision = None

            cur.execute(
                """
                MERGE app.SnapshotMetricasObservadas AS t
                USING (SELECT ? AS SnapshotId, ? AS TopK) AS s
                ON t.SnapshotId = s.SnapshotId AND t.TopK = s.TopK
                WHEN MATCHED THEN UPDATE SET
                    Estado = ?, Denominador = ?, Positivos = ?, Precision = ?,
                    VentanaInicio = ?, VentanaFin = ?, FuenteCompletaHasta = ?, CalculadoEn = ?
                WHEN NOT MATCHED THEN INSERT (
                    SnapshotId, TopK, Estado, Denominador, Positivos, Precision,
                    VentanaInicio, VentanaFin, FuenteCompletaHasta, CalculadoEn
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                snapshot_id,
                top_k,
                estado,
                denom,
                positivos,
                precision,
                ventana_ini,
                ventana_fin,
                fuente,
                now,
                snapshot_id,
                top_k,
                estado,
                denom,
                positivos,
                precision,
                ventana_ini,
                ventana_fin,
                fuente,
                now,
            )
            metricas += 1

    conn.commit()
    return {"outcomes": upserted, "metricas": metricas}


def update_coverage(conn: pyodbc.Connection) -> dict:
    cur = conn.cursor()
    cur.execute(
        """
        SELECT Id, Horizonte, ActivadoEn, ImportadoEn, EsVigente
        FROM app.RankingSnapshots
        WHERE ItemsImportados IS NULL OR ItemsImportados > 0
        """
    )
    snapshots = cur.fetchall()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    today = now.date()
    updated = 0

    for snapshot_id, horizonte, activado, importado, _es_vigente in snapshots:
        activado_dt = activado or importado or now
        if isinstance(activado_dt, datetime):
            pass
        else:
            activado_dt = datetime.combine(activado_dt, datetime.min.time())
        ventana_ini, ventana_fin = _cohort_window(activado_dt, str(horizonte))
        estado = "cerrada" if today > ventana_fin else "abierta"
        # No congelar/sobrescribir cerradas salvo recálculo de abiertas.
        cur.execute(
            "SELECT Estado FROM app.SnapshotCoberturas WHERE SnapshotId = ? AND TopK = 50",
            snapshot_id,
        )
        existing = cur.fetchone()
        if existing and existing[0] == "cerrada" and estado == "cerrada":
            continue

        for top_k in (CAPACITY_CRITICAL, CAPACITY_MONTHLY):
            cur.execute(
                """
                SELECT IdEstablecimiento
                FROM app.RankingItems
                WHERE SnapshotId = ? AND Ranking <= ?
                """,
                snapshot_id,
                top_k,
            )
            cohort_ids = {str(r[0]).strip() for r in cur.fetchall()}
            denom = len(cohort_ids)
            if denom == 0:
                continue

            # Cubierto: agenda del snapshot con estado programada|realizada cuya
            # FechaPlanificada o visita real cae en la ventana operativa.
            cur.execute(
                """
                SELECT a.IdEstablecimiento, a.Estado, a.FechaPlanificada, v.FechaHoraReal
                FROM app.AgendaItems a
                LEFT JOIN app.VisitasApp v ON v.AgendaItemId = a.Id
                WHERE a.SnapshotId = ?
                   OR (a.SnapshotId IS NULL AND a.Periodo = (
                        SELECT Periodo FROM app.RankingSnapshots WHERE Id = ?
                   ) AND a.Horizonte = (
                        SELECT Horizonte FROM app.RankingSnapshots WHERE Id = ?
                   ))
                """,
                snapshot_id,
                snapshot_id,
                snapshot_id,
            )
            programados: set[str] = set()
            realizados: set[str] = set()
            for est, estado_ag, fecha_plan, fecha_real in cur.fetchall():
                est = str(est).strip()
                if est not in cohort_ids:
                    continue
                if estado_ag == "cancelada":
                    continue
                in_window = False
                if fecha_plan is not None:
                    fp = fecha_plan if isinstance(fecha_plan, date) else fecha_plan.date()
                    if ventana_ini <= fp <= ventana_fin:
                        in_window = True
                if fecha_real is not None:
                    fr = fecha_real.date() if isinstance(fecha_real, datetime) else fecha_real
                    if ventana_ini <= fr <= ventana_fin:
                        in_window = True
                        realizados.add(est)
                if in_window and estado_ag in {"programada", "realizada"}:
                    programados.add(est)
                if estado_ag == "realizada" and in_window:
                    realizados.add(est)

            cubiertos = programados | realizados
            pct = round(100.0 * len(cubiertos) / denom, 1) if denom else 0.0
            corte = now if estado == "cerrada" else None

            cur.execute(
                """
                MERGE app.SnapshotCoberturas AS t
                USING (SELECT ? AS SnapshotId, ? AS TopK) AS s
                ON t.SnapshotId = s.SnapshotId AND t.TopK = s.TopK
                WHEN MATCHED THEN UPDATE SET
                    VentanaInicio = ?, VentanaFin = ?, Denominador = ?,
                    Programados = ?, Realizados = ?, Cubiertos = ?, Porcentaje = ?,
                    Estado = ?, CorteEn = COALESCE(t.CorteEn, ?), CalculadoEn = ?
                WHEN NOT MATCHED THEN INSERT (
                    SnapshotId, TopK, VentanaInicio, VentanaFin, Denominador,
                    Programados, Realizados, Cubiertos, Porcentaje, Estado, CorteEn, CalculadoEn
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                snapshot_id,
                top_k,
                ventana_ini,
                ventana_fin,
                denom,
                len(programados),
                len(realizados),
                len(cubiertos),
                pct,
                estado,
                corte,
                now,
                snapshot_id,
                top_k,
                ventana_ini,
                ventana_fin,
                denom,
                len(programados),
                len(realizados),
                len(cubiertos),
                pct,
                estado,
                corte,
                now,
            )
            updated += 1

    conn.commit()
    return {"coberturas": updated}


def seed_holdout_metrics(conn: pyodbc.Connection, fuente: str) -> dict:
    """Inserta métricas históricas holdout 2025 sin borrar snapshots existentes."""
    cur = conn.cursor()
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    seeded = 0
    for horizon, fname in (("1m", "top_k_per_month_1m.json"), ("3m", "top_k_per_month_3m.json")):
        path = REPORTS_RANKING_DIR / fname
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        months = data.get("months") or []
        for month in months:
            periodo = str(month["periodo"])
            ventana_ini, ventana_fin = _window_for_horizon(periodo, horizon)
            if not _periodo_le(ventana_fin, fuente):
                continue
            artifact_hash = f"holdout-metrics-{horizon}-{periodo}".ljust(64, "0")[:64]
            cur.execute(
                """
                SELECT Id FROM app.RankingSnapshots
                WHERE Periodo = ? AND Horizonte = ? AND ArtifactHash = ?
                """,
                periodo,
                horizon,
                artifact_hash,
            )
            row = cur.fetchone()
            if row:
                snapshot_id = int(row[0])
            else:
                cur.execute(
                    """
                    INSERT INTO app.RankingSnapshots
                        (Periodo, Horizonte, ArchivoOrigen, Filas, Criticos, Altos, EsVigente,
                         ModeloVersion, ArtifactHash, DatosHasta, ImportadoEn, ActivadoEn,
                         UniversoFilas, ItemsImportados)
                    OUTPUT INSERTED.Id
                    VALUES (?, ?, ?, ?, 50, 175, 0, ?, ?, ?, ?, ?, ?, 0)
                    """,
                    periodo,
                    horizon,
                    f"reports/ranking/{fname}",
                    int(month.get("filas") or 0),
                    "holdout_metrics",
                    artifact_hash,
                    fuente,
                    now,
                    now,
                    int(month.get("filas") or 0),
                )
                snapshot_id = int(cur.fetchone()[0])

            for top_k, key in ((50, "precision_at_50"), (225, "precision_at_225")):
                precision = month.get(key)
                if precision is None:
                    continue
                positivos = int(round(float(precision) * top_k))
                cur.execute(
                    """
                    MERGE app.SnapshotMetricasObservadas AS t
                    USING (SELECT ? AS SnapshotId, ? AS TopK) AS s
                    ON t.SnapshotId = s.SnapshotId AND t.TopK = s.TopK
                    WHEN MATCHED THEN UPDATE SET
                        Estado = N'maduro', Denominador = ?, Positivos = ?, Precision = ?,
                        VentanaInicio = ?, VentanaFin = ?, FuenteCompletaHasta = ?, CalculadoEn = ?
                    WHEN NOT MATCHED THEN INSERT (
                        SnapshotId, TopK, Estado, Denominador, Positivos, Precision,
                        VentanaInicio, VentanaFin, FuenteCompletaHasta, CalculadoEn
                    ) VALUES (?, ?, N'maduro', ?, ?, ?, ?, ?, ?, ?);
                    """,
                    snapshot_id,
                    top_k,
                    top_k,
                    positivos,
                    float(precision),
                    ventana_ini,
                    ventana_fin,
                    fuente,
                    now,
                    snapshot_id,
                    top_k,
                    top_k,
                    positivos,
                    float(precision),
                    ventana_ini,
                    ventana_fin,
                    fuente,
                    now,
                )
                seeded += 1
    conn.commit()
    return {"holdout_metricas": seeded}


def main() -> None:
    parser = argparse.ArgumentParser(description="Actualiza outcomes, precisión y cobertura")
    parser.add_argument("--fuente-completa-hasta", required=True, help="YYYY-MM cierre de fuente")
    parser.add_argument("--conn", default=DEFAULT_CONN)
    parser.add_argument("--skip-holdout-seed", action="store_true")
    parser.add_argument("--skip-coverage", action="store_true")
    parser.add_argument("--skip-outcomes", action="store_true")
    args = parser.parse_args()

    fuente = args.fuente_completa_hasta.strip()
    if len(fuente) != 7 or fuente[4] != "-":
        raise SystemExit("fuente-completa-hasta debe ser YYYY-MM")

    conn = _connect(args.conn)
    results: dict = {"fuente_completa_hasta": fuente}
    try:
        if not args.skip_outcomes:
            panel = pd.read_parquet(PANEL_PARQUET)
            results["panel"] = update_outcomes_from_panel(conn, panel, fuente)
        if not args.skip_holdout_seed:
            results["holdout"] = seed_holdout_metrics(conn, fuente)
        if not args.skip_coverage:
            results["coverage"] = update_coverage(conn)
        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
