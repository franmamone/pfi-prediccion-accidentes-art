import { useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { acceptInvite } from "../api";

export function InvitarPage() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const navigate = useNavigate();
  const [nueva, setNueva] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const [saving, setSaving] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
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
      await acceptInvite(token, nueva);
      setOk(true);
      window.setTimeout(() => navigate("/login"), 1500);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo activar la cuenta");
    } finally {
      setSaving(false);
    }
  }

  if (!token) {
    return (
      <div className="login-page">
        <div className="login-card">
          <h1 className="page-title">Invitación inválida</h1>
          <p className="muted">Falta el token en el enlace.</p>
          <Link to="/login">Ir al login</Link>
        </div>
      </div>
    );
  }

  return (
    <div className="login-page">
      <form className="login-card" onSubmit={onSubmit}>
        <h1 className="page-title" style={{ fontSize: 20 }}>
          Crear contraseña
        </h1>
        <p className="muted">Activá tu cuenta de Prevex.</p>
        {error && <div className="error">{error}</div>}
        {ok && <div className="success">Listo. Redirigiendo al login…</div>}
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
        <button className="btn success" type="submit" disabled={saving || ok}>
          {saving ? "Guardando…" : "Activar cuenta"}
        </button>
      </form>
    </div>
  );
}
