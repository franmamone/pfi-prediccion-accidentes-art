using System.Text;
using System.Text.Json;

namespace PfiPrevencion.Api.Services;

public sealed class GeminiOptions
{
    public string ApiKey { get; set; } = "";

    /// <summary>Modelo preferido (compat). Si <see cref="Models"/> está vacío, se usa este.</summary>
    public string Model { get; set; } = "gemini-3.8-flash";

    /// <summary>
    /// Cadena de fallback ordenada de mejor a peor. Se prueba el primero;
    /// si falla por cuota/disponibilidad, se pasa al siguiente.
    /// </summary>
    public string[] Models { get; set; } = [];

    public string BaseUrl { get; set; } = "https://generativelanguage.googleapis.com/v1beta";
    public double Temperature { get; set; } = 0.4;
    public int MaxOutputTokens { get; set; } = 900;

    /// <summary>Timeout de la llamada HTTP al modelo. Modelos grandes pueden tardar &gt;60s.</summary>
    public int TimeoutSeconds { get; set; } = 180;

    /// <summary>
    /// Presupuesto de "thinking" para modelos Gemini (2.5/3.x). Estos vienen con
    /// razonamiento activado por defecto, que consume el presupuesto de salida y
    /// deja la respuesta visible cortada. 0 lo desactiva (respuesta directa y rápida).
    /// -1 lo deja en automático. No aplica a modelos Gemma.
    /// </summary>
    public int ThinkingBudget { get; set; } = 0;
}

public sealed record GeminiResult(string Texto, int? TokensPrompt, int? TokensSalida, string Modelo);

public sealed class GeminiException(string message) : Exception(message);

/// <summary>
/// Cliente mínimo para la Generative Language API de Google (modelos Gemini/Gemma).
/// Envía únicamente texto anonimizado; no recibe identificadores del establecimiento.
/// Prueba la lista de modelos en orden hasta obtener una respuesta usable.
/// </summary>
public sealed class GeminiClient(HttpClient http, IConfiguration config)
{
    private readonly GeminiOptions _opt = LoadOptions(config);
    private string? _ultimoModeloUsado;

    private static GeminiOptions LoadOptions(IConfiguration config)
    {
        var opt = new GeminiOptions();
        config.GetSection("Gemini").Bind(opt);
        var envKey = Environment.GetEnvironmentVariable("GEMINI_API_KEY");
        if (!string.IsNullOrWhiteSpace(envKey)) opt.ApiKey = envKey.Trim();
        return opt;
    }

    public bool Configurado => !string.IsNullOrWhiteSpace(_opt.ApiKey);

    /// <summary>Último modelo que respondió con éxito; si aún no hubo llamada, el preferido.</summary>
    public string Model => _ultimoModeloUsado ?? ModelosEnOrden().FirstOrDefault() ?? _opt.Model;

    private IReadOnlyList<string> ModelosEnOrden()
    {
        var list = new List<string>();
        if (_opt.Models is { Length: > 0 })
        {
            foreach (var m in _opt.Models)
            {
                if (string.IsNullOrWhiteSpace(m)) continue;
                var id = m.Trim();
                if (!list.Contains(id, StringComparer.OrdinalIgnoreCase))
                    list.Add(id);
            }
        }
        if (list.Count == 0 && !string.IsNullOrWhiteSpace(_opt.Model))
            list.Add(_opt.Model.Trim());
        return list;
    }

    public async Task<GeminiResult> GenerarAsync(string prompt, CancellationToken ct = default)
    {
        if (!Configurado)
        {
            throw new GeminiException("El servicio de IA no está configurado (falta la API key de Gemini).");
        }

        var modelos = ModelosEnOrden();
        if (modelos.Count == 0)
        {
            throw new GeminiException("No hay modelos Gemini configurados (Gemini:Models / Gemini:Model).");
        }

        var errores = new List<string>();
        foreach (var modelo in modelos)
        {
            try
            {
                var resultado = await GenerarConModeloAsync(prompt, modelo, ct);
                _ultimoModeloUsado = modelo;
                return resultado;
            }
            catch (GeminiException ex) when (EsErrorRecuperable(ex.Message))
            {
                errores.Add($"{modelo}: {ex.Message}");
            }
        }

        throw new GeminiException(
            "Ningún modelo Gemini disponible. Intentos: " + string.Join(" | ", errores));
    }

