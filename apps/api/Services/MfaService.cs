using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using OtpNet;

namespace PfiPrevencion.Api.Services;

public class MfaService
{
    public const string Issuer = "Prevex";

    public static string GenerateSecret()
    {
        var key = KeyGeneration.GenerateRandomKey(20);
        return Base32Encoding.ToString(key);
    }

    public static string BuildOtpAuthUrl(string email, string secret) =>
        $"otpauth://totp/{Uri.EscapeDataString(Issuer)}:{Uri.EscapeDataString(email)}?secret={secret}&issuer={Uri.EscapeDataString(Issuer)}&digits=6&period=30";

    public static bool VerifyCode(string secret, string code)
    {
        if (string.IsNullOrWhiteSpace(secret) || string.IsNullOrWhiteSpace(code)) return false;
        code = code.Trim().Replace(" ", "");
        try
        {
            var totp = new Totp(Base32Encoding.ToBytes(secret));
            return totp.VerifyTotp(code, out _, new VerificationWindow(1, 1));
        }
        catch
        {
            return false;
        }
    }

    public static (List<string> Plain, string JsonHashes) GenerateRecoveryCodes(int count = 8)
    {
        var plain = new List<string>();
        var hashes = new List<string>();
        for (var i = 0; i < count; i++)
        {
            var code = Convert.ToHexString(RandomNumberGenerator.GetBytes(4)).ToLowerInvariant();
            plain.Add(code);
            hashes.Add(HashRecovery(code));
        }
        return (plain, JsonSerializer.Serialize(hashes));
    }

    public static string HashRecovery(string code)
    {
        var bytes = SHA256.HashData(Encoding.UTF8.GetBytes(code.Trim().ToLowerInvariant()));
        return Convert.ToHexString(bytes).ToLowerInvariant();
    }

    public static bool TryConsumeRecovery(string? jsonHashes, string code, out string? updatedJson)
    {
        updatedJson = jsonHashes;
        if (string.IsNullOrWhiteSpace(jsonHashes)) return false;
        var list = JsonSerializer.Deserialize<List<string>>(jsonHashes) ?? [];
        var hash = HashRecovery(code);
        var idx = list.FindIndex(h => h == hash);
        if (idx < 0) return false;
        list.RemoveAt(idx);
        updatedJson = JsonSerializer.Serialize(list);
        return true;
    }
}
