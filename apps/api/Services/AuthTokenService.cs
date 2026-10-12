using System.Security.Cryptography;
using System.Text;
using Microsoft.EntityFrameworkCore;
using PfiPrevencion.Api.Data;

namespace PfiPrevencion.Api.Services;

public class AuthTokenService(
    AppDbContext db,
    IConfiguration config,
    IEmailSender email,
    ILogger<AuthTokenService> logger)
{
    public string PublicBaseUrl =>
        (config["App:PublicBaseUrl"] ?? "http://localhost:5173").TrimEnd('/');

    public static string HashToken(string raw)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(raw));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }

    public static string NewRawToken() => Convert.ToHexString(RandomNumberGenerator.GetBytes(32)).ToLowerInvariant();

    public async Task<(string Raw, AuthToken Row)> CreateTokenAsync(
        int usuarioId, string tipo, TimeSpan ttl, CancellationToken ct = default)
    {
        var raw = NewRawToken();
        var row = new AuthToken
        {
            UsuarioId = usuarioId,
            Tipo = tipo,
            TokenHash = HashToken(raw),
            ExpiraEn = DateTime.UtcNow.Add(ttl),
            CreadoEn = DateTime.UtcNow,
        };
        db.AuthTokens.Add(row);
        await db.SaveChangesAsync(ct);
        return (raw, row);
    }

    public async Task<AuthToken?> FindValidAsync(string raw, string tipo, CancellationToken ct = default)
    {
        var hash = HashToken(raw);
        return await db.AuthTokens
            .Include(t => t.Usuario)
            .FirstOrDefaultAsync(t =>
                t.TokenHash == hash
                && t.Tipo == tipo
                && t.UsadoEn == null
                && t.ExpiraEn > DateTime.UtcNow, ct);
    }

    public async Task SendInviteAsync(Usuario user, CancellationToken ct = default)
    {
        var (raw, _) = await CreateTokenAsync(user.Id, "invite", TimeSpan.FromDays(7), ct);
        var link = $"{PublicBaseUrl}/invitar?token={raw}";
        var html = EmailTemplates.Invite(user.Nombre, link);
        await email.SendAsync(user.Email, "Invitación a Prevex", html, ct);
    }

    public async Task SendResetAsync(Usuario user, CancellationToken ct = default)
    {
        var (raw, _) = await CreateTokenAsync(user.Id, "reset", TimeSpan.FromHours(1), ct);
        var link = $"{PublicBaseUrl}/recuperar?token={raw}";
        var html = EmailTemplates.ResetPassword(user.Nombre, link);
        await email.SendAsync(user.Email, "Restablecer contraseña - Prevex", html, ct);
    }

    /// <summary>
    /// Notifica al preventor (soft-fail: no rompe la asignación si SMTP falla o no está configurado).
    /// </summary>
    public async Task TryNotifyVisitaAsignadaAsync(
        Usuario preventor,
        AgendaItem agenda,
        bool reprogramacion,
        CancellationToken ct = default)
    {
        if (preventor.Rol != "Prevencionista") return;
        if (!email.IsConfigured)
        {
            logger.LogWarning(
                "SMTP no configurado: no se envió mail de turno {AgendaId} a {Email}",
                agenda.Id, preventor.Email);
            return;
        }

        try
        {
            var link = $"{PublicBaseUrl}/agenda?visita={agenda.Id}";
            var fecha = agenda.FechaPlanificada.ToString("dd/MM/yyyy");
            var hora = agenda.HoraPlanificada.ToString("HH\\:mm");
            var html = EmailTemplates.VisitAssigned(
                preventor.Nombre,
                fecha,
                hora,
                agenda.IdEstablecimiento,
                link,
                reprogramacion);
            var subject = reprogramacion
                ? $"Turno actualizado · {fecha} {hora} - Prevex"
                : $"Nuevo turno · {fecha} {hora} - Prevex";
            await email.SendAsync(preventor.Email, subject, html, ct);
        }
        catch (Exception ex)
        {
            logger.LogError(ex,
                "No se pudo enviar mail de turno {AgendaId} a {Email}",
                agenda.Id, preventor.Email);
        }
    }
}
