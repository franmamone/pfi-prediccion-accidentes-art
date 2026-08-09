"""Re-etiqueta app.RankingItems.Banda según la escala de acierto histórico
(precision@K del tramo) definida en config.BAND_ACCURACY_THRESHOLDS:
Crítico ≥80%, Alto ≥60%, Medio ≥30%, Bajo <30%.

No toca modelo, SHAP ni métricas: solo recalcula la banda a partir de
(Ranking, Horizonte) del snapshot, para todos los snapshots existentes.
"""

from __future__ import annotations

import argparse

import pyodbc

from _bootstrap import SRC  # noqa: F401

from pfi_prediccion.config import banda_por_acierto

DEFAULT_CONN = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=PfiPrevencion;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)


def _chunks(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conn", default=DEFAULT_CONN)
    args = parser.parse_args()

    conn = pyodbc.connect(args.conn, autocommit=False)
    cur = conn.cursor()

    cur.execute(
        """
        SELECT i.Id, i.Ranking, s.Horizonte
        FROM app.RankingItems i
        JOIN app.RankingSnapshots s ON s.Id = i.SnapshotId
        """
    )
    filas = cur.fetchall()

    por_banda: dict[str, list[int]] = {}
    for row in filas:
        item_id, ranking, horizonte = row
        banda = banda_por_acierto(int(ranking), str(horizonte))
        por_banda.setdefault(banda, []).append(int(item_id))

    total = 0
    resumen: dict[str, int] = {}
    for banda, ids in por_banda.items():
        for chunk in _chunks(ids, 500):
            marcadores = ",".join("?" for _ in chunk)
            cur.execute(
                f"UPDATE app.RankingItems SET Banda = ? WHERE Id IN ({marcadores})",
                banda,
                *chunk,
            )
            total += cur.rowcount
        resumen[banda] = resumen.get(banda, 0) + len(ids)

    conn.commit()
    conn.close()

    print(f"Filas actualizadas: {total}")
    for banda, cantidad in sorted(resumen.items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {banda}: {cantidad}")


if __name__ == "__main__":
    main()
