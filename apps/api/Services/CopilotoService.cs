using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Text.RegularExpressions;
using Microsoft.EntityFrameworkCore;
using PfiPrevencion.Api.Data;

namespace PfiPrevencion.Api.Services;

public sealed record CopilotoRequest(string? Pregunta, string? Tema, string? Actividad, bool? Refrescar);

public sealed record CopilotoGuardadoRequest(
    string? Pregunta,
    string? Respuesta,
    string? Tema,
    string? Seccion,
    string? Modelo);

public sealed record CopilotoResponse(
    string Respuesta,
    string Tema,
    string Seccion,
    string? Actividad,
    string Modelo,
    bool SinFundamento,
    bool DesdeCache,
    DateTime? GeneradoEn);

public sealed class CopilotoService(AppDbContext db, GeminiClient gemini)
{
    private static readonly HashSet<string> TemasPermitidos = new(StringComparer.OrdinalIgnoreCase)
    {
        "rgrl_checklist",
        "visitas_frecuencia",
        "rgrl_obligacion",
        "pese",
        "pese_pyme",
        "rar_examenes",
        "accidentes_previos",
        "general",
        "auto",
    };

    private static readonly HashSet<string> SeccionesChip = new(StringComparer.OrdinalIgnoreCase)
    {
        "rgrl_checklist",
        "visitas_frecuencia",
        "rgrl_obligacion",
        "pese",
        "pese_pyme",
        "rar_examenes",
        "accidentes_previos",
    };

    private static readonly (string Tema, string[] Keywords)[] TemaKeywords =
    [
        ("pese", ["pese", "prs", "ige", "siniestralidad elevada", "plan de reducción"]),
        ("pese_pyme", ["pyme", "pymes", "pequeñas y medianas"]),
        ("rar_examenes", ["rar", "examen", "periódico", "periodico", "agente de riesgo", "enfermedad profesional"]),
        ("visitas_frecuencia", ["frecuencia", "cada cuánto", "cada cuanto", "visitar", "cronograma de visita"]),
        ("rgrl_obligacion", ["actualizar rgrl", "presentar rgrl", "renovación", "renovacion", "remitir"]),
        ("rgrl_checklist", ["rgrl", "verificar", "checklist", "andamio", "epp", "higiene", "ruido", "qué mirar", "que mirar", "visita"]),
        ("accidentes_previos", ["accidentes previos", "historial de accidentes", "siniestros previos", "briefing de accidentes"]),
    ];

    private static bool _cacheTableReady;

