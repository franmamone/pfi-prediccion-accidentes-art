"""Vacía las agendas/visitas/historial de la app (PfiPrevencion local).

Deja a TODOS los establecimientos en estado "pendiente":
- app.AgendaEventos  (historial append-only de movimientos)
- app.VisitasApp     (visitas realizadas registradas en la app)
- app.AgendaItems    (agendas programadas/realizadas/canceladas)

No toca rankings, snapshots ni dossiers. Borra en orden por las FKs y
dentro de una transacción. Imprime conteos antes y después.
"""
from __future__ import annotations

import pyodbc

APP_CONN = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;DATABASE=PfiPrevencion;"
    "Trusted_Connection=yes;TrustServerCertificate=yes;"
)

TABLES = ["app.AgendaEventos", "app.VisitasApp", "app.AgendaItems"]


def counts(cur) -> dict[str, int]:
    out: dict[str, int] = {}
    for t in TABLES:
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        out[t] = cur.fetchone()[0]
    return out


def main() -> None:
    cn = pyodbc.connect(APP_CONN, autocommit=False)
    cur = cn.cursor()

    before = counts(cur)
    print("Antes:")
    for t, n in before.items():
        print(f"  {t}: {n}")

    # Orden por dependencias: eventos y visitas dependen de AgendaItems.
    for t in TABLES:
        cur.execute(f"DELETE FROM {t}")

    cn.commit()

    after = counts(cur)
    print("Despues:")
    for t, n in after.items():
        print(f"  {t}: {n}")

    cn.close()
    total_borrado = sum(before.values())
    print(f"OK reset agenda: {total_borrado} filas eliminadas. Todos los establecimientos quedan en 'pendiente'.")


if __name__ == "__main__":
    main()
