"""Construye el dossier del preventor por establecimiento (para los 259 vigentes).

Fuentes (exportadas anonimizadas y copiadas a data/raw/contexto/):
  acc_agg.json     : id_est, total, y22..y25, ult12m   (1 fila/establecimiento)
  acc_forma.json   : id_est, top_forma  ("nombre:conteo|..." top-3)
  acc_zona.json    : id_est, top_zona
  acc_nat.json     : id_est, top_nat
  acc_grav.json    : id_est, top_grav   (top-4)
  acc_narr.json    : id_est, fecha, forma, relato       (hasta 4 recientes/est)
  vis_agg.json     : id_est, total_real, ultima         (1 fila/establecimiento)
  vis_narr_top3.json / vis_narr_top1.json : id_est, fecha, resultado, obs, inc

Salida: data/processed/dossier_preventor.json
  { generado_en, referencia, establecimientos: { id_est: { accidentes, visitas } } }

Solo se conservan los 259 establecimientos objetivo. Textos saneados (sin
dígitos largos, CUIT/CUIL ni emails) para poder resumirlos con un LLM.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "contexto"
PROC = ROOT / "data" / "processed"
REFERENCIA = date(2025, 11, 30)

_EMAIL = re.compile(r"[\w.\-]+@[\w.\-]+", re.IGNORECASE)
_CUIT = re.compile(r"\b\d{2}[-\s]?\d{7,8}[-\s]?\d\b")
_DIGITS = re.compile(r"\d{7,}")
_MULTISPACE = re.compile(r"\s+")


def sanitize(text, max_len: int = 400):
    if not text:
        return None
    t = _EMAIL.sub("[email]", str(text))
    t = _CUIT.sub("[id]", t)
    t = _DIGITS.sub("[nro]", t)
    t = _MULTISPACE.sub(" ", t).strip()
    return t[:max_len] or None


def load_rows(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text).get("data") or []
    except json.JSONDecodeError:
        arr_start = text.find("[", text.find('"data"'))
        cut = text.rfind("\n    }")
        body = text[arr_start + 1 : cut + len("\n    }")].rstrip().rstrip(",")
        rows = json.loads("[" + body + "]")
        print(f"  [salvage] {path.name}: {len(rows)} registros recuperados de JSON truncado")
        return rows


def index_by_est(rows: list[dict]) -> dict[str, dict]:
    return {r["id_est"]: r for r in rows if r.get("id_est")}


_JUNK = ("error 50", "no corresponde", "invalid", "codigo de nat")


def clean_cat(name):
    if not name:
        return None
    n = _MULTISPACE.sub(" ", str(name)).strip()
    low = n.lower()
    if not n or any(j in low for j in _JUNK):
        return None
    return n


def parse_top(value) -> list[dict]:
    """'nombre:conteo|nombre:conteo' -> [{k,n}, ...]."""
    if not value:
        return []
    out = []
    for part in str(value).split("|"):
        if ":" not in part:
            continue
        name, _, cnt = part.rpartition(":")
        name = clean_cat(name)
        try:
            n = int(cnt)
        except ValueError:
            continue
        if name:
            out.append({"k": name, "n": n})
    return out


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def main() -> None:
    targets = set(json.loads((PROC / "_target_hashes.json").read_text("utf-8")))

    acc_agg = index_by_est(load_rows(RAW / "acc_agg.json"))
    forma = index_by_est(load_rows(RAW / "acc_forma.json"))
    zona = index_by_est(load_rows(RAW / "acc_zona.json"))
    nat = index_by_est(load_rows(RAW / "acc_nat.json"))
    grav = index_by_est(load_rows(RAW / "acc_grav.json"))
    vis_agg = index_by_est(load_rows(RAW / "vis_agg.json"))

    # Relatos de accidentes recientes por establecimiento.
    acc_narr: dict[str, list] = defaultdict(list)
    for r in load_rows(RAW / "acc_narr.json"):
        est = r.get("id_est")
        if est:
            acc_narr[est].append(r)

    # Notas de visita: fusiono top-3 (parcial) + top-1 (cobertura total).
    vis_notes: dict[str, dict] = defaultdict(dict)  # est -> {clave: row}
    for src in ("vis_narr_top3.json", "vis_narr_top1.json"):
        for r in load_rows(RAW / src):
            est = r.get("id_est")
            if not est:
                continue
            clave = (r.get("fecha"), (r.get("obs") or "")[:40])
            vis_notes[est].setdefault(clave, r)

    establecimientos = {}
    for est in targets:
        a = acc_agg.get(est)
        accidentes = None
        if a:
            narr = sorted(
                acc_narr.get(est, []),
                key=lambda r: parse_date(r.get("fecha")) or date.min,
                reverse=True,
            )[:4]
            accidentes = {
                "total": a.get("total") or 0,
                "ultimos_12m": a.get("ult12m") or 0,
                "por_anio": {
                    "2022": a.get("y22") or 0,
                    "2023": a.get("y23") or 0,
                    "2024": a.get("y24") or 0,
                    "2025": a.get("y25") or 0,
                },
                "top_forma": parse_top(forma.get(est, {}).get("top_forma")),
                "top_zona": parse_top(zona.get(est, {}).get("top_zona")),
                "top_naturaleza": parse_top(nat.get(est, {}).get("top_nat")),
                "top_gravedad": parse_top(grav.get(est, {}).get("top_grav")),
                "recientes": [
                    {
                        "fecha": r.get("fecha"),
                        "forma": clean_cat(r.get("forma")),
                        "relato": sanitize(r.get("relato"), 360),
                    }
                    for r in narr
                ],
            }

        v = vis_agg.get(est)
        visitas = None
        if v or est in vis_notes:
            notas = sorted(
                vis_notes.get(est, {}).values(),
                key=lambda r: parse_date(r.get("fecha")) or date.min,
                reverse=True,
            )[:3]
            visitas = {
                "total": (v or {}).get("total_real") or 0,
                "ultima_fecha": (v or {}).get("ultima"),
                "recientes": [
                    {
                        "fecha": r.get("fecha"),
                        "resultado": r.get("resultado"),
                        "observaciones": sanitize(r.get("obs"), 300),
                        "incumplimientos": sanitize(r.get("inc"), 300),
                    }
                    for r in notas
                ],
            }

        establecimientos[est] = {"accidentes": accidentes, "visitas": visitas}

    con_acc = sum(1 for e in establecimientos.values() if e["accidentes"])
    con_vis = sum(1 for e in establecimientos.values() if e["visitas"])
    payload = {
        "generado_en": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "referencia": REFERENCIA.isoformat(),
        "fuente": "export anonimizado por hash de establecimiento",
        "establecimientos": establecimientos,
    }
    out = PROC / "dossier_preventor.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"OK dossier: {con_acc}/{len(targets)} con accidentes, {con_vis}/{len(targets)} con visitas")
    print(f"escrito: {out} ({out.stat().st_size/1024:.1f} KB)")


if __name__ == "__main__":
    main()
