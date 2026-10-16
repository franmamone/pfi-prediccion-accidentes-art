using PfiPrevencion.Api.Services;

namespace PfiPrevencion.Api.Tests;

public class EmailTemplatesTests
{
    [Fact]
    public void Invite_ContieneCtaYNombre()
    {
        var html = EmailTemplates.Invite("Ana", "https://app/invitar?token=1");
        Assert.Contains("Ana", html);
        Assert.Contains("https://app/invitar?token=1", html);
        Assert.Contains("Prevex", html);
        Assert.Contains(EmailTemplates.LogoContentId, html);
    }

    [Fact]
    public void ResetPassword_ContieneEnlace()
    {
        var html = EmailTemplates.ResetPassword("Luis", "https://app/recuperar?t=x");
        Assert.Contains("Luis", html);
        Assert.Contains("https://app/recuperar?t=x", html);
    }

    [Fact]
    public void VisitAssigned_ReprogramacionYAlta()
    {
        var alta = EmailTemplates.VisitAssigned("P", "2026-10-20", "10:00", "EST-1", "https://app/agenda", false);
        Assert.Contains("EST-1", alta);
        Assert.Contains("10:00", alta);

        var repro = EmailTemplates.VisitAssigned("P", "2026-10-21", "11:30", "EST-2", "https://app/agenda", true);
        Assert.Contains("EST-2", repro);
        Assert.Contains("actualizada", repro, StringComparison.OrdinalIgnoreCase);
    }
}
