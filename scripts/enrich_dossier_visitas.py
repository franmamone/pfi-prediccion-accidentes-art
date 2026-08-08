"""Enriquece el dossier con los incumplimientos de TODAS las visitas.

Problema: cada visita registra la lista completa de incumplimientos de ese
momento, pero en el dossier original solo se guardaban 1-3 visitas de ejemplo
(y cada texto quedaba truncado). Para que el resumen IA use toda la información
de visitas previas, acá se agregan por establecimiento los incumplimientos
DISTINTOS (deduplicados), con su frecuencia (en cuántas visitas aparecieron) y
la última fecha en que se registraron, más las observaciones distintas.

Fuentes (data/raw/contexto/): visitas_raw.json (muestra amplia de visitas con
`incumplimientos_texto`), vis_narr_top3.json y vis_narr_top1.json (notas por
establecimiento). Se deduplican visitas repetidas entre fuentes.

Salida: reescribe data/processed/dossier_preventor.json agregando en cada
`visitas`:
  - incumplimientos_frecuentes: [{k, n, ultima}]  (ordenado por frecuencia)
  - observaciones: [texto, ...]  (distintas, recientes)
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "contexto"
PROC = ROOT / "data" / "processed"
DOSSIER = PROC / "dossier_preventor.json"

_EMAIL = re.compile(r"[\w.\-]+@[\w.\-]+", re.IGNORECASE)
_CUIT = re.compile(r"\b\d{2}[-\s]?\d{7,8}[-\s]?\d\b")
_DIGITS = re.compile(r"\d{7,}")
_WS = re.compile(r"\s+")
_JUNK = ("error 50", "no corresponde", "invalid", "codigo de nat")

MAX_INCUMPLIMIENTOS = 25
MAX_OBSERVACIONES = 4


def sanitize(text, max_len: int = 200):
    if not text:
        return None
    t = _EMAIL.sub("[email]", str(text))
    t = _CUIT.sub("[id]", t)
    t = _DIGITS.sub("[nro]", t)
    t = _WS.sub(" ", t).strip()
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


def parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def norm_item(s) -> str | None:
    n = _WS.sub(" ", str(s)).strip()
    low = n.lower()
    if not n or any(j in low for j in _JUNK):
        return None
    return n


def collect_visits() -> dict:
    """Devuelve visitas únicas: clave -> {est, fecha, inc, obs}."""
    visits: dict = {}

    def add(est, fecha, inc, obs):
        if not est:
            return
        key = (est, fecha, (inc or "")[:60], (obs or "")[:40])
        visits.setdefault(key, {"est": est, "fecha": fecha, "inc": inc, "obs": obs})

    for r in load_rows(RAW / "visitas_raw.json"):
        add(r.get("id_est"), r.get("fecha"), r.get("incumplimientos_texto"), r.get("observaciones"))
    for src in ("vis_narr_top3.json", "vis_narr_top1.json"):
        for r in load_rows(RAW / src):
            add(r.get("id_est"), r.get("fecha"), r.get("inc"), r.get("obs"))
    return visits


def main() -> None:
    dossier = json.loads(DOSSIER.read_text(encoding="utf-8"))
    ests = dossier.get("establecimientos") or {}
    visits = collect_visits()

    inc_agg: dict = defaultdict(lambda: defaultdict(lambda: {"n": 0, "ultima": None}))
    obs_agg: dict = defaultdict(list)

    for v in visits.values():
        est = v["est"]
        d = parse_date(v["fecha"])
        items = set()
        if v["inc"]:
            for part in str(v["inc"]).split("|"):
                it = norm_item(part)
                if it:
                    items.add(it)
        for it in items:
            cell = inc_agg[est][it]
            cell["n"] += 1
            if d and (cell["ultima"] is None or d > cell["ultima"]):
                cell["ultima"] = d
        if v["obs"]:
            o = sanitize(v["obs"], 240)
            if o:
                obs_agg[est].append((d or date.min, o))

    updated = 0
    for est, data in ests.items():
        vis = data.get("visitas")
        if not vis:
            if est not in inc_agg and est not in obs_agg:
                continue
            vis = {"total": 0}
            data["visitas"] = vis

        items = inc_agg.get(est, {})
        frec = sorted(
            items.items(),
            key=lambda kv: (kv[1]["n"], kv[1]["ultima"] or date.min),
            reverse=True,
        )
        incumplimientos = []
        for k, c in frec[:MAX_INCUMPLIMIENTOS]:
            sk = sanitize(k, 180)
            if sk:
                incumplimientos.append(
                    {"k": sk, "n": c["n"], "ultima": c["ultima"].isoformat() if c["ultima"] else None}
                )
        vis["incumplimientos_frecuentes"] = incumplimientos

        seen = set()
        obs_list = []
        for _, o in sorted(obs_agg.get(est, []), key=lambda x: x[0], reverse=True):
            key = o[:60].lower()
            if key in seen:
                continue
            seen.add(key)
            obs_list.append(o)
            if len(obs_list) >= MAX_OBSERVACIONES:
                break
        vis["observaciones"] = obs_list
        updated += 1

    con_inc = sum(
        1
        for e in ests.values()
        if (e.get("visitas") or {}).get("incumplimientos_frecuentes")
    )
    DOSSIER.write_text(json.dumps(dossier, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        f"OK enrich: {updated} establecimientos procesados; "
        f"{con_inc} con incumplimientos agregados; {len(visits)} visitas únicas usadas"
    )


if __name__ == "__main__":
    main()
