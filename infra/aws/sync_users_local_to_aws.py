"""Copia usuarios reales (con MFA) y su disponibilidad desde SQL local a AWS (túnel :14333)."""

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

# Cuentas reales usadas en local (no demos prev.*)
REAL_EMAILS = (
    "usuario@ejemplo.local",
    "usuario@uade.local",
    "usuario@ejemplo.local",
)

USER_COLS = [
    "Email", "Nombre", "PasswordHash", "Rol", "ZonaId", "Activo", "CreadoEn",
    "Latitud", "Longitud", "MfaEnabled", "MfaSecret", "MfaConfirmedEn",
    "DebeCambiarPassword", "MfaRecoveryHashes", "MfaRequired",
]


def main() -> int:
    src = pyodbc.connect(LOCAL)
    dst = pyodbc.connect(AWS, autocommit=False)
    sc, dc = src.cursor(), dst.cursor()

    placeholders = ",".join("?" for _ in REAL_EMAILS)
    sc.execute(
        f"SELECT Id, {','.join(USER_COLS)} FROM app.Usuarios WHERE Email IN ({placeholders})",
        REAL_EMAILS,
    )
    rows = sc.fetchall()
    if len(rows) != len(REAL_EMAILS):
        found = {r[1] for r in rows}
        missing = set(REAL_EMAILS) - found
        print("Missing locally:", missing)
        return 1

    # Zona en AWS (si existe)
    dc.execute("SELECT TOP 1 Id FROM app.Zonas")
    zona = dc.fetchone()
    zona_id = zona[0] if zona else None

    id_map: dict[int, int] = {}
    for r in rows:
        local_id = int(r[0])
        data = list(r[1:])
        # index of ZonaId in USER_COLS = 4
        if data[4] is not None and zona_id is not None:
            data[4] = zona_id
        email = data[0]
        dc.execute("SELECT Id FROM app.Usuarios WHERE Email = ?", email)
        existing = dc.fetchone()
        if existing:
            uid = int(existing[0])
            sets = ", ".join(f"{c} = ?" for c in USER_COLS if c != "Email")
            vals = [data[USER_COLS.index(c)] for c in USER_COLS if c != "Email"]
            dc.execute(f"UPDATE app.Usuarios SET {sets} WHERE Id = ?", (*vals, uid))
            print(f"UPDATE {email} -> Id={uid}")
        else:
            cols = ", ".join(USER_COLS)
            q = ",".join("?" for _ in USER_COLS)
            dc.execute(
                f"INSERT INTO app.Usuarios ({cols}) OUTPUT INSERTED.Id VALUES ({q})",
                data,
            )
            uid = int(dc.fetchone()[0])
            print(f"INSERT {email} -> Id={uid}")
        id_map[local_id] = uid

    dst.commit()

    # Disponibilidad
    for local_id, aws_id in id_map.items():
        dc.execute("DELETE FROM app.UsuarioDisponibilidad WHERE UsuarioId = ?", aws_id)
        sc.execute(
            "SELECT DiaSemana, HoraDesde, HoraHasta FROM app.UsuarioDisponibilidad WHERE UsuarioId = ?",
            local_id,
        )
        disp = sc.fetchall()
        for d in disp:
            dc.execute(
                "INSERT INTO app.UsuarioDisponibilidad (UsuarioId, DiaSemana, HoraDesde, HoraHasta) VALUES (?,?,?,?)",
                (aws_id, d[0], d[1], d[2]),
            )
        print(f"  disponibilidad usuario {aws_id}: {len(disp)} filas")
    dst.commit()

    dc.execute(
        "SELECT Id, Rol, Email, MfaEnabled, "
        "CASE WHEN MfaSecret IS NULL OR MfaSecret='' THEN 0 ELSE 1 END AS TieneMfa "
        "FROM app.Usuarios ORDER BY Rol, Email"
    )
    print("AWS users:")
    for r in dc.fetchall():
        print(" ", r)
    print("DONE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