    public async Task<CopilotoResponse> ResponderAsync(
        string idEstablecimiento,
        CopilotoRequest req,
        CancellationToken ct = default)
    {
        await EnsureCacheTableAsync(ct);

        var pregunta = (req.Pregunta ?? "").Trim();
        if (pregunta.Length < 5)
            throw new ArgumentException("La pregunta es demasiado corta.");
        if (pregunta.Length > 800)
            pregunta = pregunta[..800];

        var tema = InferirTema(req.Tema, pregunta);
        if (!TemasPermitidos.Contains(tema))
            throw new ArgumentException("Tema no permitido para el copiloto normativo.");

        var seccion = ResolverSeccion(req.Tema, pregunta);
        var forzar = req.Refrescar == true;

        if (!forzar)
        {
            var cached = await db.CopilotoRespuestasCache
                .FirstOrDefaultAsync(
                    c => c.IdEstablecimiento == idEstablecimiento && c.Seccion == seccion,
                    ct);
            if (cached is not null)
            {
                return new CopilotoResponse(
                    cached.Respuesta,
                    cached.Tema,
                    cached.Seccion,
                    cached.Actividad,
                    cached.Modelo,
                    cached.SinFundamento,
                    DesdeCache: true,
                    cached.GeneradoEn);
            }
        }

        if (!gemini.Configurado)
            throw new GeminiException("El servicio de IA no está configurado (falta la API key de Gemini).");

        var item = await db.RankingItems.AsNoTracking()
            .Where(i => i.IdEstablecimiento == idEstablecimiento)
            .OrderByDescending(i => i.SnapshotId)
            .Select(i => new { i.Sector, i.CiiuDivision, i.ObligacionPrs, i.Banda, i.Ranking })
            .FirstOrDefaultAsync(ct);

        var actividad = NormalizeActividad(req.Actividad)
            ?? InferirActividad(item?.Sector, item?.CiiuDivision);

        string texto;
        var sinFundamento = false;
        var modeloUsado = gemini.Model;

        // Sección aparte: briefing de accidentes del dossier.
        if (seccion == "accidentes_previos" || tema == "accidentes_previos")
        {
            seccion = "accidentes_previos";
            tema = "accidentes_previos";
            var (dossierRich, tieneDatos) = await BuildAccidentesDossierAsync(idEstablecimiento, ct);
            if (!tieneDatos)
            {
                texto =
                    "No hay historial de accidentes ni visitas cargado para este establecimiento. " +
                    "Sin esos datos no puedo armar un briefing de accidentes previos.";
                sinFundamento = true;
            }
            else
            {
                var prompt = BuildAccidentesPrompt(
                    pregunta, dossierRich, item?.Banda, item?.Ranking, item?.ObligacionPrs == true, actividad);
                var resultado = await gemini.GenerarAsync(prompt, ct);
                texto = LimpiarSalida(resultado.Texto);
                modeloUsado = resultado.Modelo;
            }
        }
        else
        {
            // Contexto rico del establecimiento para anclar chips normativos (no genéricos).
            var (dossierCtx, tieneDossier) = await BuildAccidentesDossierAsync(idEstablecimiento, ct);
            if (dossierCtx.Length > 3200)
                dossierCtx = dossierCtx[..3200] + "…";

            var focusTokens = Tokenizar($"{pregunta}\n{dossierCtx}");
            var temasQuery = TemasParaRetrieve(tema, item?.ObligacionPrs == true);
            var chunks = await RecuperarChunksAsync(temasQuery, actividad, focusTokens, ct);

            if (chunks.Count == 0)
            {
                texto =
                    "No tengo fundamento normativo en el corpus cargado para responder esa consulta. Probá un chip de RGRL, visitas, PESE o RAR.";
                sinFundamento = true;
            }
            else
            {
                var prompt = BuildPrompt(
                    pregunta, tema, actividad, item?.Banda, item?.Ranking,
                    item?.ObligacionPrs == true, chunks, dossierCtx, tieneDossier);
                var resultado = await gemini.GenerarAsync(prompt, ct);
                texto = LimpiarSalida(resultado.Texto);
                modeloUsado = resultado.Modelo;
            }
        }

        var row = await db.CopilotoRespuestasCache
            .FirstOrDefaultAsync(
                c => c.IdEstablecimiento == idEstablecimiento && c.Seccion == seccion,
                ct);
        if (row is null)
        {
            row = new CopilotoRespuestaCache
            {
                IdEstablecimiento = idEstablecimiento,
                Seccion = seccion,
            };
            db.CopilotoRespuestasCache.Add(row);
        }

        row.Pregunta = pregunta;
        row.Tema = tema;
        row.Actividad = actividad;
        row.Respuesta = texto;
        row.Modelo = modeloUsado;
        row.SinFundamento = sinFundamento;
        row.GeneradoEn = DateTime.UtcNow;
        await db.SaveChangesAsync(ct);

        return new CopilotoResponse(
            texto,
            tema,
            seccion,
            actividad,
            modeloUsado,
            sinFundamento,
            DesdeCache: false,
            row.GeneradoEn);
    }

