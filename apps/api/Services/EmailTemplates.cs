using System.Net;

namespace PfiPrevencion.Api.Services;

/// <summary>Plantillas HTML para mails transaccionales (logo CID + botón CTA).</summary>
public static class EmailTemplates
{
    public const string LogoContentId = "prevex-logo";

    public static string Invite(string nombre, string actionUrl) =>
        Build(
            preheader: "Te invitaron a Prevex. Creá tu contraseña para activar la cuenta.",
            eyebrow: "Invitación",
            title: "Bienvenido a Prevex",
            greeting: $"Hola {nombre},",
            body: "Te invitaron a la plataforma de prevención Prevex. Creá tu contraseña para activar la cuenta y empezar a operar.",
            ctaLabel: "Crear contraseña",
            actionUrl: actionUrl,
            validity: "Este enlace vence en 7 días.",
            footnote: "Si no esperabas esta invitación, podés ignorar este mensaje.");

    public static string ResetPassword(string nombre, string actionUrl) =>
        Build(
            preheader: "Restablecé tu contraseña de Prevex.",
            eyebrow: "Seguridad",
            title: "Restablecer contraseña",
            greeting: $"Hola {nombre},",
            body: "Recibimos un pedido para restablecer la contraseña de tu cuenta Prevex. Si fuiste vos, usá el botón de abajo.",
            ctaLabel: "Elegir nueva contraseña",
            actionUrl: actionUrl,
            validity: "Este enlace vence en 1 hora.",
            footnote: "Si no pediste este cambio, ignorá el mail. Tu contraseña actual sigue vigente.");

    public static string VisitAssigned(
        string nombre,
        string fecha,
        string hora,
        string idEstablecimiento,
        string actionUrl,
        bool reprogramacion)
    {
        var safeFecha = WebUtility.HtmlEncode(fecha);
        var safeHora = WebUtility.HtmlEncode(hora);
        var safeEst = WebUtility.HtmlEncode(idEstablecimiento);
        var details = $"""
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-top:16px;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;">
              <tr><td style="padding:14px 16px;font-size:14px;line-height:1.55;color:#334155;">
                <div style="margin:0 0 8px;"><strong style="color:#0f172a;">Fecha:</strong> {safeFecha}</div>
                <div style="margin:0 0 8px;"><strong style="color:#0f172a;">Hora:</strong> {safeHora}</div>
                <div style="margin:0;"><strong style="color:#0f172a;">Establecimiento:</strong> {safeEst}</div>
              </td></tr>
            </table>
            """;

        return Build(
            preheader: reprogramacion
                ? $"Turno actualizado: {fecha} {hora}"
                : $"Nuevo turno: {fecha} {hora}",
            eyebrow: reprogramacion ? "Turno actualizado" : "Nuevo turno",
            title: reprogramacion ? "Tu visita fue actualizada" : "Tenés una visita asignada",
            greeting: $"Hola {nombre},",
            body: reprogramacion
                ? "Actualizaron un turno en tu agenda de Prevex. Revisá el detalle y abrí el turno."
                : "Te asignaron una visita preventiva. Revisá el detalle y abrí el turno en tu agenda.",
            ctaLabel: "Ver turno en mi agenda",
            actionUrl: actionUrl,
            validity: "Al abrir el enlace vas a ver el turno en tu agenda (si no estás logueado, primero iniciá sesión).",
            footnote: "Si el turno no te corresponde, consultá con tu coordinador.",
            detailsHtml: details);
    }

