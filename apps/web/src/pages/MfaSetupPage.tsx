import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import { confirmMfa, setupMfa } from "../api";
import { useAuth } from "../auth";
import { landingFor } from "../roles";
import { needsMfaSetup } from "../mfa";
import { takePostLoginNext } from "../loginRedirect";
import { useTheme } from "../theme";
import { IconMoon, IconSun } from "../icons";

export function MfaSetupPage() {
  const { user, setUser, logout } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const [otpauthUrl, setOtpauthUrl] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!user || !needsMfaSetup(user) || otpauthUrl) return;
    let cancelled = false;
    setBusy(true);
    setError(null);
    void setupMfa()
      .then((res) => {
        if (!cancelled) setOtpauthUrl(res.otpauthUrl);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "No se pudo iniciar MFA");
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user, otpauthUrl]);

  if (!user) return <Navigate to="/login" replace />;
  if (!needsMfaSetup(user)) {
    return <Navigate to={takePostLoginNext() ?? landingFor(user.rol)} replace />;
  }

  async function onConfirm(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await confirmMfa(code.trim());
      if (user) setUser({ ...user, mfaEnabled: true, mfaSetupRequired: false });
      navigate(takePostLoginNext() ?? landingFor(user!.rol), { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Código inválido");
      setBusy(false);
    }
  }

  return (
    <div className="login-page">
      <button
        className="icon-btn login-theme-toggle"
        title={theme === "dark" ? "Modo claro" : "Modo oscuro"}
        onClick={toggleTheme}
        type="button"
      >
        {theme === "dark" ? <IconSun /> : <IconMoon />}
      </button>
      <div className="login-card mfa-setup-card">
        <div className="login-brand">
          <img className="login-logo" src="/logo.png" alt="Prevex" />
        </div>
        <h1 className="page-title" style={{ fontSize: 20, margin: "0 0 8px" }}>
          Configurar autenticación en dos pasos
        </h1>
        <p className="muted" style={{ marginTop: 0, marginBottom: 16, fontSize: 13 }}>
          Escaneá el QR con Authenticator y confirmá con un código de 6 dígitos.
        </p>

        {error && <div className="error">{error}</div>}

        <form onSubmit={onConfirm} className="form-stack">
          {otpauthUrl ? (
            <div className="mfa-qr">
              <QRCodeSVG value={otpauthUrl} size={180} />
            </div>
          ) : (
            <p className="muted" style={{ fontSize: 13 }}>
              {busy ? "Generando código QR…" : "Preparando MFA…"}
            </p>
          )}
          <div className="field">
            <label htmlFor="mfa-setup-code">Código</label>
            <input
              id="mfa-setup-code"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              inputMode="numeric"
              autoComplete="one-time-code"
              placeholder="000000"
              required
              minLength={6}
              disabled={!otpauthUrl || busy}
            />
          </div>
          <button
            className="btn success"
            type="submit"
            disabled={busy || !otpauthUrl || code.trim().length < 6}
          >
            {busy ? "Confirmando…" : "Confirmar MFA"}
          </button>
          <button
            type="button"
            className="ghost-btn"
            style={{ width: "100%" }}
            onClick={() => {
              logout();
              navigate("/login", { replace: true });
            }}
          >
            Cerrar sesión
          </button>
        </form>
      </div>
    </div>
  );
}
