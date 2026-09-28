"""Aplica sql/app/08_copiloto_cache.sql sobre PfiPrevencion."""
from pathlib import Path

import pyodbc

ROOT = Path(__file__).resolve().parents[2]
DDL = ROOT / "sql" / "app" / "08_copiloto_cache.sql"
APP_CONN = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;DATABASE=PfiPrevencion;"
    "Trusted_Connection=yes;TrustServerCertificate=yes;"
)


def main() -> None:
    sql = DDL.read_text(encoding="utf-8")
    cn = pyodbc.connect(APP_CONN, autocommit=True)
    cur = cn.cursor()
    for batch in [b.strip() for b in sql.replace("\r\n", "\n").split("\nGO") if b.strip()]:
        cur.execute(batch)
    cur.execute(
        "SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_SCHEMA='app' AND TABLE_NAME='CopilotoRespuestaCache'"
    )
    print("CopilotoRespuestaCache:", cur.fetchone()[0])
    cn.close()


if __name__ == "__main__":
    main()
