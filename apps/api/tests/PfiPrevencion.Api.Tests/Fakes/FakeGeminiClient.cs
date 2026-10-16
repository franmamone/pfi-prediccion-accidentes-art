using PfiPrevencion.Api.Services;

namespace PfiPrevencion.Api.Tests.Fakes;

public sealed class FakeGeminiClient : IGeminiClient
{
    public bool Configurado => true;
    public string Model => "fake-gemini";
    public string Respuesta { get; set; } =
        "===RESPUESTA===\n**Resumen**\n- Foco de prueba.\n**Ítems**\n- Item 1";

    public Task<GeminiResult> GenerarAsync(string prompt, CancellationToken ct = default) =>
        Task.FromResult(new GeminiResult(Respuesta, 10, 20, Model));
}
