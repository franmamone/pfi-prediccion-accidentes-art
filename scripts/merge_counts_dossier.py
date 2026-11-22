"""Fusiona conteos de accidentes (por año) al dossier del preventor.

Preserva los dossiers completos existentes (259) y agrega, para los
establecimientos objetivo sin datos de accidentes, un bloque de accidentes
"solo conteos" (total, últimos 12m y barras por año). Las categorías y relatos
quedan vacíos: el export de categorías/relatos a escala no se realizó en este paso.

Lee todos los data/raw/contexto/counts/result_*.json (formato {"data":[...]}).
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
COUNTS = ROOT / "data" / "raw" / "contexto" / "counts"
DOSSIER = PROC / "dossier_preventor.json"


def main() -> None:
    payload = json.loads(DOSSIER.read_text(encoding="utf-8"))
    ests = payload.get("establecimientos") or {}

    counts: dict[str, dict] = {}
    for f in sorted(COUNTS.glob("result_*.json")):
        data = json.loads(f.read_text(encoding="utf-8")).get("data") or []
        for r in data:
            est = r.get("id_est")
            if est:
                counts[est] = r

    added = 0
    for est, r in counts.items():
        entry = ests.get(est)
        if entry and (entry.get("accidentes")):
            continue  # ya tiene dossier completo: no tocar
        acc = {
            "total": int(r.get("total") or 0),
            "ultimos_12m": int(r.get("ult12m") or 0),
            "por_anio": {
                "2022": int(r.get("y22") or 0),
                "2023": int(r.get("y23") or 0),
                "2024": int(r.get("y24") or 0),
                "2025": int(r.get("y25") or 0),
            },
            "top_forma": [],
            "top_zona": [],
            "top_naturaleza": [],
            "top_gravedad": [],
            "recientes": [],
        }
        ests[est] = {"accidentes": acc, "visitas": (entry or {}).get("visitas")}
        added += 1

    payload["establecimientos"] = ests
    DOSSIER.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    con_acc = sum(1 for e in ests.values() if e.get("accidentes"))
    print(f"OK merge: +{added} conteos, total con accidentes={con_acc}, total establecimientos={len(ests)}")


if __name__ == "__main__":
    main()
