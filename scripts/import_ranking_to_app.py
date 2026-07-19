"""Importa ranking_maestro_*.json a la BD operativa PfiPrevencion (localhost)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pyodbc

from _bootstrap import SRC  # noqa: F401

from pfi_prediccion.config import REPORTS_RANKING_DIR, REPO_ROOT

DEFAULT_CONN = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;"
    "DATABASE=PfiPrevencion;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)


def _connect(conn_str: str) -> pyodbc.Connection:
    return pyodbc.connect(conn_str, autocommit=False)


def _as_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:  # NaN
        return None
    return number


def _as_str(value: object, max_len: int | None = None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() == "nan":
        return None
    if max_len is not None:
        return text[:max_len]
    return text


def import_ranking(path: Path, conn: pyodbc.Connection) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    periodo = str(data.get("periodo") or "")
    horizonte = str(data.get("horizonte") or "")
    items = data.get("items") or []
    if not periodo or horizonte not in {"1m", "3m"}:
        raise ValueError(f"JSON inválido en {path}: faltan periodo/horizonte")

    totales = data.get("totales") or {}
    cur = conn.cursor()

    cur.execute(
        """
        UPDATE app.RankingSnapshots
        SET EsVigente = 0
        WHERE Periodo = ? AND Horizonte = ?
        """,
        periodo,
        horizonte,
    )
    cur.execute(
        """
        DELETE FROM app.RankingSnapshots
        WHERE Periodo = ? AND Horizonte = ?
        """,
        periodo,
        horizonte,
    )

    cur.execute(
        """
        INSERT INTO app.RankingSnapshots
            (Periodo, Horizonte, ArchivoOrigen, Filas, Criticos, Altos, EsVigente)
        OUTPUT INSERTED.Id
        VALUES (?, ?, ?, ?, ?, ?, 1)
        """,
        periodo,
        horizonte,
        str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
        int(totales.get("filas") or len(items)),
        int(totales.get("criticos") or sum(1 for i in items if i.get("banda") == "critico")),
        int(totales.get("altos") or sum(1 for i in items if i.get("banda") == "alto")),
    )
    snapshot_id = int(cur.fetchone()[0])

    rows = []
    for item in items:
        rows.append(
            (
                snapshot_id,
                str(item["id_establecimiento"]),
                _as_str(item.get("id_empleador"), 64),
                int(item["ranking"]),
                float(item["score_riesgo"]),
                str(item.get("banda") or "medio"),
                _as_str(item.get("motivo"), 80),
                1 if item.get("obligacion_prs") else 0,
                1 if item.get("en_cooldown") else 0,
                _as_float(item.get("ultima_visita_hace_meses")),
                _as_str(item.get("sector"), 120),
                _as_str(item.get("ciiu_seccion"), 10),
                _as_float(item.get("cantidad_capitas")),
                _as_float(item.get("dotacion_nomina_mes")),
                1 if item.get("alerta_umbral") else 0,
                _as_str(item.get("motivo_principal"), 500),
            )
        )

    cur.fast_executemany = False
    cur.executemany(
        """
        INSERT INTO app.RankingItems (
            SnapshotId, IdEstablecimiento, IdEmpleador, Ranking, ScoreRiesgo, Banda,
            Motivo, ObligacionPrs, EnCooldown, UltimaVisitaHaceMeses, Sector, CiiuDivision,
            CantidadCapitas, DotacionNominaMes, AlertaUmbral, MotivoPrincipalTexto
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )

    cur.execute(
        """
        MERGE app.AppConfig AS t
        USING (SELECT ? AS Clave, ? AS Valor) AS s
        ON t.Clave = s.Clave
        WHEN MATCHED THEN UPDATE SET Valor = s.Valor, Actualizado = SYSUTCDATETIME()
        WHEN NOT MATCHED THEN INSERT (Clave, Valor) VALUES (s.Clave, s.Valor);
        """,
        f"periodo_vigente_{horizonte}",
        periodo,
    )
    conn.commit()
    return {
        "archivo": str(path),
        "periodo": periodo,
        "horizonte": horizonte,
        "snapshot_id": snapshot_id,
        "items": len(rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa rankings a PfiPrevencion")
    parser.add_argument(
        "--files",
        nargs="*",
        default=[
            str(REPORTS_RANKING_DIR / "ranking_maestro_1m_2025-10.json"),
            str(REPORTS_RANKING_DIR / "ranking_maestro_3m_2025-08.json"),
        ],
    )
    parser.add_argument("--conn", default=DEFAULT_CONN)
    args = parser.parse_args()

    conn = _connect(args.conn)
    results = []
    try:
        for raw in args.files:
            path = Path(raw)
            if not path.is_absolute():
                path = REPO_ROOT / path
            if not path.exists():
                print(f"[skip] no existe {path}")
                continue
            result = import_ranking(path, conn)
            results.append(result)
            print(
                f"[ok] {result['horizonte']} {result['periodo']}: "
                f"{result['items']} items → snapshot {result['snapshot_id']}"
            )
    finally:
        conn.close()

    if not results:
        raise SystemExit("No se importó ningún ranking.")
    print(json.dumps({"imported": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
