import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { forgotPassword, resetPassword } from "../api";

export function RecuperarPage() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [nueva, setNueva] = useState("");
  const [confirm, setConfirm] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function onRequest(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    setMsg(null);
    try {
      await forgotPassword(email.trim());
      setMsg("Si el email existe, vas a recibir un enlace para restablecer la contraseña.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo enviar el mail");
    } finally {
      setSaving(false);
    }
  }

  async function onReset(e: FormEvent) {
    e.preventDefault();
    if (!token) return;
    if (nueva.length < 8) {
      setError("La contraseña debe tener al menos 8 caracteres.");
      return;
    }
    if (nueva !== confirm) {
      setError("La confirmación no coincide.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await resetPassword(token, nueva);
      setMsg("Contraseña actualizada. Redirigiendo…");
      window.setTimeout(() => navigate("/login"), 1200);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo restablecer");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={token ? onReset : onRequest}>
        <h1 className="page-title" style={{ fontSize: 20 }}>
          {token ? "Nueva contraseña" : "Olvidé mi contraseña"}
        </h1>
        {error && <div className="error">{error}</div>}
        {msg && <div className="success">{msg}</div>}
        {!token ? (
          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="username"
            />
          </div>
        ) : (
          <>
            <div className="field">
              <label htmlFor="nueva">Nueva contraseña</label>
              <input
                id="nueva"
                type="password"
                value={nueva}
                onChange={(e) => setNueva(e.target.value)}
                autoComplete="new-password"
              />
            </div>
            <div className="field">
              <label htmlFor="confirm">Confirmar</label>
              <input
                id="confirm"
                type="password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                autoComplete="new-password"
              />
            </div>
          </>
        )}
        <button className="btn success" type="submit" disabled={saving}>
          {saving ? "Enviando…" : token ? "Guardar" : "Enviar enlace"}
        </button>
        <p style={{ marginTop: 12 }}>
          <Link to="/login">Volver al login</Link>
        </p>
      </form>
    </div>
  );
}