    private async Task EnsureCacheTableAsync(CancellationToken ct)
    {
        if (_cacheTableReady) return;
        await db.Database.ExecuteSqlRawAsync(
            """
            IF OBJECT_ID(N'app.CopilotoRespuestaCache', N'U') IS NULL
            BEGIN
                CREATE TABLE app.CopilotoRespuestaCache
                (
                    Id                 int IDENTITY(1,1) NOT NULL PRIMARY KEY,
                    IdEstablecimiento  varchar(64)    NOT NULL,
                    Seccion            nvarchar(80)   NOT NULL,
                    Pregunta           nvarchar(800)  NOT NULL,
                    Tema               nvarchar(64)   NOT NULL,
                    Actividad          nvarchar(16)   NULL,
                    Respuesta          nvarchar(max)  NOT NULL,
                    Modelo             nvarchar(80)   NOT NULL,
                    SinFundamento      bit            NOT NULL CONSTRAINT DF_CopilotoCache_SinFundamento DEFAULT 0,
                    GeneradoEn         datetime2      NOT NULL CONSTRAINT DF_CopilotoCache_GeneradoEn DEFAULT SYSUTCDATETIME()
                );
                CREATE UNIQUE INDEX UX_CopilotoCache_Est_Seccion
                    ON app.CopilotoRespuestaCache (IdEstablecimiento, Seccion);
            END
            """,
            ct);
        _cacheTableReady = true;
    }

