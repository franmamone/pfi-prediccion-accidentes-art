using PfiPrevencion.Api.Services;

namespace PfiPrevencion.Api.Tests;

public class PiiTextSanitizerTests
{
    [Theory]
    [InlineData("CUIT 30-71234567-8 del Sr. Pérez", "[id]")]
    [InlineData("escribir a juan@empresa.com", "[email]")]
    [InlineData("llamar al 11 4567-8901", "[tel]")]
    [InlineData("DNI: 30123456", "[doc]")]
    [InlineData("Av. Corrientes 1234 piso 2", "[domicilio]")]
    public void Scrub_reemplaza_patrones_tipados(string input, string expectedToken)
    {
        var outText = PiiTextSanitizer.Scrub(input);
        Assert.Contains(expectedToken, outText, StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("71234567", outText);
        Assert.DoesNotContain("juan@", outText, StringComparison.OrdinalIgnoreCase);
    }

    [Fact]
    public void ForLlmOperationalNote_omite_prosa_con_domicilio()
    {
        var note = PiiTextSanitizer.ForLlmOperationalNote(
            "El trabajador vive en Calle Falsa 123 y dejó el teléfono 1145678901");
        Assert.Equal("[detalle omitido por privacidad]", note);
    }

    [Fact]
    public void ForLlmOperationalNote_conserva_categoria_corta()
    {
        var note = PiiTextSanitizer.ForLlmOperationalNote("Orden y Limpieza");
        Assert.Equal("Orden y Limpieza", note);
    }
}
