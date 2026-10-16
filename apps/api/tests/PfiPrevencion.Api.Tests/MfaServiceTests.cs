using PfiPrevencion.Api.Services;

namespace PfiPrevencion.Api.Tests;

public class MfaServiceTests
{
    [Fact]
    public void GenerateSecret_NoVacio()
    {
        var s = MfaService.GenerateSecret();
        Assert.False(string.IsNullOrWhiteSpace(s));
        Assert.True(s.Length >= 16);
    }

    [Fact]
    public void BuildOtpAuthUrl_ContieneIssuerYEmail()
    {
        var url = MfaService.BuildOtpAuthUrl("a@b.com", "SECRETBASE32");
        Assert.Contains("otpauth://totp/", url);
        Assert.Contains("Prevex", url);
        Assert.Contains("a%40b.com", url);
    }

    [Fact]
    public void VerifyCode_SecretOCodigoVacio_False()
    {
        Assert.False(MfaService.VerifyCode("", "123456"));
        Assert.False(MfaService.VerifyCode("ABC", ""));
        Assert.False(MfaService.VerifyCode("!!!!", "123456"));
    }

    [Fact]
    public void VerifyCode_CodigoIncorrecto_False()
    {
        var secret = MfaService.GenerateSecret();
        Assert.False(MfaService.VerifyCode(secret, "000000"));
    }

    [Fact]
    public void RecoveryCodes_GenerateConsume()
    {
        var (plain, json) = MfaService.GenerateRecoveryCodes(4);
        Assert.Equal(4, plain.Count);
        Assert.Contains("[", json);

        var ok = MfaService.TryConsumeRecovery(json, plain[0], out var updated);
        Assert.True(ok);
        Assert.NotNull(updated);
        Assert.False(MfaService.TryConsumeRecovery(updated, plain[0], out _));
        Assert.False(MfaService.TryConsumeRecovery(null, "x", out _));
        Assert.False(MfaService.TryConsumeRecovery("[]", "zzzz", out _));
    }

    [Fact]
    public void HashRecovery_Estable()
    {
        var a = MfaService.HashRecovery("AbCd");
        var b = MfaService.HashRecovery("abcd");
        Assert.Equal(a, b);
    }
}
