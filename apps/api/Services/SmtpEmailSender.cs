using MailKit.Net.Smtp;
using MailKit.Security;
using MimeKit;

namespace PfiPrevencion.Api.Services;

public interface IEmailSender
{
    bool IsConfigured { get; }
    Task SendAsync(string toEmail, string subject, string htmlBody, CancellationToken ct = default);
}

public class SmtpEmailSender(IConfiguration config, ILogger<SmtpEmailSender> logger, IHostEnvironment env) : IEmailSender
{
    public bool IsConfigured
    {
        get
        {
            var host = config["Smtp:Host"];
            var user = config["Smtp:User"];
            var pass = config["Smtp:Password"];
            return !string.IsNullOrWhiteSpace(host)
                && !string.IsNullOrWhiteSpace(user)
                && !string.IsNullOrWhiteSpace(pass);
        }
    }

    public async Task SendAsync(string toEmail, string subject, string htmlBody, CancellationToken ct = default)
    {
        if (!IsConfigured)
            throw new InvalidOperationException(
                "SMTP no configurado. Definí Smtp:Host/User/Password (User Secrets o variables de entorno).");

        var host = config["Smtp:Host"]!;
        var port = config.GetValue("Smtp:Port", 587);
        var user = config["Smtp:User"]!;
        var pass = config["Smtp:Password"]!;
        var from = config["Smtp:From"] ?? $"Prevex <{user}>";

        var message = new MimeMessage();
        message.From.Add(MailboxAddress.Parse(from));
        message.To.Add(MailboxAddress.Parse(toEmail));
        message.Subject = subject;

        var builder = new BodyBuilder { HtmlBody = htmlBody };
        AttachLogoIfPresent(builder);
        message.Body = builder.ToMessageBody();

        using var client = new SmtpClient();
        await client.ConnectAsync(host, port, SecureSocketOptions.StartTls, ct);
        await client.AuthenticateAsync(user, pass.Replace(" ", ""), ct);
        await client.SendAsync(message, ct);
        await client.DisconnectAsync(true, ct);
        logger.LogInformation("Mail enviado a {To} ({Subject})", toEmail, subject);
    }

    void AttachLogoIfPresent(BodyBuilder builder)
    {
        var path = ResolveLogoPath();
        if (path is null) return;

        var resource = builder.LinkedResources.Add(path);
        resource.ContentId = EmailTemplates.LogoContentId;
        resource.ContentDisposition = new ContentDisposition(ContentDisposition.Inline);
        resource.ContentType.MediaType = "image";
        resource.ContentType.MediaSubtype = "png";
    }

    string? ResolveLogoPath()
    {
        var candidates = new[]
        {
            Path.Combine(AppContext.BaseDirectory, "Assets", "logo-mark.png"),
            Path.Combine(env.ContentRootPath, "Assets", "logo-mark.png"),
            Path.Combine(env.ContentRootPath, "..", "web", "public", "logo-mark.png"),
            Path.Combine(AppContext.BaseDirectory, "Assets", "logo.png"),
            Path.Combine(env.ContentRootPath, "Assets", "logo.png"),
        };

        foreach (var c in candidates)
        {
            try
            {
                var full = Path.GetFullPath(c);
                if (File.Exists(full)) return full;
            }
            catch
            {
                // ignore bad paths
            }
        }

        logger.LogWarning("No se encontró logo para embeber en el mail (Assets/logo-mark.png).");
        return null;
    }
}
