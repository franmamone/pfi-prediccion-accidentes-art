using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace PfiPrevencion.Api.Services;

public sealed class GeminiOptions
{
    public string ApiKey { get; set; } = "";
    public string Model { get; set; } = "gemma-4-31b-it";
    public string BaseUrl { get; set; } = "https://generativelanguage.googleapis.com/v1beta";
    public double Temperature { get; set; } = 0.4;
    public int MaxOutputTokens { get; set; } = 900;

    /// <summary>Timeout de la llamada HTTP al modelo. Modelos grandes (p. ej. gemma 31B) pueden tardar &gt;60s.</summary>
    public int TimeoutSeconds { get; set; } = 180;

    /// <summary>
    /// Presupuesto de "thinking" para modelos Gemini (2.5/3.x). Estos vienen con
    /// razonamiento activado por defecto, que consume el presupuesto de salida y
    /// deja la respuesta visible cortada. 0 lo desactiva (respuesta directa y rápida).
    /// -1 lo deja en automático. No aplica a modelos Gemma.
    /// </summary>
    public int ThinkingBudget { get; set; } = 0;
}

public sealed record GeminiResult(string Texto, int? TokensPrompt, int? TokensSalida);

public sealed class GeminiException(string message) : Exception(message);

/// <summary>
/// Cliente mínimo para la Generative Language API de Google (modelos Gemini/Gemma).
/// Envía únicamente texto anonimizado; no recibe identificadores del establecimiento.
/// </summary>
public sealed class GeminiClient(HttpClient http, IConfiguration config)
{
    private readonly GeminiOptions _opt = LoadOptions(config);

    private static GeminiOptions LoadOptions(IConfiguration config)
    {
        var opt = new GeminiOptions();
        config.GetSection("Gemini").Bind(opt);
        // La clave puede venir por variable de entorno (preferido en despliegue).
        var envKey = Environment.GetEnvironmentVariable("GEMINI_API_KEY");
        if (!string.IsNullOrWhiteSpace(envKey)) opt.ApiKey = envKey.Trim();
        return opt;
    }

    public bool Configurado => !string.IsNullOrWhiteSpace(_opt.ApiKey);
    public string Model => _opt.Model;

    public async Task<GeminiResult> GenerarAsync(string prompt, CancellationToken ct = default)
    {
        if (!Configurado)
        {
            throw new GeminiException("El servicio de IA no está configurado (falta la API key de Gemini).");
        }

        // Google admite dos tipos de credencial para la Generative Language API:
        //  - API keys (clásicas "AIza…" y las nuevas "auth keys" "AQ.Ab8…"): van por el
        //    header "x-goog-api-key" (equivalente a ?key=). NO deben mandarse como Bearer.
        //  - Tokens OAuth2 de acceso ("ya29.…"): van como "Authorization: Bearer".
        var esOAuthToken = _opt.ApiKey.StartsWith("ya29.", StringComparison.Ordinal);
        var url = $"{_opt.BaseUrl.TrimEnd('/')}/models/{_opt.Model}:generateContent";

        var generationConfig = new Dictionary<string, object?>
        {
            ["temperature"] = _opt.Temperature,
            ["maxOutputTokens"] = _opt.MaxOutputTokens,
        };
        // Solo los modelos Gemini soportan thinkingConfig; Gemma lo rechaza.
        // Con thinkingBudget=0 la respuesta no se "come" el presupuesto de salida.
        var esGemini = _opt.Model.Contains("gemini", StringComparison.OrdinalIgnoreCase);
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
            var detalle = ExtraerError(json) ?? $"HTTP {(int)resp.StatusCode}";
            throw new GeminiException($"El servicio de IA rechazó la solicitud: {detalle}");
        }

        var parsed = ParseRespuesta(json);
        if (string.IsNullOrWhiteSpace(parsed.Texto))
        {
            throw new GeminiException("El servicio de IA no devolvió texto (posible filtro de contenido o cuota).");
        }
        return parsed;
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

    private static GeminiResult ParseRespuesta(string json)
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

        return new GeminiResult(sb.ToString().Trim(), tokPrompt, tokSalida);
    }
}
