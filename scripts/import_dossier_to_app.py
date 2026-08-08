"""Importa data/processed/dossier_preventor.json a PfiPrevencion (localhost).

- Aplica sql/app/05_add_contexto_preventor.sql (idempotente).
- Refresca app.EstablecimientoDossier (delete + insert) con el dossier por
  establecimiento (JSON compacto) y contadores desnormalizados para la grilla.
"""
from __future__ import annotations

import json
from pathlib import Path

import pyodbc

ROOT = Path(__file__).resolve().parents[1]
DOSSIER = ROOT / "data" / "processed" / "dossier_preventor.json"
DDL = ROOT / "sql" / "app" / "05_add_contexto_preventor.sql"

APP_CONN = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;DATABASE=PfiPrevencion;"
    "Trusted_Connection=yes;TrustServerCertificate=yes;"
)


def apply_ddl(cur) -> None:
    sql = DDL.read_text(encoding="utf-8")
    batches = [b.strip() for b in sql.replace("\r\n", "\n").split("\nGO") if b.strip()]
    for batch in batches:
        cur.execute(batch)


def main() -> None:
    payload = json.loads(DOSSIER.read_text(encoding="utf-8"))
    referencia = payload.get("referencia")
    fuente = payload.get("fuente")
    ests = payload.get("establecimientos") or {}

    cn = pyodbc.connect(APP_CONN, autocommit=False)
    cur = cn.cursor()
    apply_ddl(cur)
    cn.commit()

    cur.execute("DELETE FROM app.EstablecimientoDossier")

    rows = []
    for est, data in ests.items():
        acc = data.get("accidentes") or {}
        vis = data.get("visitas") or {}
        if not acc and not vis:
            continue
        rows.append(
            (
                est,
                referencia,
                (fuente or "")[:200],
                acc.get("total"),
                acc.get("ultimos_12m"),
                vis.get("total"),
                json.dumps(data, ensure_ascii=False),
            )
        )

    cur.fast_executemany = False
    cur.executemany(
        """
        INSERT INTO app.EstablecimientoDossier
            (IdEstablecimiento, Referencia, Fuente, AccidentesTotal, AccidentesUlt12m, VisitasTotal, DossierJson)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    cn.commit()
    cur.execute("SELECT COUNT(*) FROM app.EstablecimientoDossier")
    total = cur.fetchone()[0]
    cn.close()
    print(f"OK import dossier: {len(rows)} filas insertadas, {total} en tabla")


if __name__ == "__main__":
    main()
