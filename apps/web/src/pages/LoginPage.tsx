import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth";
import { needsMfaSetup } from "../mfa";
import { landingFor } from "../roles";
import {
  peekPostLoginNext,
  rememberPostLoginNext,
  sanitizeNextPath,
  takePostLoginNext,
} from "../loginRedirect";
import { LoginWaveField } from "../components/LoginWaveField";
import { IconEye, IconEyeOff, IconMoon, IconSun } from "../icons";
import { useTheme } from "../theme";
import type { User } from "../api";

function resolveAfterLogin(u: User, nextFromQuery: string | null) {
  const next = sanitizeNextPath(nextFromQuery) ?? peekPostLoginNext();
  if (needsMfaSetup(u)) {
    if (next) rememberPostLoginNext(next);
    return "/mfa-setup";
  }
  return sanitizeNextPath(nextFromQuery) ?? takePostLoginNext() ?? landingFor(u.rol);
}

export function LoginPage() {
  const { user, login, finishMfa } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const nextParam = params.get("next");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [mfaToken, setMfaToken] = useState<string | null>(null);
  const [mfaCode, setMfaCode] = useState("");

  if (user) return <Navigate to={resolveAfterLogin(user, nextParam)} replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      if (mfaToken) {
        const loggedIn = await finishMfa(mfaToken, mfaCode.trim());
        navigate(resolveAfterLogin(loggedIn, nextParam));
        return;
      }
      const result = await login(email, password);
      if ("mfaRequired" in result && result.mfaRequired) {
        setMfaToken(result.mfaToken);
        return;
      }
      navigate(resolveAfterLogin(result.user, nextParam));
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo iniciar sesión");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <LoginWaveField theme={theme} />
      <button
        className="icon-btn login-theme-toggle"
        title={theme === "dark" ? "Modo claro" : "Modo oscuro"}
        onClick={toggleTheme}
      >
        {theme === "dark" ? <IconSun /> : <IconMoon />}
      </button>
      <form className="login-card" onSubmit={onSubmit}>
        <div className="login-brand">
          <img className="login-logo" src="/logo.png" alt="Prevex" />
        </div>
        {error && <div className="error">{error}</div>}
        {!mfaToken ? (
          <>
            <div className="field">
              <label htmlFor="email">Email</label>
              <input
                id="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="username"
              />
            </div>
            <div className="field password-field">
              <label htmlFor="password">Contraseña</label>
              <input
                id="password"
                type={showPassword ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
              />
              <button
                type="button"
                className="password-toggle"
                title={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                onClick={() => setShowPassword((v) => !v)}
              >
                {showPassword ? <IconEyeOff size={16} /> : <IconEye size={16} />}
              </button>
            </div>
            <button className="btn" type="submit" disabled={loading}>
              {loading ? "Ingresando…" : "Ingresar"}
            </button>
            <p className="login-forgot">
              <Link to="/recuperar">¿Olvidaste tu contraseña?</Link>
            </p>
          </>
        ) : (
          <>
            <p className="muted" style={{ marginTop: 0 }}>
              Ingresá el código de tu app Authenticator.
            </p>
            <div className="field">
              <label htmlFor="mfa">Código MFA</label>
              <input
                id="mfa"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={mfaCode}
                onChange={(e) => setMfaCode(e.target.value)}
                placeholder="000000"
              />
            </div>
            <button className="btn" type="submit" disabled={loading || mfaCode.trim().length < 6}>
              {loading ? "Verificando…" : "Verificar"}
            </button>
            <button
              type="button"
              className="ghost-btn"
              style={{ marginTop: 8, width: "100%" }}
              onClick={() => {
                setMfaToken(null);
                setMfaCode("");
                setError(null);
              }}
            >
              Volver
            </button>
          </>
        )}
      </form>
    </div>
  );
}
