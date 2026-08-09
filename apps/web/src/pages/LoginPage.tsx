import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { landingFor } from "../roles";
import { LoginWaveField } from "../components/LoginWaveField";
import { IconEye, IconEyeOff, IconMoon, IconSun } from "../icons";
import { useTheme } from "../theme";

export function LoginPage() {
  const { user, login } = useAuth();
  const { theme, toggleTheme } = useTheme();
  const navigate = useNavigate();
  const [email, setEmail] = useState("admin@pfi.local");
  const [password, setPassword] = useState("Admin123!");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (user) return <Navigate to={landingFor(user.rol)} replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const loggedIn = await login(email, password);
      navigate(landingFor(loggedIn.rol));
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
        <div className="field">
          <label htmlFor="email">Email</label>
          <input id="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="username" />
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
      </form>
    </div>
  );
}