    private async Task<GeminiResult> GenerarConModeloAsync(
        string prompt, string modelo, CancellationToken ct)
    {
        // Google admite dos tipos de credencial para la Generative Language API:
        //  - API keys (clásicas "AIza…" y las nuevas "auth keys" "AQ.Ab8…"): van por el
        //    header "x-goog-api-key" (equivalente a ?key=). NO deben mandarse como Bearer.
        //  - Tokens OAuth2 de acceso ("ya29.…"): van como "Authorization: Bearer".
        var esOAuthToken = _opt.ApiKey.StartsWith("ya29.", StringComparison.Ordinal);
        var url = $"{_opt.BaseUrl.TrimEnd('/')}/models/{modelo}:generateContent";

        var generationConfig = new Dictionary<string, object?>
        {
            ["temperature"] = _opt.Temperature,
            ["maxOutputTokens"] = _opt.MaxOutputTokens,
        };
        var esGemini = modelo.Contains("gemini", StringComparison.OrdinalIgnoreCase);
        if (esGemini && _opt.ThinkingBudget >= 0)
        {
            generationConfig["thinkingConfig"] = new { thinkingBudget = _opt.ThinkingBudget };
        }

        var body = new
        {
            contents = new[]
            {
                new { role = "user", parts = new[] { new { text = prompt } } },
            },
            generationConfig,
        };

        using var req = new HttpRequestMessage(HttpMethod.Post, url)
        {
            Content = new StringContent(
                JsonSerializer.Serialize(body), Encoding.UTF8, "application/json"),
        };
        if (esOAuthToken)
        {
            req.Headers.TryAddWithoutValidation("Authorization", $"Bearer {_opt.ApiKey}");
        }
        else
        {
            req.Headers.TryAddWithoutValidation("x-goog-api-key", _opt.ApiKey);
        }

        HttpResponseMessage resp;
        try
        {
            resp = await http.SendAsync(req, ct);
        }
        catch (Exception ex)
        {
            throw new GeminiException($"No se pudo contactar el servicio de IA: {ex.Message}");
        }

        var json = await resp.Content.ReadAsStringAsync(ct);
        if (!resp.IsSuccessStatusCode)
        {
            var detalle = ExtraerError(json) ?? resp.ReasonPhrase ?? "sin detalle";
            throw new GeminiException(
                $"El servicio de IA rechazó la solicitud: HTTP {(int)resp.StatusCode} — {detalle}");
        }

        var parsed = ParseRespuesta(json, modelo);
        if (string.IsNullOrWhiteSpace(parsed.Texto))
        {
            throw new GeminiException("El servicio de IA no devolvió texto (posible filtro de contenido o cuota).");
        }
        return parsed;
    }

    /// <summary>
    /// Errores donde vale la pena probar el siguiente modelo de la cadena
    /// (cuota, sobrecarga/demanda alta de un modelo, 5xx, modelo inexistente, respuesta vacía).
    /// </summary>
    private static bool EsErrorRecuperable(string mensaje)
    {
        if (string.IsNullOrWhiteSpace(mensaje)) return false;
        var m = mensaje.ToLowerInvariant();
        return m.Contains("429")
            || m.Contains("500")
            || m.Contains("502")
            || m.Contains("503")
            || m.Contains("504")
            || m.Contains("resource_exhausted")
            || m.Contains("quota")
            || m.Contains("rate limit")
            || m.Contains("unavailable")
            || m.Contains("overloaded")
            || m.Contains("high demand")
            || m.Contains("try again later")
            || m.Contains("temporarily")
            || m.Contains("capacity")
            || m.Contains("not found")
            || m.Contains("404")
            || m.Contains("no devolvió texto")
            || m.Contains("filter de contenido")
            || m.Contains("filtro de contenido");
    }

    private static string? ExtraerError(string json)
    {
        try
        {
            using var doc = JsonDocument.Parse(json);
            if (doc.RootElement.TryGetProperty("error", out var err) &&
                err.TryGetProperty("message", out var msg))
            {
                return msg.GetString();
            }
        }
        catch (JsonException) { }
        return null;
    }

    private static GeminiResult ParseRespuesta(string json, string modelo)
    {
        using var doc = JsonDocument.Parse(json);
        var root = doc.RootElement;
        var sb = new StringBuilder();
        if (root.TryGetProperty("candidates", out var candidates) &&
            candidates.ValueKind == JsonValueKind.Array &&
            candidates.GetArrayLength() > 0)
        {
            var content = candidates[0];
            if (content.TryGetProperty("content", out var c) &&
                c.TryGetProperty("parts", out var parts) &&
                parts.ValueKind == JsonValueKind.Array)
            {
                foreach (var part in parts.EnumerateArray())
                {
                    if (part.TryGetProperty("text", out var t))
                    {
                        sb.Append(t.GetString());
                    }
                }
            }
        }

        int? tokPrompt = null, tokSalida = null;
        if (root.TryGetProperty("usageMetadata", out var usage))
        {
            if (usage.TryGetProperty("promptTokenCount", out var p)) tokPrompt = p.GetInt32();
            if (usage.TryGetProperty("candidatesTokenCount", out var s)) tokSalida = s.GetInt32();
        }

        return new GeminiResult(sb.ToString().Trim(), tokPrompt, tokSalida, modelo);
    }
}
