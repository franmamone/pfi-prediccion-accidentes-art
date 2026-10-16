using System.Text.RegularExpressions;

namespace PfiPrevencion.Api.Services;

/// <summary>
/// Saneo de texto libre antes de enviarlo a un modelo generativo.
/// No es NER perfecto: la política principal es no mandar prosa (ver <see cref="DossierLlmContextBuilder"/>).
/// Este filtro es defensa en profundidad para restos (CUIT, teléfonos, domicilios tipados).
/// </summary>
public static partial class PiiTextSanitizer
{
    [GeneratedRegex(@"[\w.\-]+@[\w.\-]+\.\w+", RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)]
    private static partial Regex EmailRegex();

    [GeneratedRegex(@"\b\d{2}[-\s]?\d{7,8}[-\s]?\d\b", RegexOptions.CultureInvariant)]
    private static partial Regex CuitRegex();

    [GeneratedRegex(@"\b(?:\+?54[\s\-]?)?(?:9[\s\-]?)?(?:11|15|2\d{2}|3\d{2})[\s\-]?\d{3,4}[\s\-]?\d{4}\b", RegexOptions.CultureInvariant)]
    private static partial Regex PhoneRegex();

    [GeneratedRegex(@"\b\d{7,11}\b", RegexOptions.CultureInvariant)]
    private static partial Regex LongDigitsRegex();

    [GeneratedRegex(
        @"\b(?:av(?:enida)?|calle|pasaje|pje\.?|ruta|rp|rn|boulevard|bvd\.?|diag(?:onal)?)\b\.?\s+[\wáéíóúñÁÉÍÓÚÑ\s\.]{0,40}\d{1,5}\b",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)]
    private static partial Regex AddressRegex();

    [GeneratedRegex(
        @"\b(?:domicilio|dirección|direccion)\s*:?\s+[\wáéíóúñÁÉÍÓÚÑ\s\.,#\-]{3,60}",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)]
    private static partial Regex DomicilioLabelRegex();

    [GeneratedRegex(
        @"\b(?:dni|doc(?:umento)?|legajo|cuil)\s*:?\s*[\d\.\-]{5,15}\b",
        RegexOptions.IgnoreCase | RegexOptions.CultureInvariant)]
    private static partial Regex DocLabelRegex();

    [GeneratedRegex(
        @"(?i)\b(ignore|ignor[aá]|olvid[aá]|disregard)\b.{0,40}\b(instrucciones|instructions|reglas|rules)\b")]
    private static partial Regex InjectionIgnoreRegex();

    [GeneratedRegex(@"(?i)\b(system\s*prompt|jailbreak|DAN\b)\b")]
    private static partial Regex InjectionJailbreakRegex();

    [GeneratedRegex(@"\s+")]
    private static partial Regex MultiSpaceRegex();

    /// <summary>Reemplaza patrones tipados de PII. No elimina nombres propios en prosa.</summary>
    public static string Scrub(string? text, int maxLen = 120)
    {
        if (string.IsNullOrWhiteSpace(text)) return "";
        var s = text.Trim();
        s = EmailRegex().Replace(s, "[email]");
        s = CuitRegex().Replace(s, "[id]");
        s = PhoneRegex().Replace(s, "[tel]");
        s = DocLabelRegex().Replace(s, "[doc]");
        s = AddressRegex().Replace(s, "[domicilio]");
        s = DomicilioLabelRegex().Replace(s, "[domicilio]");
        s = LongDigitsRegex().Replace(s, "[nro]");
        s = InjectionIgnoreRegex().Replace(s, "[texto]");
        s = InjectionJailbreakRegex().Replace(s, "[texto]");
        s = MultiSpaceRegex().Replace(s, " ").Trim();
        if (s.Length > maxLen) s = s[..maxLen] + "…";
        return s;
    }

    /// <summary>
    /// true si, tras scrub, aún parece prosa con riesgo (domicilio residual, muchos tokens, etc.).
    /// </summary>
    public static bool LooksRiskyForLlm(string? scrubbed)
    {
        if (string.IsNullOrWhiteSpace(scrubbed)) return false;
        if (scrubbed.Contains("[domicilio]", StringComparison.OrdinalIgnoreCase)) return true;
        if (scrubbed.Contains("[tel]", StringComparison.OrdinalIgnoreCase)) return true;
        if (scrubbed.Contains("[id]", StringComparison.OrdinalIgnoreCase)) return true;
        if (scrubbed.Contains("[email]", StringComparison.OrdinalIgnoreCase)) return true;
        if (scrubbed.Contains("[doc]", StringComparison.OrdinalIgnoreCase)) return true;
        // Categorías cortas tipo "Orden y Limpieza" están OK; párrafos no.
        return scrubbed.Length > 90 || scrubbed.Count(c => c == ' ') >= 12;
    }

    /// <summary>
    /// Para hallazgos/notas operativas: si el scrub deja riesgo, no se envía el texto libre.
    /// </summary>
    public static string ForLlmOperationalNote(string? text, int maxLen = 80)
    {
        var scrubbed = Scrub(text, maxLen);
        if (string.IsNullOrWhiteSpace(scrubbed)) return "";
        if (LooksRiskyForLlm(scrubbed))
            return "[detalle omitido por privacidad]";
        return scrubbed;
    }
}
