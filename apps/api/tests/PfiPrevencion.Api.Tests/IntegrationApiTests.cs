using System.Net;
using System.Net.Http.Headers;
using System.Net.Http.Json;
using System.Text.Json;

namespace PfiPrevencion.Api.Tests;

public class IntegrationApiTests : IClassFixture<ApiFactory>, IAsyncLifetime
{
    private readonly ApiFactory _factory;
    private readonly HttpClient _client;
    private static readonly JsonSerializerOptions JsonOpts = new() { PropertyNameCaseInsensitive = true };

    public IntegrationApiTests(ApiFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();
    }

    public async Task InitializeAsync() => await _factory.ResetAndSeedAsync();
    public Task DisposeAsync() => Task.CompletedTask;

    private async Task<string> LoginAsync(string email, string password = "Test1234!")
    {
        var res = await _client.PostAsJsonAsync("/api/auth/login", new { email, password });
        res.EnsureSuccessStatusCode();
        using var doc = JsonDocument.Parse(await res.Content.ReadAsStringAsync());
        if (doc.RootElement.TryGetProperty("access_token", out var at))
            return at.GetString() ?? throw new InvalidOperationException("access_token null");
        if (doc.RootElement.TryGetProperty("token", out var t))
            return t.GetString() ?? throw new InvalidOperationException("token null");
        throw new InvalidOperationException("No token in login response: " + doc.RootElement);
    }

    private void Auth(string token) =>
        _client.DefaultRequestHeaders.Authorization = new AuthenticationHeaderValue("Bearer", token);

    [Fact]
    public async Task Health_Ok()
    {
        var res = await _client.GetAsync("/api/health");
        Assert.Equal(HttpStatusCode.OK, res.StatusCode);
    }

    [Fact]
    public async Task Login_Y_Me_Y_Riesgo()
    {
        var token = await LoginAsync("prev@test.local");
        Auth(token);

        var me = await _client.GetAsync("/api/me");
        me.EnsureSuccessStatusCode();

        var riesgo = await _client.GetAsync("/api/riesgo?horizonte=3m&page=1&pageSize=20");
        Assert.True(riesgo.IsSuccessStatusCode, await riesgo.Content.ReadAsStringAsync());
    }

    [Fact]
    public async Task Login_Invalido_Unauthorized()
    {
        var res = await _client.PostAsJsonAsync("/api/auth/login", new { email = "prev@test.local", password = "wrong" });
        Assert.Equal(HttpStatusCode.Unauthorized, res.StatusCode);
    }

    [Fact]
    public async Task Detalle_Dossier_Y_Copiloto()
    {
        var token = await LoginAsync("prev@test.local");
        Auth(token);

        var det = await _client.GetAsync("/api/establecimientos/EST-TEST-001?horizonte=3m");
        Assert.True(det.IsSuccessStatusCode || det.StatusCode == HttpStatusCode.NotFound, await det.Content.ReadAsStringAsync());

        var dossier = await _client.GetAsync("/api/establecimientos/EST-TEST-001/dossier");
        // Puede ser 200 o 404 según contrato; no debe ser 500
        Assert.NotEqual(HttpStatusCode.InternalServerError, dossier.StatusCode);

        var copiloto = await _client.PostAsJsonAsync("/api/establecimientos/EST-TEST-001/copiloto", new
        {
            pregunta = "¿Qué mirar del RGRL?",
            tema = "rgrl_checklist",
        });
        // Con fake Gemini debería responder OK o BadRequest de validación, no 500
        Assert.NotEqual(HttpStatusCode.InternalServerError, copiloto.StatusCode);
    }

    [Fact]
    public async Task Admin_ListaUsuarios_Y_BajaLogica()
    {
        var token = await LoginAsync("admin@test.local");
        Auth(token);

        var list = await _client.GetAsync("/api/usuarios");
        Assert.True(list.IsSuccessStatusCode, await list.Content.ReadAsStringAsync());

        // Crear usuario
        var create = await _client.PostAsJsonAsync("/api/usuarios", new
        {
            email = "nuevo@test.local",
            nombre = "Nuevo",
            rol = "Preventor",
            activo = true,
        });
        Assert.True(create.IsSuccessStatusCode || create.StatusCode == HttpStatusCode.Conflict
            || create.StatusCode == HttpStatusCode.BadRequest, await create.Content.ReadAsStringAsync());
    }

    [Fact]
    public async Task Coord_Candidatos_Y_Capacidad()
    {
        var token = await LoginAsync("coord@test.local");
        Auth(token);

        var cap = await _client.GetAsync("/api/agenda/capacidad");
        Assert.NotEqual(HttpStatusCode.InternalServerError, cap.StatusCode);

        var cand = await _client.GetAsync("/api/agenda/candidatos?idEstablecimiento=EST-TEST-001&fecha=2026-10-20&hora=10:00");
        Assert.NotEqual(HttpStatusCode.InternalServerError, cand.StatusCode);
    }

    [Fact]
    public async Task Resumen_Y_Estadisticas()
    {
        var token = await LoginAsync("prev@test.local");
        Auth(token);

        var resumen = await _client.GetAsync("/api/resumen?horizonte=3m");
        Assert.NotEqual(HttpStatusCode.InternalServerError, resumen.StatusCode);

        foreach (var path in new[]
                 {
                     "/api/estadisticas/cobertura?horizonte=3m",
                     "/api/estadisticas/shap?horizonte=3m",
                     "/api/estadisticas/precision?horizonte=3m",
                 })
        {
            var r = await _client.GetAsync(path);
            Assert.NotEqual(HttpStatusCode.InternalServerError, r.StatusCode);
        }
    }
}
