"""Construye el corpus normativo (RGRL PDF + resoluciones SRT) e importa a SQL.

Pasos:
  1) Extrae texto del PDF RGRL (docs/normativa/rgrl-anexo-i.pdf).
  2) Descarga texto oficial de las resoluciones (argentina.gob.ar).
  3) Chunkear con Tema / Actividad / NormaRef.
  4) Escribe data/normativa/chunks.jsonl + docs/normativa/raw/*.txt
  5) Aplica sql/app/07_normativa_chunk.sql e importa a app.NormativaChunk.

Uso:
  python scripts/normativa/build_and_import_corpus.py
  python scripts/normativa/build_and_import_corpus.py --skip-import
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from pypdf import PdfReader

try:
    import pyodbc
except ImportError:  # pragma: no cover
    pyodbc = None  # type: ignore

ROOT = Path(__file__).resolve().parents[2]
NORM_DIR = ROOT / "docs" / "normativa"
RAW_DIR = NORM_DIR / "raw"
DATA_DIR = ROOT / "data" / "normativa"
CHUNKS_PATH = DATA_DIR / "chunks.jsonl"
DDL = ROOT / "sql" / "app" / "07_normativa_chunk.sql"
SOURCES_JSON = NORM_DIR / "sources.json"

APP_CONN = (
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost;DATABASE=PfiPrevencion;"
    "Trusted_Connection=yes;TrustServerCertificate=yes;"
)

UA = (
    "Mozilla/5.0 (compatible; PrevexCorpus/1.0; +https://github.com/)"
    " AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

RESOLUCIONES: list[dict[str, str]] = [
    {
        "id": "srt-463",
        "titulo": "Res. SRT 463/2009 (texto actualizado)",
        "url": "https://www.argentina.gob.ar/normativa/nacional/resolucion-463-2009-153431/actualizacion",
        "tema_default": "visitas_frecuencia",
        "prioridad_arts": "10,11,12,20",
    },
    {
        "id": "srt-741",
        "titulo": "Res. SRT 741/2010 (texto actualizado)",
        "url": "https://www.argentina.gob.ar/normativa/nacional/resolucion-741-2010-167725/actualizacion",
        "tema_default": "rgrl_obligacion",
        "prioridad_arts": "",
    },
    {
        "id": "srt-37",
        "titulo": "Res. SRT 37/2010",
        "url": "https://www.argentina.gob.ar/normativa/nacional/resolucion-37-2010-163171/texto",
        "tema_default": "rar_examenes",
        "prioridad_arts": "",
    },
    {
        "id": "srt-363",
        "titulo": "Res. SRT 363/2016 (PESE)",
        "url": "https://www.argentina.gob.ar/normativa/nacional/265441/texto",
        "tema_default": "pese",
        "prioridad_arts": "",
    },
    {
        "id": "srt-20",
        "titulo": "Res. SRT 20/2018 (PESE-PyMES)",
        "url": "https://www.argentina.gob.ar/normativa/nacional/307746/texto",
        "tema_default": "pese_pyme",
        "prioridad_arts": "",
    },
]

HEADER_NOISE = re.compile(
    r"(Ministerio de Trabajo.*?Superintendencia de Riesgos del Trabajo|"
    r"“2009 - Año de Homenaje.*?Ortiz”|"
    r"rAaAnAntonArgentina”|"
    r"^\s*ANEXO I\s*$)",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)

ACTIVIDAD_MARKERS = [
    (re.compile(r"DECRETO\s*351", re.I), "industria"),
    (re.compile(r"DECRETO\s*911", re.I), "obra"),
    (re.compile(r"DECRETO\s*617", re.I), "agro"),
]
ART_SPLIT = re.compile(
    r"(?m)^(?P<head>(?:Art(?:[íi]culo|\.)|ART[ÍI]CULO)\s*"
    r"(?P<num>\d+[°ºoªa]?(?:\s*bis)?)\s*[.\-—:]?\s*)",
    re.IGNORECASE,
)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "nav", "footer", "header"}:
            self._skip += 1
        if tag in {"p", "br", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self._parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "nav", "footer", "header"} and self._skip:
            self._skip -= 1
        if tag in {"p", "div", "li", "tr", "h1", "h2", "h3", "h4"}:
            self._parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = data.strip()
        if text:
            self._parts.append(text + " ")

    def text(self) -> str:
        raw = "".join(self._parts)
        raw = re.sub(r"[ \t]+", " ", raw)
        raw = re.sub(r"\n{3,}", "\n\n", raw)
        return raw.strip()


def fetch_url(url: str) -> str:
    req = Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urlopen(req, timeout=60) as resp:
        data = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
    html = data.decode(charset, errors="replace")
    parser = _TextExtractor()
    parser.feed(html)
    text = parser.text()
    # Recortar ruido típico del portal
    for marker in ("Acerca de esta norma", "Scroll hacia arriba", '{"@context"'):
        idx = text.find(marker)
        if idx > 200:
            text = text[:idx].strip()
    return text


def extract_pdf(path: Path) -> str:
    reader = PdfReader(str(path))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    text = "\n".join(pages)
    text = HEADER_NOISE.sub("\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _norm_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def chunk_rgrl(text: str) -> list[dict[str, Any]]:
    """Chunkea el Anexo I RGRL por sección temática e ítems numerados."""
    chunks: list[dict[str, Any]] = []
    orden = 0

    # Intro / reglas generales (antes del primer checklist)
    intro_end = re.search(
        r"ESTADO DE CUMPLIMIENTO EN EL ESTABLECIMIENTO",
        text,
        re.I,
    )
    if intro_end:
        intro = _norm_ws(text[: intro_end.start()])
        if len(intro) > 80:
            orden += 1
            chunks.append(
                {
                    "sourceId": "rgrl",
                    "titulo": "RGRL — reglas generales del relevamiento",
                    "texto": intro[:3500],
                    "tema": "rgrl_obligacion",
                    "actividad": None,
                    "normaRef": "Anexo I RGRL (Res. SRT 463/2009)",
                    "orden": orden,
                }
            )

    actividad = "industria"
    # Dividir por marcadores de decreto
    parts: list[tuple[str, str]] = []
    matches = list(
        re.finditer(
            r"ESTADO DE CUMPLIMIENTO.*?NORMATIVA VIGENTE\s*\((DECRETO\s*\d+/[^\)]+)\)",
            text,
            re.I | re.S,
        )
    )
    if not matches:
        # fallback: un solo bloque industria
        parts = [("industria", text)]
    else:
        for i, m in enumerate(matches):
            dec = m.group(1).upper()
            act = "industria"
            for pat, name in ACTIVIDAD_MARKERS:
                if pat.search(dec):
                    act = name
                    break
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            parts.append((act, text[start:end]))

    for act, block in parts:
        actividad = act
        # Planillas A/B/C al final suelen ser listados de sustancias
        if re.search(r"PLANILLA\s+[ABC]\b", block, re.I) and not re.search(
            r"^\d{1,3}\s+¿", block, re.M
        ):
            orden += 1
            chunks.append(
                {
                    "sourceId": "rgrl",
                    "titulo": f"RGRL {act} — planillas de sustancias / agentes",
                    "texto": _norm_ws(block)[:4000],
                    "tema": "rgrl_checklist",
                    "actividad": act,
                    "normaRef": f"Anexo I RGRL ({act})",
                    "orden": orden,
                }
            )
            continue

        # Extraer ítems numerados
        items = []
        for m in re.finditer(
            r"^(?P<num>\d{1,3})\s+(?P<body>.+?)(?=^\d{1,3}\s+|\Z)",
            block,
            flags=re.M | re.S,
        ):
            body = _norm_ws(m.group("body"))
            if len(body) < 15:
                continue
            # Filtrar basura de encabezados repetidos
            if "Ministerio de Trabajo" in body or "rAaAnAntonArgentina" in body:
                continue
            items.append((int(m.group("num")), body))

        if not items:
            # Guardar bloque resumido
            clean = _norm_ws(block)
            if len(clean) > 100:
                orden += 1
                chunks.append(
                    {
                        "sourceId": "rgrl",
                        "titulo": f"RGRL {act} — bloque",
                        "texto": clean[:4000],
                        "tema": "rgrl_checklist",
                        "actividad": act,
                        "normaRef": f"Anexo I RGRL ({act})",
                        "orden": orden,
                    }
                )
            continue

        # Agrupar de a ~6 ítems, intentando cortar en cambios de sección
        group: list[tuple[int, str]] = []
        section_hint = f"cumplimiento Dec. ({act})"

        def flush(hint: str) -> None:
            nonlocal orden, group
            if not group:
                return
            nums = [n for n, _ in group]
            texto = "\n".join(f"{n}. {b}" for n, b in group)
            orden += 1
            n0, n1 = nums[0], nums[-1]
            chunks.append(
                {
                    "sourceId": "rgrl",
                    "titulo": f"RGRL {act} — {hint} (ítems {n0}–{n1})"[:200],
                    "texto": texto[:4500],
                    "tema": "rgrl_checklist",
                    "actividad": act,
                    "normaRef": f"Anexo I RGRL ({act}) ítems {n0}–{n1}",
                    "orden": orden,
                }
            )
            group = []

        last_num = None
        for num, body in items:
            # Detectar salto de sección por salto grande de numeración o reset
            if last_num is not None and (num < last_num or num - last_num > 8):
                flush(section_hint)
            # Heurística de título de sección: cuerpo corto en mayúsculas sin ¿
            if "¿" not in body and body.isupper() and len(body) < 80:
                flush(section_hint)
                section_hint = body.title()[:60]
                last_num = num
                continue
            # Prefijo de sección pegado al ítem (ej. "HERRAMIENTAS 7 ¿Las...")
            sec_m = re.match(
                r"^([A-ZÁÉÍÓÚÜÑ /()\-]{4,60}?)\s+(\d+)\s+(¿.+)$",
                body,
            )
            if sec_m and "¿" in body:
                flush(section_hint)
                section_hint = sec_m.group(1).title()[:60]
                group.append((int(sec_m.group(2)), sec_m.group(3)))
            else:
                group.append((num, body))
            if len(group) >= 6:
                flush(section_hint)
            last_num = num
        flush(section_hint)

    return chunks


def _tema_for_art(source_id: str, art_num: str, default: str, text: str) -> str:
    t = text.lower()
    if source_id == "srt-463":
        if art_num.rstrip("°ºoa ") in {"10", "11", "12"}:
            return "visitas_frecuencia"
        if art_num.rstrip("°ºoa ") == "20":
            return "rgrl_obligacion"
        if "derogado" in t and len(t) < 280:
            return "general"
    if source_id in {"srt-363", "srt-20"}:
        if any(k in t for k in ("visita", "p.r.s", "prs", "ige", "plan de reducción")):
            return default
    if source_id == "srt-741" and "relevamiento" in t:
        return "rgrl_obligacion"
    if source_id == "srt-37":
        return "rar_examenes"
    return default


def chunk_resolucion(source: dict[str, str], text: str) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    sid = source["id"]
    default_tema = source["tema_default"]
    prioridad = {
        x.strip()
        for x in source.get("prioridad_arts", "").split(",")
        if x.strip()
    }

    # Intro corta (título + objeto)
    head = text[:1200]
    orden = 1
    chunks.append(
        {
            "sourceId": sid,
            "titulo": f"{source['titulo']} — objeto",
            "texto": _norm_ws(head)[:2000],
            "tema": default_tema if sid != "srt-463" else "general",
            "actividad": None,
            "normaRef": source["titulo"],
            "orden": orden,
        }
    )

    parts = list(ART_SPLIT.finditer(text))
    if not parts:
        orden += 1
        chunks.append(
            {
                "sourceId": sid,
                "titulo": source["titulo"],
                "texto": _norm_ws(text)[:4500],
                "tema": default_tema,
                "actividad": None,
                "normaRef": source["titulo"],
                "orden": orden,
            }
        )
        return chunks

    for i, m in enumerate(parts):
        start = m.start()
        end = parts[i + 1].start() if i + 1 < len(parts) else len(text)
        body = _norm_ws(text[start:end])
        art_num = re.sub(r"[^\d]", "", m.group("num")) or m.group("num")
        # Saltar considerandos / basura muy corta de derogados salvo prioridad
        is_derogado = "artículo derogado" in body.lower() or body.lower().startswith(
            "art."
        ) and "derogado" in body.lower()
        if is_derogado and art_num not in prioridad:
            continue
        if len(body) < 40:
            continue
        # Para 463: preferir artículos prioritarios; incluir otros operativos no derogados
        if sid == "srt-463" and prioridad and art_num not in prioridad:
            if is_derogado:
                continue
            # Mantener arts. relevantes de prevención (22 registro, etc.) si son cortos
            if art_num not in {"22", "23", "25"} and len(body) > 900:
                # truncar anexos enormes
                body = body[:900] + "…"

        tema = _tema_for_art(sid, art_num, default_tema, body)
        orden += 1
        # Partir artículos muy largos
        pieces = [body]
        if len(body) > 4200:
            pieces = []
            step = 3800
            for j in range(0, len(body), step):
                pieces.append(body[j : j + step])
        for k, piece in enumerate(pieces):
            suffix = f" (parte {k + 1})" if len(pieces) > 1 else ""
            chunks.append(
                {
                    "sourceId": sid,
                    "titulo": f"{source['titulo']} — art. {art_num}{suffix}"[:200],
                    "texto": piece,
                    "tema": tema,
                    "actividad": None,
                    "normaRef": f"{source['titulo']} art. {art_num}",
                    "orden": orden + k,
                }
            )
        orden += max(0, len(pieces) - 1)

    return chunks


def apply_ddl(cur) -> None:
    sql = DDL.read_text(encoding="utf-8")
    batches = [b.strip() for b in sql.replace("\r\n", "\n").split("\nGO") if b.strip()]
    for batch in batches:
        cur.execute(batch)


def import_sql(chunks: list[dict[str, Any]]) -> int:
    if pyodbc is None:
        raise RuntimeError("pyodbc no disponible")
    cn = pyodbc.connect(APP_CONN, autocommit=False)
    cur = cn.cursor()
    apply_ddl(cur)
    cn.commit()
    cur.execute("DELETE FROM app.NormativaChunk")
    rows = [
        (
            c["sourceId"],
            c["titulo"][:200],
            c["texto"],
            c["tema"][:64],
            c.get("actividad"),
            (c.get("normaRef") or "")[:120] or None,
            int(c["orden"]),
            1,
        )
        for c in chunks
    ]
    cur.fast_executemany = False
    cur.executemany(
        """
        INSERT INTO app.NormativaChunk
            (SourceId, Titulo, Texto, Tema, Actividad, NormaRef, Orden, Activo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    cn.commit()
    cur.execute("SELECT COUNT(*) FROM app.NormativaChunk")
    total = cur.fetchone()[0]
    cn.close()
    return int(total)


def update_sources_json() -> None:
    today = date.today().isoformat()
    payload = json.loads(SOURCES_JSON.read_text(encoding="utf-8"))
    for s in payload.get("sources", []):
        s["fecha_captura"] = today
    SOURCES_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-import", action="store_true")
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    all_chunks: list[dict[str, Any]] = []

    pdf = NORM_DIR / "rgrl-anexo-i.pdf"
    if not pdf.exists():
        print(f"ERROR: falta {pdf}", file=sys.stderr)
        return 1
    print(f"[rgrl] extrayendo {pdf.name}…")
    rgrl_text = extract_pdf(pdf)
    (RAW_DIR / "rgrl-anexo-i.txt").write_text(rgrl_text, encoding="utf-8")
    rgrl_chunks = chunk_rgrl(rgrl_text)
    print(f"[rgrl] {len(rgrl_chunks)} chunks")
    all_chunks.extend(rgrl_chunks)

    for src in RESOLUCIONES:
        print(f"[{src['id']}] descargando {src['url']}…")
        try:
            text = fetch_url(src["url"])
        except Exception as ex:  # noqa: BLE001
            print(f"[{src['id']}] FALLO fetch: {ex}", file=sys.stderr)
            return 1
        (RAW_DIR / f"{src['id']}.txt").write_text(text, encoding="utf-8")
        print(f"[{src['id']}] {len(text)} chars")
        ch = chunk_resolucion(src, text)
        print(f"[{src['id']}] {len(ch)} chunks")
        all_chunks.extend(ch)

    # Reasignar orden global estable
    for i, c in enumerate(all_chunks, start=1):
        c["orden"] = i

    with CHUNKS_PATH.open("w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"OK chunks → {CHUNKS_PATH} ({len(all_chunks)})")

    update_sources_json()

    by_src: dict[str, int] = {}
    by_tema: dict[str, int] = {}
    for c in all_chunks:
        by_src[c["sourceId"]] = by_src.get(c["sourceId"], 0) + 1
        by_tema[c["tema"]] = by_tema.get(c["tema"], 0) + 1
    print("por fuente:", by_src)
    print("por tema:", by_tema)

    if args.skip_import:
        print("skip import SQL")
        return 0

    try:
        total = import_sql(all_chunks)
        print(f"OK import SQL: {total} filas en app.NormativaChunk")
    except Exception as ex:  # noqa: BLE001
        print(f"WARN import SQL falló: {ex}", file=sys.stderr)
        print("Los chunks quedaron en JSONL; reintentar import luego.")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
