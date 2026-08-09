"""Re-etiqueta app.RankingItems.Sector a partir de CiiuDivision con el mapeo
ampliado (features.SECTOR_LABELS). No toca modelo, SHAP ni métricas: solo la
etiqueta legible de rubro que consume la UI (grilla, detalle y estadísticas).
"""

from __future__ import annotations

import argparse

import pyodbc

from _bootstrap import SRC  # noqa: F401

from pfi_prediccion.features import SECTOR_LABELS

DEFAULT_CONN = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=PfiPrevencion;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--conn", default=DEFAULT_CONN)
    args = parser.parse_args()

    conn = pyodbc.connect(args.conn, autocommit=False)
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT CiiuDivision FROM app.RankingItems")
    divisiones = [row[0] for row in cur.fetchall()]

    total = 0
    resumen: dict[str, int] = {}
    for div in divisiones:
        if div is None:
            etiqueta = "Otros"
            cur.execute(
                "UPDATE app.RankingItems SET Sector = ? WHERE CiiuDivision IS NULL",
                etiqueta,
            )
        else:
            clave = "".join(ch for ch in str(div) if ch.isdigit())[:2]
            etiqueta = SECTOR_LABELS.get(clave, "Otros")
            cur.execute(
                "UPDATE app.RankingItems SET Sector = ? WHERE CiiuDivision = ?",
                etiqueta,
                div,
            )
        filas = cur.rowcount
        total += filas
        resumen[etiqueta] = resumen.get(etiqueta, 0) + filas

    conn.commit()
    conn.close()

    print(f"Filas actualizadas: {total}")
    for etiqueta, cantidad in sorted(resumen.items(), key=lambda kv: kv[1], reverse=True):
        print(f"  {etiqueta}: {cantidad}")


if __name__ == "__main__":
    main()
