namespace PfiPrevencion.Api.Services;

public interface IGeminiClient
{
    bool Configurado { get; }
    string Model { get; }
    Task<GeminiResult> GenerarAsync(string prompt, CancellationToken ct = default);
}