    private static string ResolverSeccion(string? temaReq, string pregunta)
    {
        // Solo los chips (Tema explícito de sección) comparten una caché por establecimiento.
        // Las preguntas libres NUNCA reutilizan esa entrada: si no, "andamios sin baranda"
        // devolvía la misma respuesta que el chip "Qué verificar (RGRL)".
        if (!string.IsNullOrWhiteSpace(temaReq) && SeccionesChip.Contains(temaReq.Trim()))
            return temaReq.Trim().ToLowerInvariant();

        var norm = Regex.Replace(pregunta.Trim().ToLowerInvariant(), @"\s+", " ");
        var hash = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(norm)))[..16].ToLowerInvariant();
        return $"q:{hash}";
    }

    private async Task<List<NormativaChunk>> RecuperarChunksAsync(
        IReadOnlyList<string> temas,
        string? actividad,
        HashSet<string> focusTokens,
        CancellationToken ct)
    {
        var q = db.NormativaChunks.AsNoTracking().Where(c => c.Activo && temas.Contains(c.Tema));
        // Preferir actividad del establecimiento, pero incluir chunks genéricos (Actividad null).
        if (!string.IsNullOrWhiteSpace(actividad))
        {
            q = q.Where(c => c.Actividad == null || c.Actividad == actividad);
        }

        var candidatos = await q
            .OrderBy(c => c.SourceId == "rgrl" ? 0 : 1)
            .ThenBy(c => c.Orden)
            .Take(160)
            .ToListAsync(ct);

        if (candidatos.Count == 0)
        {
            candidatos = await db.NormativaChunks.AsNoTracking()
                .Where(c => c.Activo && temas.Contains(c.Tema))
                .OrderBy(c => c.Orden)
                .Take(100)
                .ToListAsync(ct);
        }

        return candidatos
            .Select(c => (Chunk: c, Score: Score(c, focusTokens, actividad)))
            .OrderByDescending(x => x.Score)
            .ThenBy(x => x.Chunk.SourceId == "rgrl" ? 0 : 1)
            .Take(10)
            .Select(x => x.Chunk)
            .ToList();
    }

    private static int Score(NormativaChunk c, HashSet<string> tokens, string? actividad)
    {
        var score = 0;
        if (c.SourceId == "rgrl") score += 2;
        if (!string.IsNullOrWhiteSpace(actividad) &&
            string.Equals(c.Actividad, actividad, StringComparison.OrdinalIgnoreCase))
            score += 5;
        var haystack = $"{c.Titulo} {c.Texto} {c.NormaRef}".ToLowerInvariant();
        foreach (var t in tokens)
        {
            if (haystack.Contains(t, StringComparison.Ordinal)) score += 3;
        }
        // Bonus a señales típicas de riesgo operativo (mejor que el orden del corpus).
        string[] boost =
        [
            "caida", "caída", "andamio", "baranda", "epp", "incendio", "evacuacion", "evacuación",
            "electri", "puesta a tierra", "ruido", "amoladora", "maquina", "máquina", "herramienta",
            "orden", "limpieza", "agresion", "agresión", "vehiculo", "vehículo", "altura",
        ];
        foreach (var b in boost)
        {
            if (tokens.Any(t => t.Contains(b, StringComparison.Ordinal) || b.Contains(t, StringComparison.Ordinal)) &&
                haystack.Contains(b, StringComparison.Ordinal))
                score += 4;
        }
        return score;
    }

    private static HashSet<string> Tokenizar(string texto)
    {
        var stop = new HashSet<string>(StringComparer.OrdinalIgnoreCase)
        {
            "de", "la", "el", "los", "las", "un", "una", "y", "o", "en", "para", "por", "con", "del",
            "que", "qué", "como", "cómo", "esta", "este", "visita", "tengo", "debo", "hay", "total",
            "periodo", "período", "meses", "casos", "sin", "dossier", "anio", "año",
        };
        return texto
            .ToLowerInvariant()
            .Split([' ', '\n', '\t', ',', '.', '?', '¿', '!', '¡', ';', ':', '/', '(', ')', '-', '*', '[', ']', '='],
                StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
            .Where(t => t.Length >= 4 && !stop.Contains(t))
            .Take(40)
            .ToHashSet(StringComparer.OrdinalIgnoreCase);
    }

    private static string InferirTema(string? temaReq, string pregunta)
    {
        if (!string.IsNullOrWhiteSpace(temaReq) &&
            !temaReq.Equals("auto", StringComparison.OrdinalIgnoreCase))
            return temaReq.Trim().ToLowerInvariant();

        var p = pregunta.ToLowerInvariant();
        foreach (var (tema, keys) in TemaKeywords)
        {
            if (keys.Any(k => p.Contains(k, StringComparison.Ordinal)))
                return tema;
        }
        return "rgrl_checklist";
    }

    private static IReadOnlyList<string> TemasParaRetrieve(string tema, bool tienePrs)
    {
        var list = new List<string> { tema };
        if (tema == "rgrl_checklist")
            list.Add("visitas_frecuencia");
        if (tienePrs && tema is "rgrl_checklist" or "auto" or "pese")
        {
            list.Add("pese");
            list.Add("pese_pyme");
        }
        return list.Distinct(StringComparer.OrdinalIgnoreCase).ToList();
    }

    private static string? NormalizeActividad(string? a)
    {
        if (string.IsNullOrWhiteSpace(a)) return null;
        a = a.Trim().ToLowerInvariant();
        return a switch
        {
            "industria" or "comercio" or "351" => "industria",
            "obra" or "construccion" or "construcción" or "911" => "obra",
            "agro" or "rural" or "617" => "agro",
            _ => null,
        };
    }

    private static string? InferirActividad(string? sector, string? ciiu)
    {
        var s = $"{sector} {ciiu}".ToLowerInvariant();
        if (s.Contains("const") || s.Contains("obra")) return "obra";
        if (s.Contains("agro") || s.Contains("agric") || s.Contains("ganad") || s.Contains("rural"))
            return "agro";
        if (string.IsNullOrWhiteSpace(s)) return null;
        return "industria";
    }

    private async Task<string> BuildDossierContextAsync(string id, CancellationToken ct)
    {
        var (ctx, _) = await BuildAccidentesDossierAsync(id, ct);
        return ctx.Length > 3200 ? ctx[..3200] + "…" : ctx;
    }

    /// <summary>Contexto rico del dossier (accidentes + incumplimientos de visitas).</summary>
    private async Task<(string Texto, bool TieneDatos)> BuildAccidentesDossierAsync(
        string id, CancellationToken ct)
    {
        var dossier = await db.EstablecimientoDossiers.AsNoTracking()
            .FirstOrDefaultAsync(d => d.IdEstablecimiento == id, ct);

        var sb = new StringBuilder();
        var tiene = false;

        if (dossier is null)
        {
            sb.AppendLine("Sin dossier histórico cargado.");
        }
        else
        {
            try
            {
                using var doc = JsonDocument.Parse(dossier.DossierJson);
                var root = doc.RootElement;

                if (root.TryGetProperty("accidentes", out var acc) && acc.ValueKind == JsonValueKind.Object)
                {
                    tiene = true;
                    sb.AppendLine("ACCIDENTES:");
                    if (acc.TryGetProperty("total", out var tot))
                        sb.Append("- Total período: ").Append(tot.GetRawText()).AppendLine();
                    if (acc.TryGetProperty("ultimos_12m", out var u12))
                        sb.Append("- Últimos 12 meses: ").Append(u12.GetRawText()).AppendLine();
                    if (acc.TryGetProperty("por_anio", out var anio) && anio.ValueKind == JsonValueKind.Object)
                    {
                        sb.Append("- Por año:");
                        foreach (var p in anio.EnumerateObject())
                            sb.Append(' ').Append(p.Name).Append(':').Append(p.Value.GetRawText());
                        sb.AppendLine();
                    }
                    AppendTopKeyCount(sb, acc, "top_forma", "- Formas más frecuentes");
                    AppendTopKeyCount(sb, acc, "top_zona", "- Zonas del cuerpo");
                    AppendTopKeyCount(sb, acc, "top_naturaleza", "- Naturaleza de la lesión");
                    AppendTopKeyCount(sb, acc, "top_gravedad", "- Gravedad");
                    if (acc.TryGetProperty("recientes", out var recientes) && recientes.ValueKind == JsonValueKind.Array)
                    {
                        sb.AppendLine("- Relatos / casos recientes:");
                        var n = 0;
                        foreach (var r in recientes.EnumerateArray())
                        {
                            if (n++ >= 8) break;
                            var fecha = r.TryGetProperty("fecha", out var f) ? f.GetString() : null;
                            var forma = r.TryGetProperty("forma", out var fo) ? fo.GetString() : null;
                            var relato = r.TryGetProperty("relato", out var re) ? re.GetString() : null;
                            if (string.IsNullOrWhiteSpace(relato) && string.IsNullOrWhiteSpace(forma)) continue;
                            sb.Append("  * [").Append(fecha).Append("] ");
                            if (!string.IsNullOrWhiteSpace(forma)) sb.Append(Sanitize(forma)).Append(": ");
                            sb.AppendLine(Sanitize(relato));
                        }
                    }
                }

                if (root.TryGetProperty("visitas", out var vis) && vis.ValueKind == JsonValueKind.Object)
                {
                    tiene = true;
                    sb.AppendLine("VISITAS PREVENTIVAS PREVIAS:");
                    if (vis.TryGetProperty("total", out var vt))
                        sb.Append("- Total visitas: ").Append(vt.GetRawText()).AppendLine();
                    if (vis.TryGetProperty("incumplimientos_frecuentes", out var inc) &&
                        inc.ValueKind == JsonValueKind.Array && inc.GetArrayLength() > 0)
                    {
                        sb.AppendLine("- Incumplimientos recurrentes (n = en cuántas visitas apareció):");
                        var i = 0;
                        foreach (var e in inc.EnumerateArray())
                        {
                            if (i++ >= 12) break;
                            var k = e.TryGetProperty("k", out var kv) ? kv.GetString() : null;
                            if (string.IsNullOrWhiteSpace(k)) continue;
                            var n = e.TryGetProperty("n", out var nv) ? nv.GetRawText() : null;
                            var ultima = e.TryGetProperty("ultima", out var uv) && uv.ValueKind == JsonValueKind.String
                                ? uv.GetString()
                                : null;
                            sb.Append("  * ").Append(Sanitize(k));
                            if (n is not null) sb.Append(" (n=").Append(n);
                            if (!string.IsNullOrWhiteSpace(ultima)) sb.Append(", última ").Append(ultima);
                            if (n is not null) sb.Append(')');
                            sb.AppendLine();
                        }
                    }
                }
            }
            catch
            {
                sb.AppendLine("Dossier no parseable.");
            }
        }

        try
        {
            var abiertos = await db.VisitasHallazgos.AsNoTracking()
                .Where(h => h.IdEstablecimiento == id && h.Estado == "abierto")
                .OrderByDescending(h => h.Severidad == "alta")
                .ThenByDescending(h => h.CreadoEn)
                .Take(15)
                .Select(h => new { h.Severidad, h.Hallazgo, h.PlazoDias, h.NormaRef })
                .ToListAsync(ct);
            if (abiertos.Count > 0)
            {
                tiene = true;
                sb.AppendLine("HALLAZGOS ABIERTOS (app):");
                foreach (var h in abiertos)
                {
                    sb.Append("- [").Append(h.Severidad).Append("] ").Append(Sanitize(h.Hallazgo));
                    if (h.PlazoDias is int plazo) sb.Append(" (plazo ").Append(plazo).Append(" días");
                    if (!string.IsNullOrWhiteSpace(h.NormaRef))
                    {
                        sb.Append(h.PlazoDias is null ? " (" : "; ");
                        sb.Append("norma ").Append(Sanitize(h.NormaRef));
                    }
                    if (h.PlazoDias is not null || !string.IsNullOrWhiteSpace(h.NormaRef))
                        sb.Append(')');
                    sb.AppendLine();
                }
            }
        }
        catch
        {
            // tabla aún no creada: el dossier histórico alcanza
        }

        var ctx = sb.ToString().Trim();
        if (!tiene || string.IsNullOrWhiteSpace(ctx))
            return ("Dossier sin detalle usable de accidentes/visitas.", false);
        return (ctx.Length > 4500 ? ctx[..4500] + "…" : ctx, true);
    }

    private static void AppendTopKeyCount(StringBuilder sb, JsonElement parent, string prop, string label)
    {
        if (!parent.TryGetProperty(prop, out var arr) || arr.ValueKind != JsonValueKind.Array) return;
        sb.Append(label).Append(':');
        var i = 0;
        foreach (var e in arr.EnumerateArray())
        {
            if (i++ >= 5) break;
            var k = e.TryGetProperty("k", out var kv) ? kv.GetString() : null;
            if (string.IsNullOrWhiteSpace(k)) continue;
            sb.Append(' ').Append(Sanitize(k));
            if (e.TryGetProperty("n", out var n)) sb.Append('(').Append(n.GetRawText()).Append(')');
            sb.Append(';');
        }
        sb.AppendLine();
    }

    private static string BuildAccidentesPrompt(
        string pregunta,
        string dossierRich,
        string? banda,
        int? ranking,
        bool prs,
        string? actividad)
    {
        var sb = new StringBuilder();
        sb.AppendLine("=== HISTORIAL DEL ESTABLECIMIENTO (anonimizado) ===");
        sb.AppendLine(dossierRich);
        if (!string.IsNullOrWhiteSpace(banda)) sb.Append("Banda de riesgo: ").Append(banda).Append(". ");
        if (ranking is not null) sb.Append("Posición en priorización: #").Append(ranking).Append(". ");
        if (prs) sb.Append("Obligación PRS/PESE: sí. ");
        if (!string.IsNullOrWhiteSpace(actividad)) sb.Append("Actividad: ").Append(actividad).Append('.');
        sb.AppendLine();
        sb.AppendLine();
        sb.AppendLine("=== PEDIDO DEL PREVENTOR ===");
        sb.AppendLine(pregunta);
        sb.AppendLine();
        sb.AppendLine("=== TAREA ===");
        sb.AppendLine(
            "Sos un asistente para un preventor de ART (Argentina). Con SOLO el historial de arriba, " +
            "armá un briefing de ACCIDENTES PREVIOS para preparar la próxima visita. " +
            "Esto NO es el resumen IA genérico de guía de visita: enfocate en el patrón de siniestros.");
        sb.AppendLine("REGLAS:");
        sb.AppendLine("- Empezá exactamente con ===RESPUESTA=== y no escribas nada antes.");
        sb.AppendLine("- Español rioplatense. No inventes datos que no figuren arriba.");
        sb.AppendLine("- No uses nombre de empresa ni datos personales.");
        sb.AppendLine("- Máximo ~200 palabras. Viñetas con \"- \".");
        sb.AppendLine("- Usá EXACTAMENTE este formato:");
        sb.AppendLine();
        sb.AppendLine("**Qué pasó en este establecimiento**");
        sb.AppendLine("- (volumen, tendencia 12m / por año si hay, gravedad)");
        sb.AppendLine();
        sb.AppendLine("**Patrones a mirar en la visita**");
        sb.AppendLine("- (formas, zonas, naturaleza: 3–5 focos concretos anclados a los números)");
        sb.AppendLine();
        sb.AppendLine("**Incumplimientos o hallazgos previos**");
        sb.AppendLine("- (si hay visitas; marcá recurrentes. Si no hay: \"Sin incumplimientos de visitas en el dossier.\")");
        sb.AppendLine();
        sb.AppendLine("**Preguntas / chequeos al llegar**");
        sb.AppendLine("- (2–4 acciones concretas derivadas del historial)");
        return sb.ToString();
    }

    private static string Sanitize(string? s)
    {
        if (string.IsNullOrWhiteSpace(s)) return "";
        // Evitar filtrar CUIL/DNI hacia el modelo.
        s = Regex.Replace(s, @"\b\d{2}-\d{8}-\d\b", "[id]");
        s = Regex.Replace(s, @"\b\d{7,11}\b", "[nro]");
        return s.Trim();
    }

    private static string BuildPrompt(
        string pregunta,
        string tema,
        string? actividad,
        string? banda,
        int? ranking,
        bool prs,
        IReadOnlyList<NormativaChunk> chunks,
        string dossierCtx,
        bool tieneDossier)
    {
        var sb = new StringBuilder();
        sb.AppendLine("=== CONTEXTO DEL ESTABLECIMIENTO QUE ESTÁ VIENDO EL PREVENTOR (anonimizado) ===");
        if (tieneDossier && !string.IsNullOrWhiteSpace(dossierCtx))
            sb.AppendLine(dossierCtx);
        else
            sb.AppendLine("Sin historial detallado de accidentes/visitas en dossier.");
        if (!string.IsNullOrWhiteSpace(banda)) sb.Append("- Banda de riesgo: ").Append(banda).AppendLine();
        if (ranking is not null) sb.Append("- Ranking de priorización: #").Append(ranking).AppendLine();
        sb.Append("- Obligación PRS/PESE en ranking: ").Append(prs ? "sí" : "no / no marcada").AppendLine();
        if (!string.IsNullOrWhiteSpace(actividad))
            sb.Append("- Actividad inferida: ").Append(actividad).AppendLine();
        sb.AppendLine();

        sb.AppendLine("=== CORPUS NORMATIVO SRT (únicas fuentes permitidas para citar) ===");
        for (var i = 0; i < chunks.Count; i++)
        {
            var c = chunks[i];
            sb.Append("[#").Append(i + 1).Append("] ");
            sb.Append(c.NormaRef ?? c.Titulo);
            sb.Append(" | tema=").Append(c.Tema);
            if (!string.IsNullOrWhiteSpace(c.Actividad)) sb.Append(" | actividad=").Append(c.Actividad);
            sb.AppendLine();
            sb.AppendLine(c.Texto.Length > 1600 ? c.Texto[..1600] + "…" : c.Texto);
            sb.AppendLine();
        }

        sb.AppendLine("=== PREGUNTA DEL PREVENTOR ===");
        sb.AppendLine(pregunta);
        sb.AppendLine();
        sb.AppendLine("=== TAREA ===");
        sb.AppendLine("Sos el copiloto normativo de Prevex (ART Argentina).");
        sb.AppendLine("REGLAS GENERALES:");
        sb.AppendLine("- Empezá exactamente con ===RESPUESTA=== y no escribas nada antes.");
        sb.AppendLine("- Español rioplatense, concreto, útil para ESTA visita a ESTE establecimiento.");
        sb.AppendLine("- Citá fuentes solo del corpus con [#n]. No inventes artículos ni plazos.");
        sb.AppendLine("- No es asesoramiento legal; es apoyo operativo al preventor.");
        sb.AppendLine("- Máximo ~240 palabras. Viñetas con \"- \".");
        sb.AppendLine("- Organizá en secciones. Cada título solo en su línea: **Título**");
        sb.AppendLine("- PROHIBIDO un listado genérico que ignore el contexto del establecimiento.");
        sb.AppendLine("- Si el dossier trae formas de accidente o incumplimientos, PRIORIZALOS en la respuesta.");
        sb.AppendLine();
        sb.AppendLine("ENFOQUE SEGÚN EL TEMA (" + tema + "):");
        switch (tema.ToLowerInvariant())
        {
            case "rgrl_checklist":
                sb.AppendLine("- Elegí 6–10 ítems del RGRL del corpus que mejor se relacionen con los accidentes,");
                sb.AppendLine("  incumplimientos o riesgos del dossier (caídas, herramientas, eléctrico, incendio, etc.).");
                sb.AppendLine("- Empezá con 1 línea: por qué esos focos en ESTE establecimiento (números del dossier).");
                sb.AppendLine("- No listes aparatos para izar u otros ítems si no hay señal en el dossier.");
                break;
            case "visitas_frecuencia":
                sb.AppendLine("- Explicá la regla normativa Y aplicála a este caso con los datos del dossier");
                sb.AppendLine("  (accidentes/año, últimos 12m, banda/ranking). Decí si es probable visita anual u otra.");
                sb.AppendLine("- Si faltan datos para concluir, marcá qué dato falta; no copies solo el artículo.");
                break;
            case "pese":
            case "pese_pyme":
                sb.AppendLine("- Si PRS/PESE = sí: obligaciones a controlar en ESTA visita + vínculo con incumplimientos del dossier.");
                sb.AppendLine("- Si PRS/PESE = no: aclaralo y listá qué mirarías igual / cuándo aplicaría.");
                break;
            case "rar_examenes":
                sb.AppendLine("- Relacioná exámenes/nómina de expuestos con riesgos sugeridos por el dossier");
                sb.AppendLine("  (ruido, químico, etc.). Si el dossier no sugiere agentes, dilo y no inventes exposiciones.");
                break;
            case "rgrl_obligacion":
                sb.AppendLine("- Explicá obligación de actualizar/presentar RGRL y qué chequearías acá según historial.");
                break;
            default:
                sb.AppendLine("- Anclá la respuesta a los datos del establecimiento antes de la norma genérica.");
                break;
        }
        return sb.ToString();
    }

    private static string LimpiarSalida(string? texto)
    {
        if (string.IsNullOrWhiteSpace(texto)) return "";
        var t = texto.Replace("\r\n", "\n").Replace("\r", "\n");
        var idx = t.LastIndexOf("===RESPUESTA===", StringComparison.OrdinalIgnoreCase);
        if (idx >= 0)
        {
            var nl = t.IndexOf('\n', idx);
            t = nl >= 0 ? t[(nl + 1)..] : "";
        }
        return t.Trim();
    }
}
