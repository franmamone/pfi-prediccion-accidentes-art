"""Importa ranking_maestro_*.json a la BD operativa PfiPrevencion (localhost).

Snapshots inmutables: misma ArtifactHash = no-op; hash distinta = nueva versión vigente.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
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


def _artifact_hash(data: dict) -> str:
    existing = data.get("artifact_hash")
    if existing and isinstance(existing, str) and len(existing) == 64:
        return existing
    body = json.dumps(
        {
            "periodo": data.get("periodo"),
            "horizonte": data.get("horizonte"),
            "modelo_version": data.get("modelo_version"),
            "items": [
                {
                    "id": i.get("id_establecimiento"),
                    "ranking": i.get("ranking"),
                    "score": i.get("score_riesgo"),
                }
                for i in (data.get("items") or [])
            ],
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def import_ranking(path: Path, conn: pyodbc.Connection) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    periodo = str(data.get("periodo") or "")
    horizonte = str(data.get("horizonte") or "")
    items = data.get("items") or []
    if not periodo or horizonte not in {"1m", "3m"}:
        raise ValueError(f"JSON inválido en {path}: faltan periodo/horizonte")

    totales = data.get("totales") or {}
    artifact_hash = _artifact_hash(data)
    modelo_version = _as_str(data.get("modelo_version"), 80) or Path(path).name
    datos_hasta = _as_str(data.get("datos_hasta"), 7)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    cur = conn.cursor()

    # Idempotencia: mismo hash ya importado → no-op (reactiva vigencia si hace falta).
    cur.execute(
        """
        SELECT Id, EsVigente
        FROM app.RankingSnapshots
        WHERE Periodo = ? AND Horizonte = ? AND ArtifactHash = ?
        """,
        periodo,
        horizonte,
        artifact_hash,
    )
    existing = cur.fetchone()
    if existing:
        snapshot_id = int(existing[0])
        if not existing[1]:
            cur.execute(
                "UPDATE app.RankingSnapshots SET EsVigente = 0 WHERE Horizonte = ?",
                horizonte,
            )
            cur.execute(
                """
                UPDATE app.RankingSnapshots
                SET EsVigente = 1, ActivadoEn = ?
                WHERE Id = ?
                """,
                now,
                snapshot_id,
            )
            conn.commit()
        return {
            "archivo": str(path),
            "periodo": periodo,
            "horizonte": horizonte,
            "snapshot_id": snapshot_id,
            "accion": "noop_mismo_hash",
            "items": 0,
            "contribuciones": 0,
            "shap_agregados": 0,
        }

    # Nueva versión: desactivar vigentes del horizonte, insertar snapshot nuevo (sin borrar).
    cur.execute(
        "UPDATE app.RankingSnapshots SET EsVigente = 0 WHERE Horizonte = ?",
        horizonte,
    )

    universo = int(totales.get("filas") or len(items))
    criticos = int(totales.get("criticos") or sum(1 for i in items if i.get("banda") == "critico"))
    altos = int(totales.get("altos") or sum(1 for i in items if i.get("banda") == "alto"))
    items_importados = len(items)

    cur.execute(
        """
        INSERT INTO app.RankingSnapshots
            (Periodo, Horizonte, ArchivoOrigen, Filas, Criticos, Altos, EsVigente,
             ModeloVersion, ArtifactHash, DatosHasta, ImportadoEn, ActivadoEn,
             UniversoFilas, ItemsImportados)
        OUTPUT INSERTED.Id
        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
        """,
        periodo,
        horizonte,
        str(path.relative_to(REPO_ROOT)).replace("\\", "/"),
        universo,
        criticos,
        altos,
        modelo_version,
        artifact_hash,
        datos_hasta,
        now,
        now,
        universo,
        items_importados,
    )
    snapshot_id = int(cur.fetchone()[0])

    contrib_rows: list[tuple] = []
    items_inserted = 0
    for item in items:
        motivo_principal = _as_str(item.get("motivo_principal"), 500)
        cur.execute(
            """
            INSERT INTO app.RankingItems (
                SnapshotId, IdEstablecimiento, IdEmpleador, Ranking, ScoreRiesgo, Banda,
                Motivo, ObligacionPrs, EnCooldown, UltimaVisitaHaceMeses, Sector, CiiuDivision,
                CantidadCapitas, DotacionNominaMes, AlertaUmbral, MotivoPrincipalTexto
            )
            OUTPUT INSERTED.Id
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
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
            motivo_principal,
        )
        ranking_item_id = int(cur.fetchone()[0])
        items_inserted += 1

        for contrib in item.get("contribuciones") or []:
            shap_val = _as_float(contrib.get("shap_value"))
            if shap_val is None:
                continue
            direccion = _as_str(contrib.get("direccion"), 20) or (
                "aumenta" if shap_val >= 0 else "reduce"
            )
            if direccion not in {"aumenta", "reduce"}:
                direccion = "aumenta" if shap_val >= 0 else "reduce"
            contrib_rows.append(
                (
                    ranking_item_id,
                    int(contrib.get("orden") or 0),
                    _as_str(contrib.get("feature"), 120) or "feature",
                    _as_str(contrib.get("tema"), 80),
                    _as_str(contrib.get("etiqueta"), 200) or "Factor",
                    _as_str(contrib.get("valor_observado"), 200),
                    shap_val,
                    direccion,
                    _as_str(contrib.get("descripcion"), 500),
                )
            )

    if contrib_rows:
        cur.fast_executemany = False
        cur.executemany(
            """
            INSERT INTO app.RankingItemContribuciones (
                RankingItemId, Orden, Feature, Tema, Etiqueta, ValorObservado,
                ShapValue, Direccion, Descripcion
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            contrib_rows,
        )

    shap_agg_rows: list[tuple] = []
    shap_agregados = data.get("shap_agregados") or {}
    for top_key, factors in shap_agregados.items():
        try:
            top_k = int(top_key)
        except (TypeError, ValueError):
            continue
        if top_k not in {50, 225}:
            continue
        for factor in factors or []:
            shap_agg_rows.append(
                (
                    snapshot_id,
                    top_k,
                    _as_str(factor.get("feature"), 120) or "feature",
                    _as_str(factor.get("tema"), 80),
                    _as_str(factor.get("etiqueta"), 200) or "Factor",
                    int(factor.get("orden_importancia") or 0),
                    int(factor.get("items_cohorte") or items_importados),
                    float(factor.get("mean_abs_shap") or 0.0),
                    float(factor.get("mean_shap") or 0.0),
                    _as_float(factor.get("p50_abs_shap")),
                    _as_float(factor.get("p90_abs_shap")),
                    float(factor.get("pct_aumenta") or 0.0),
                    _as_str(factor.get("metodo"), 60) or "matriz_completa",
                    now,
                )
            )

    if shap_agg_rows:
        cur.executemany(
            """
            INSERT INTO app.SnapshotShapAgregados (
                SnapshotId, TopK, Feature, Tema, Etiqueta, OrdenImportancia, ItemsCohorte,
                MeanAbsShap, MeanShap, P50AbsShap, P90AbsShap, PctAumenta, Metodo, GeneradoEn
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            shap_agg_rows,
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
        "accion": "insert_version",
        "artifact_hash": artifact_hash,
        "items": items_inserted,
        "contribuciones": len(contrib_rows),
        "shap_agregados": len(shap_agg_rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa ranking JSON a PfiPrevencion")
    parser.add_argument(
        "--file",
        type=Path,
        action="append",
        dest="files",
        help="Ruta a ranking_maestro_*.json (repetible)",
    )
    parser.add_argument("--conn", default=DEFAULT_CONN, help="Cadena ODBC")
    parser.add_argument(
        "--periodo",
        default=None,
        help="Si no se pasan --file, importa ambos horizontes de este período (ej. 2025-11)",
    )
    args = parser.parse_args()

    files = list(args.files or [])
    if not files:
        periodo = args.periodo or "2025-11"
        files = [
            REPORTS_RANKING_DIR / f"ranking_maestro_1m_{periodo}.json",
            REPORTS_RANKING_DIR / f"ranking_maestro_3m_{periodo}.json",
        ]

    conn = _connect(args.conn)
    try:
        for path in files:
            if not path.exists():
                raise FileNotFoundError(path)
            result = import_ranking(path, conn)
            print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
