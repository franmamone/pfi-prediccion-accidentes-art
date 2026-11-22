# Corpus normativo Prevex (RAG)

Fuentes canónicas para el copiloto y las sugerencias de acta.

## Incluidas

| ID | Archivo esperado | Link / origen |
|----|------------------|---------------|
| `rgrl` | `rgrl-anexo-i.pdf` | PDF local (Anexo I RGRL) |
| `srt-463` | `srt-463-2009-actualizada.pdf` | https://www.argentina.gob.ar/normativa/nacional/resoluci%C3%B3n-463-2009-153431/actualizacion |
| `srt-741` | `srt-741-2010-actualizada.pdf` | https://www.argentina.gob.ar/normativa/nacional/resoluci%C3%B3n-741-2010-167725/actualizacion |
| `srt-37` | `srt-37-2010.pdf` | https://www.argentina.gob.ar/normativa/nacional/resoluci%C3%B3n-37-2010-163171/texto |
| `srt-363` | `srt-363-2016.pdf` | https://www.argentina.gob.ar/normativa/nacional/265441/texto |
| `srt-20` | `srt-20-2018.pdf` | https://www.argentina.gob.ar/normativa/nacional/307746/texto |

## Excluidas

- Res. SRT 48/2025 y ecosistema Prevención 4.0  
- Res. SRT 529/2009 (ya absorbida en 463 actualizada)

## Cómo cargar / regenerar

```bash
# Requiere: docs/normativa/rgrl-anexo-i.pdf + SQL Server PfiPrevencion
python scripts/normativa/build_and_import_corpus.py
```

- Texto crudo: `docs/normativa/raw/*.txt`
- Chunks: `data/normativa/chunks.jsonl`
- Tabla: `app.NormativaChunk` (DDL en `sql/app/07_normativa_chunk.sql`)

El PDF RGRL es la fuente principal del copiloto; las resoluciones se descargan solas desde argentina.gob.ar.
