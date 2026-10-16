using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging.Abstractions;
using PfiPrevencion.Api.Data;
using PfiPrevencion.Api.Services;
using PfiPrevencion.Api.Tests.Fakes;

namespace PfiPrevencion.Api.Tests;

public class AuthTokenServiceTests
{
    private static AppDbContext NewDb()
    {
        var opts = new DbContextOptionsBuilder<AppDbContext>()
            .UseInMemoryDatabase($"PfiTok_{Guid.NewGuid():N}")
            .Options;
        return new AppDbContext(opts);
    }

    [Fact]
    public void HashToken_Y_NewRaw_Ok()
    {
        var raw = AuthTokenService.NewRawToken();
        Assert.Equal(64, raw.Length);
        Assert.Equal(AuthTokenService.HashToken(raw), AuthTokenService.HashToken(raw));
        Assert.NotEqual(AuthTokenService.HashToken(raw), AuthTokenService.HashToken("other"));
    }

    [Fact]
    public async Task CreateFindSend_InviteResetNotify()
    {
        await using var db = NewDb();
        var email = new FakeEmailSender();
        var cfg = new ConfigurationBuilder().AddInMemoryCollection(new Dictionary<string, string?>
        {
            ["App:PublicBaseUrl"] = "http://localhost:5173",
        }).Build();
        var svc = new AuthTokenService(db, cfg, email, NullLogger<AuthTokenService>.Instance);

        var user = new Usuario
        {
            Email = "u@test.local",
            Nombre = "U",
            Rol = "Preventor",
            PasswordHash = "x",
            Activo = true,
            CreadoEn = DateTime.UtcNow,
        };
        db.Usuarios.Add(user);
        await db.SaveChangesAsync();

        var (raw, row) = await svc.CreateTokenAsync(user.Id, "invite", TimeSpan.FromHours(1));
        Assert.True(row.Id > 0);
        var found = await svc.FindValidAsync(raw, "invite");
        Assert.NotNull(found);

        await svc.SendInviteAsync(user);
        await svc.SendResetAsync(user);
        Assert.True(email.Sent.Count >= 2);

        var agenda = new AgendaItem
        {
            UsuarioId = user.Id,
            IdEstablecimiento = "E1",
            Periodo = "2025-01",
            Horizonte = "3m",
            FechaPlanificada = DateOnly.FromDateTime(DateTime.Today.AddDays(1)),
            HoraPlanificada = new TimeOnly(10, 0),
            Estado = "programada",
            CreadoEn = DateTime.UtcNow,
            ActualizadoEn = DateTime.UtcNow,
        };
        await svc.TryNotifyVisitaAsignadaAsync(user, agenda, false);
        await svc.TryNotifyVisitaAsignadaAsync(user, agenda, true);
        Assert.True(email.Sent.Count >= 4);

        user.Rol = "Administrador";
        var before = email.Sent.Count;
        await svc.TryNotifyVisitaAsignadaAsync(user, agenda, false);
        Assert.Equal(before, email.Sent.Count);
    }
}
