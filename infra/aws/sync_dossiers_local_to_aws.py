"""Copia EstablecimientoDossier + NormativaChunk desde SQL local a AWS (túnel :14333)."""

from __future__ import annotations

import sys

import pyodbc

LOCAL = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;DATABASE=PfiPrevencion;Trusted_Connection=yes;TrustServerCertificate=yes;"
)
AWS = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=127.0.0.1,14333;DATABASE=PfiPrevencion;UID=sa;PWD=REDACTED;TrustServerCertificate=yes;"
)


def bulk(dst, table: str, cols: list[str], rows, identity: bool = False):
    if not rows:
        print(f"  skip {table}")
        return
    cur = dst.cursor()
    if identity:
        cur.execute(f"SET IDENTITY_INSERT {table} ON")
    cur.fast_executemany = True
    sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({','.join('?' for _ in cols)})"
    for i in range(0, len(rows), 200):
        cur.executemany(sql, [tuple(r) for r in rows[i : i + 200]])
        print(f"  {table}: {min(i+200,len(rows))}/{len(rows)}")
    if identity:
        cur.execute(f"SET IDENTITY_INSERT {table} OFF")
    dst.commit()


def main() -> int:
    src = pyodbc.connect(LOCAL)
    dst = pyodbc.connect(AWS, autocommit=False)
    sc, dc = src.cursor(), dst.cursor()

    dc.execute("DELETE FROM app.EstablecimientoDossier")
    dc.execute("DELETE FROM app.NormativaChunk")
    dst.commit()

    sc.execute(
        "SELECT IdEstablecimiento, Referencia, Fuente, AccidentesTotal, AccidentesUlt12m, "
        "VisitasTotal, DossierJson, GeneradoEn FROM app.EstablecimientoDossier"
    )
    cols = [d[0] for d in sc.description]
    rows = sc.fetchall()
    print(f"dossiers local: {len(rows)}")
    bulk(dst, "app.EstablecimientoDossier", cols, rows, identity=False)

    sc.execute("SELECT * FROM app.NormativaChunk")
    ncols = [d[0] for d in sc.description]
    nrows = sc.fetchall()
    print(f"normativa local: {len(nrows)}")
    # Id identity?
    has_id = ncols[0].lower() == "id"
    bulk(dst, "app.NormativaChunk", ncols, nrows, identity=has_id)

    dc.execute(
        "SELECT (SELECT COUNT(*) FROM app.EstablecimientoDossier) D, "
        "(SELECT COUNT(*) FROM app.NormativaChunk) N"
    )
    print("AWS counts:", dc.fetchone())
    print("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
