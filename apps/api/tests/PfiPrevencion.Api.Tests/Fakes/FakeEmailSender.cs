using PfiPrevencion.Api.Services;

namespace PfiPrevencion.Api.Tests.Fakes;

public sealed class FakeEmailSender : IEmailSender
{
    public bool IsConfigured => true;
    public List<(string To, string Subject, string Html)> Sent { get; } = [];

    public Task SendAsync(string to, string subject, string htmlBody, CancellationToken ct = default)
    {
        Sent.Add((to, subject, htmlBody));
        return Task.CompletedTask;
    }
}
