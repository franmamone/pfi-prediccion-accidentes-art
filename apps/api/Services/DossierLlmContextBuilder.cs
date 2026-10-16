using System.Text;
using System.Text.Json;

namespace PfiPrevencion.Api.Services;

/// <summary>
/// Proyección LLM-safe del dossier: solo agregados (conteos, tops, frecuencias).
/// Nunca incluye relatos de accidentes, observaciones ni incumplimientos en prosa libre.
/// El JSON completo puede seguir en BD para uso humano; Gemini solo ve este recorte.
/// </summary>
public static class DossierLlmContextBuilder
{
    public static string BuildAggregatesOnly(string dossierJson)
    {
        using var doc = JsonDocument.Parse(dossierJson);
        var sb = new StringBuilder();
        AppendFromRoot(sb, doc.RootElement);
        var text = sb.ToString().Trim();
        return string.IsNullOrWhiteSpace(text)
            ? "Sin agregados históricos usables."
            : text;
    }

    public static void AppendFromRoot(StringBuilder sb, JsonElement root)
    {
        if (root.TryGetProperty("accidentes", out var acc) && acc.ValueKind == JsonValueKind.Object)
            AppendAccidentes(sb, acc);

        if (root.TryGetProperty("visitas", out var vis) && vis.ValueKind == JsonValueKind.Object)
            AppendVisitas(sb, vis);
    }

    public static void AppendAccidentes(StringBuilder sb, JsonElement acc)
    {
        sb.AppendLine("ACCIDENTES (solo agregados; sin relatos ni textos libres):");
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
        AppendTop(sb, acc, "top_forma", "- Formas más frecuentes");
        AppendTop(sb, acc, "top_zona", "- Zonas del cuerpo");
        AppendTop(sb, acc, "top_naturaleza", "- Naturaleza de la lesión");
        AppendTop(sb, acc, "top_gravedad", "- Gravedad");
        // Intencional: NO se incluyen accidentes.recientes / relato.
    }

    public static void AppendVisitas(StringBuilder sb, JsonElement vis)
    {
        sb.Append("VISITAS PREVENTIVAS (solo agregados");
        if (vis.TryGetProperty("total", out var vt))
            sb.Append("; total: ").Append(vt.GetRawText());
        sb.AppendLine("):");

        if (vis.TryGetProperty("incumplimientos_frecuentes", out var inc) &&
            inc.ValueKind == JsonValueKind.Array &&
            inc.GetArrayLength() > 0)
        {
            sb.AppendLine("- Incumplimientos recurrentes (categoría agregada; n = visitas en que apareció):");
            var i = 0;
            foreach (var e in inc.EnumerateArray())
            {
                if (i++ >= 15) break;
                var k = e.TryGetProperty("k", out var kv) ? kv.GetString() : null;
                var label = PiiTextSanitizer.ForLlmOperationalNote(k, maxLen: 60);
                if (string.IsNullOrWhiteSpace(label) || label.StartsWith("[detalle", StringComparison.Ordinal))
                    continue;
                var n = e.TryGetProperty("n", out var nv) ? nv.GetRawText() : null;
                var ultima = e.TryGetProperty("ultima", out var uv) && uv.ValueKind == JsonValueKind.String
                    ? uv.GetString()
                    : null;
                sb.Append("  * ").Append(label);
                if (n is not null) sb.Append(" (n=").Append(n);
                if (!string.IsNullOrWhiteSpace(ultima)) sb.Append(", última ").Append(ultima);
                if (n is not null) sb.Append(')');
                sb.AppendLine();
            }
        }
        else
        {
            sb.AppendLine("- Sin incumplimientos agregados por categoría.");
        }
        // Intencional: NO visitas.recientes, NO observaciones[], NO prosa de incumplimientos crudos.
    }

    public static void AppendHallazgoSeguro(
        StringBuilder sb,
        string severidad,
        string? hallazgo,
        int? plazoDias = null,
        string? normaRef = null)
    {
        sb.Append("- [").Append(severidad).Append("] ");
        var note = PiiTextSanitizer.ForLlmOperationalNote(hallazgo, maxLen: 70);
        sb.Append(string.IsNullOrWhiteSpace(note) ? "[hallazgo]" : note);
        if (plazoDias is int plazo) sb.Append(" (plazo ").Append(plazo).Append(" días)");
        if (!string.IsNullOrWhiteSpace(normaRef))
            sb.Append(" norma=").Append(PiiTextSanitizer.Scrub(normaRef, 40));
        sb.AppendLine();
    }

    private static void AppendTop(StringBuilder sb, JsonElement parent, string prop, string label)
    {
        if (!parent.TryGetProperty(prop, out var arr) || arr.ValueKind != JsonValueKind.Array)
            return;
        sb.Append(label).Append(':');
        var i = 0;
        foreach (var e in arr.EnumerateArray())
        {
            if (i++ >= 5) break;
            var k = e.TryGetProperty("k", out var kv) ? kv.GetString() : null;
            var labelK = PiiTextSanitizer.Scrub(k, 40);
            if (string.IsNullOrWhiteSpace(labelK) || PiiTextSanitizer.LooksRiskyForLlm(labelK))
                continue;
            sb.Append(' ').Append(labelK);
            if (e.TryGetProperty("n", out var n)) sb.Append('(').Append(n.GetRawText()).Append(')');
            sb.Append(';');
        }
        sb.AppendLine();
    }
}
