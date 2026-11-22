"""Copia snapshots vigentes (1m/3m) + items + SHAP/métricas desde SQL local a AWS (túnel SSH).

Requiere env: PFI_AWS_SQL_PASSWORD
"""

from __future__ import annotations

import os
import sys

import pyodbc

LOCAL = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=PfiPrevencion;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)


def aws_cs() -> str:
    pwd = os.environ.get("PFI_AWS_SQL_PASSWORD", "").strip()
    if not pwd:
        raise SystemExit("Definí PFI_AWS_SQL_PASSWORD (password del SQL en AWS vía túnel).")
    return (
        "DRIVER={ODBC Driver 18 for SQL Server};"
        "SERVER=127.0.0.1,14333;"
        "DATABASE=PfiPrevencion;"
        "UID=sa;"
        f"PWD={pwd};"
        "TrustServerCertificate=yes;"
    )

SNAP_COLS = [
    "Id", "Periodo", "Horizonte", "GeneradoEn", "ArchivoOrigen", "Filas", "Criticos",
    "Altos", "EsVigente", "ModeloVersion", "ArtifactHash", "DatosHasta", "ImportadoEn",
    "ActivadoEn", "UniversoFilas", "ItemsImportados",
]
ITEM_COLS = [
    "Id", "SnapshotId", "IdEstablecimiento", "IdEmpleador", "Ranking", "ScoreRiesgo",
    "Banda", "Motivo", "ObligacionPrs", "EnCooldown", "UltimaVisitaHaceMeses", "Sector",
    "CiiuDivision", "CantidadCapitas", "DotacionNominaMes", "AlertaUmbral", "MotivoPrincipalTexto",
]
CONTRIB_COLS = [
    "Id", "RankingItemId", "Orden", "Feature", "Tema", "Etiqueta", "ValorObservado",
    "ShapValue", "Direccion", "Descripcion",
]
SHAP_COLS = [
    "Id", "SnapshotId", "TopK", "Feature", "Tema", "Etiqueta", "OrdenImportancia",
    "ItemsCohorte", "MeanAbsShap", "MeanShap", "P50AbsShap", "P90AbsShap", "PctAumenta",
    "Metodo", "GeneradoEn",
]
MET_COLS = [
    "Id", "SnapshotId", "TopK", "Estado", "Denominador", "Positivos", "Precision",
    "VentanaInicio", "VentanaFin", "FuenteCompletaHasta", "EvaluadoEn",
]
COB_COLS = [
    "Id", "SnapshotId", "TopK", "VentanaInicio", "VentanaFin", "Denominador",
    "Cubiertos", "Porcentaje", "Estado",
]


def fetchall(cur, sql: str, params=()):
    cur.execute(sql, params)
    return cur.fetchall()


def bulk_insert(dst, table: str, cols: list[str], rows, identity: bool = True):
    if not rows:
        print(f"  skip {table}: 0 rows")
        return
    placeholders = ",".join("?" for _ in cols)
    col_list = ",".join(cols)
    sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"
    cur = dst.cursor()
    if identity:
        cur.execute(f"SET IDENTITY_INSERT {table} ON")
    # pyodbc fast_executemany
    cur.fast_executemany = True
    batch = 500
    for i in range(0, len(rows), batch):
        chunk = [tuple(r) for r in rows[i : i + batch]]
        cur.executemany(sql, chunk)
        print(f"  {table}: {min(i + batch, len(rows))}/{len(rows)}")
    if identity:
        cur.execute(f"SET IDENTITY_INSERT {table} OFF")
    dst.commit()


