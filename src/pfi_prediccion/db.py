from __future__ import annotations

import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from .config import env_bool, load_env


def build_odbc_connection_string() -> str:
    load_env()

    server = os.environ.get("PFI_SQL_SERVER", "SQLSERVER")
    database = os.environ.get("PFI_SQL_DATABASE", "ART_CORE")
    driver = os.environ.get("PFI_SQL_DRIVER", "ODBC Driver 17 for SQL Server")

    if env_bool("PFI_SQL_TRUSTED_CONNECTION", default=True):
        return (
            f"DRIVER={{{driver}}};"
            f"SERVER={server};"
            f"DATABASE={database};"
            "Trusted_Connection=yes;"
            "TrustServerCertificate=yes;"
        )

    user = os.environ["PFI_SQL_USER"]
    password = os.environ["PFI_SQL_PASSWORD"]
    return (
        f"DRIVER={{{driver}}};"
        f"SERVER={server};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        "TrustServerCertificate=yes;"
    )


def get_engine() -> Engine:
    odbc = build_odbc_connection_string()
    url = f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc)}"
    return create_engine(url)
