"""Aplica un archivo .sql (batches separados por líneas GO) a PfiPrevencion."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import pyodbc

DEFAULT_CONN = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=PfiPrevencion;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)


def _split_batches(sql: str) -> list[str]:
    parts = re.split(r"(?im)^\s*GO\s*$", sql)
    return [p.strip() for p in parts if p.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Ejecuta un .sql por batches GO")
    parser.add_argument("--file", type=Path, required=True)
    parser.add_argument("--conn", default=DEFAULT_CONN)
    args = parser.parse_args()

    sql = args.file.read_text(encoding="utf-8")
    batches = _split_batches(sql)
    conn = pyodbc.connect(args.conn, autocommit=True)
    cur = conn.cursor()
    try:
        for i, batch in enumerate(batches, 1):
            cur.execute(batch)
            print(f"[ok] batch {i}/{len(batches)}", flush=True)
    finally:
        conn.close()
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