def main() -> int:
    print("Connecting local...")
    src = pyodbc.connect(LOCAL, autocommit=False)
    print("Connecting AWS via tunnel :14333...")
    dst = pyodbc.connect(aws_cs(), autocommit=False)

    sc = src.cursor()
    snaps = fetchall(
        sc,
        "SELECT Id FROM app.RankingSnapshots WHERE EsVigente = 1 AND Horizonte IN ('1m','3m') ORDER BY Id",
    )
    snap_ids = [r[0] for r in snaps]
    if not snap_ids:
        print("No vigente snapshots locally")
        return 1
    print("Snapshot IDs:", snap_ids)

    dc = dst.cursor()
    existing = fetchall(dc, "SELECT COUNT(*) FROM app.RankingSnapshots")[0][0]
    if existing:
        print(f"AWS already has {existing} snapshots; clearing ranking tables for demo reload...")
        dc.execute("DELETE FROM app.RankingItemContribuciones")
        dc.execute("DELETE FROM app.RankingItemOutcomes")
        dc.execute("DELETE FROM app.RankingItems")
        dc.execute("DELETE FROM app.SnapshotShapAgregados")
        dc.execute("DELETE FROM app.SnapshotMetricasObservadas")
        dc.execute("DELETE FROM app.SnapshotCoberturas")
        dc.execute("DELETE FROM app.RankingSnapshots")
        dst.commit()

    id_list = ",".join(str(i) for i in snap_ids)

    snap_rows = fetchall(
        sc, f"SELECT {','.join(SNAP_COLS)} FROM app.RankingSnapshots WHERE Id IN ({id_list})"
    )
    item_rows = fetchall(
        sc, f"SELECT {','.join(ITEM_COLS)} FROM app.RankingItems WHERE SnapshotId IN ({id_list})"
    )
    item_ids = [r[0] for r in item_rows]
    print(f"Items: {len(item_ids)}")

    contrib_rows = []
    if item_ids:
        # chunk IN clause
        for i in range(0, len(item_ids), 800):
            chunk = item_ids[i : i + 800]
            ids = ",".join(str(x) for x in chunk)
            contrib_rows.extend(
                fetchall(
                    sc,
                    f"SELECT {','.join(CONTRIB_COLS)} FROM app.RankingItemContribuciones WHERE RankingItemId IN ({ids})",
                )
            )

    shap_rows = fetchall(
        sc, f"SELECT {','.join(SHAP_COLS)} FROM app.SnapshotShapAgregados WHERE SnapshotId IN ({id_list})"
    )
    # metricas / coberturas may have different column sets — probe
    met_rows = fetchall(sc, f"SELECT * FROM app.SnapshotMetricasObservadas WHERE SnapshotId IN ({id_list})")
    cob_rows = fetchall(sc, f"SELECT * FROM app.SnapshotCoberturas WHERE SnapshotId IN ({id_list})")

    print("Inserting snapshots...")
    bulk_insert(dst, "app.RankingSnapshots", SNAP_COLS, snap_rows)
    print("Inserting items...")
    bulk_insert(dst, "app.RankingItems", ITEM_COLS, item_rows)
    print("Inserting contribuciones...")
    bulk_insert(dst, "app.RankingItemContribuciones", CONTRIB_COLS, contrib_rows)
    print("Inserting shap agregados...")
    bulk_insert(dst, "app.SnapshotShapAgregados", SHAP_COLS, shap_rows)

    # metricas / coberturas: use cursor description from source
    sc.execute(f"SELECT * FROM app.SnapshotMetricasObservadas WHERE SnapshotId IN ({id_list})")
    met_cols = [d[0] for d in sc.description]
    met_rows = sc.fetchall()
    bulk_insert(dst, "app.SnapshotMetricasObservadas", met_cols, met_rows)

    sc.execute(f"SELECT * FROM app.SnapshotCoberturas WHERE SnapshotId IN ({id_list})")
    cob_cols = [d[0] for d in sc.description]
    cob_rows = sc.fetchall()
    bulk_insert(dst, "app.SnapshotCoberturas", cob_cols, cob_rows)

    # outcomes opcional
    sc.execute(
        f"SELECT * FROM app.RankingItemOutcomes WHERE SnapshotId IN ({id_list})"
    )
    out_cols = [d[0] for d in sc.description]
    out_rows = sc.fetchall()
    bulk_insert(dst, "app.RankingItemOutcomes", out_cols, out_rows)

    dc.execute(
        "SELECT Horizonte, COUNT(*) FROM app.RankingItems i "
        "JOIN app.RankingSnapshots s ON s.Id = i.SnapshotId WHERE s.EsVigente=1 "
        "GROUP BY Horizonte"
    )
    print("AWS vigente counts:", dc.fetchall())
    print("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