    public static string Build(
        string preheader,
        string eyebrow,
        string title,
        string greeting,
        string body,
        string ctaLabel,
        string actionUrl,
        string validity,
        string footnote,
        string? detailsHtml = null)
    {
        var safeGreeting = WebUtility.HtmlEncode(greeting);
        var safeEyebrow = WebUtility.HtmlEncode(eyebrow);
        var safeTitle = WebUtility.HtmlEncode(title);
        var safeBody = WebUtility.HtmlEncode(body);
        var safeCta = WebUtility.HtmlEncode(ctaLabel);
        var safeValidity = WebUtility.HtmlEncode(validity);
        var safeFoot = WebUtility.HtmlEncode(footnote);
        var safeUrl = WebUtility.HtmlEncode(actionUrl);
        var safePre = WebUtility.HtmlEncode(preheader);
        var detailsBlock = string.IsNullOrWhiteSpace(detailsHtml)
            ? ""
            : $"<div style=\"margin:0;\">{detailsHtml}</div>";

        return $$"""
            <!DOCTYPE html>
            <html lang="es">
            <head>
              <meta charset="utf-8" />
              <meta name="viewport" content="width=device-width, initial-scale=1" />
              <meta name="color-scheme" content="light" />
              <title>{{safeTitle}}</title>
            </head>
            <body style="margin:0;padding:0;background:#eef2f7;font-family:Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#0f172a;">
              <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{{safePre}}</div>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#eef2f7;padding:32px 12px;">
                <tr>
                  <td align="center">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:560px;background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #e2e8f0;box-shadow:0 8px 24px rgba(15,23,42,0.06);">
                      <tr>
                        <td style="background:linear-gradient(135deg,#0c1220 0%,#1e3a8a 100%);padding:28px 32px;text-align:center;">
                          <img src="cid:{{LogoContentId}}" width="56" height="56" alt="Prevex" style="display:block;margin:0 auto 12px;border:0;border-radius:12px;" />
                          <div style="font-size:22px;font-weight:800;letter-spacing:0.12em;color:#ffffff;">PREVEX</div>
                          <div style="margin-top:6px;font-size:12px;color:#93c5fd;letter-spacing:0.04em;">Prevención inteligente</div>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:32px 32px 8px;">
                          <div style="display:inline-block;padding:4px 10px;border-radius:999px;background:#eff6ff;color:#1d4ed8;font-size:11px;font-weight:700;letter-spacing:0.04em;text-transform:uppercase;">{{safeEyebrow}}</div>
                          <h1 style="margin:14px 0 0;font-size:22px;line-height:1.3;font-weight:700;color:#0f172a;">{{safeTitle}}</h1>
                          <p style="margin:18px 0 0;font-size:15px;line-height:1.55;color:#334155;">{{safeGreeting}}</p>
                          <p style="margin:10px 0 0;font-size:15px;line-height:1.55;color:#475569;">{{safeBody}}</p>
                          {{detailsBlock}}
                        </td>
                      </tr>
                      <tr>
                        <td align="center" style="padding:24px 32px 8px;">
                          <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                            <tr>
                              <td style="border-radius:10px;background:#2563eb;">
                                <a href="{{safeUrl}}" target="_blank" style="display:inline-block;padding:14px 28px;font-size:15px;font-weight:700;color:#ffffff;text-decoration:none;border-radius:10px;">
                                  {{safeCta}}
                                </a>
                              </td>
                            </tr>
                          </table>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:16px 32px 8px;">
                          <p style="margin:0;font-size:12px;line-height:1.5;color:#64748b;">{{safeValidity}}</p>
                          <p style="margin:12px 0 0;font-size:11px;line-height:1.5;color:#94a3b8;word-break:break-all;">
                            Si el botón no funciona, copiá este enlace:<br />
                            <a href="{{safeUrl}}" style="color:#2563eb;text-decoration:underline;">{{safeUrl}}</a>
                          </p>
                        </td>
                      </tr>
                      <tr>
                        <td style="padding:20px 32px 28px;border-top:1px solid #e2e8f0;">
                          <p style="margin:0;font-size:12px;line-height:1.5;color:#64748b;">{{safeFoot}}</p>
                          <p style="margin:14px 0 0;font-size:11px;color:#94a3b8;">© Prevex · Sistema predictivo de prevención</p>
                        </td>
                      </tr>
                    </table>
                  </td>
                </tr>
              </table>
            </body>
            </html>
            """;
    }
}
