"""Siembra visitas de agenda demo asignadas al preventor (Prevencionista Demo).

Toma los primeros establecimientos del snapshot vigente 1m y crea visitas
'programada' con fechas futuras, para que al iniciar sesión como
prevencionista@pfi.local se vean 'Mis visitas'.

Idempotente: no crea una visita si el establecimiento ya tiene una programada.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pyodbc

APP_CONN = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;DATABASE=PfiPrevencion;"
    "Trusted_Connection=yes;TrustServerCertificate=yes;"
)
CANTIDAD = 10


def main() -> None:
    cn = pyodbc.connect(APP_CONN, autocommit=False)
    cur = cn.cursor()

    cur.execute(
        "SELECT TOP 1 Id, Nombre FROM app.Usuarios WHERE Email = 'prevencionista@pfi.local' AND Activo = 1"
    )
    row = cur.fetchone()
    if not row:
        raise SystemExit("No existe el usuario prevencionista@pfi.local (arrancá la API una vez para el seed).")
    usuario_id, usuario_nombre = row

    cur.execute(
        """
        SELECT TOP 1 Id, Periodo, Horizonte FROM app.RankingSnapshots
        WHERE EsVigente = 1 AND Horizonte = '1m'
        ORDER BY Periodo DESC
        """
    )
    snap = cur.fetchone()
    if not snap:
        raise SystemExit("No hay snapshot vigente 1m.")
    snapshot_id, periodo, horizonte = snap

    cur.execute(
        """
        SELECT TOP (?) Id, IdEstablecimiento, Ranking, ScoreRiesgo, Banda, Motivo, ObligacionPrs
        FROM app.RankingItems
        WHERE SnapshotId = ?
        ORDER BY Ranking
        """,
        CANTIDAD,
        snapshot_id,
    )
    items = cur.fetchall()

    now = datetime.now(timezone.utc)
    creadas = 0
    for i, it in enumerate(items):
        (item_id, id_est, ranking, score, banda, motivo, prs) = it
        cur.execute(
            "SELECT COUNT(*) FROM app.AgendaItems WHERE IdEstablecimiento = ? AND Estado = 'programada'",
            id_est,
        )
        if cur.fetchone()[0] > 0:
            continue

        fecha = date.today() + timedelta(days=2 + i * 2)
        motivo_visita = "prs" if prs or (motivo or "").lower().find("prs") >= 0 else "predictivo"
        cur.execute(
            """
            INSERT INTO app.AgendaItems
                (UsuarioId, IdEstablecimiento, Periodo, Horizonte, FechaPlanificada, MotivoVisita,
                 Estado, SnapshotId, SnapshotItemId, RankingOrigen, ScoreOrigen, BandaOrigen, MotivoOrigen,
                 Notas, CreadoEn, ActualizadoEn)
            VALUES (?, ?, ?, ?, ?, ?, 'programada', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            usuario_id,
            id_est,
            periodo,
            horizonte,
            fecha,
            motivo_visita,
            snapshot_id,
            item_id,
            ranking,
            float(score),
            banda,
            motivo,
            "Visita demo asignada por el equipo de coordinación.",
            now,
            now,
        )
        creadas += 1

    cn.commit()
    cn.close()
    print(f"OK seed agenda: {creadas} visitas 'programada' asignadas a {usuario_nombre} (id {usuario_id})")


if __name__ == "__main__":
    main()
