import { useEffect, useState, type FormEvent } from "react";
import { changePassword, updateProfile } from "../api";
import { useAuth } from "../auth";
import { IconEye, IconEyeOff } from "../icons";

export function PerfilPage() {
  const { user, setUser } = useAuth();
  const [nombre, setNombre] = useState(user?.nombre ?? "");
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [showActual, setShowActual] = useState(false);
  const [showNueva, setShowNueva] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPass, setSavingPass] = useState(false);

  useEffect(() => {
    setNombre(user?.nombre ?? "");
  }, [user?.nombre]);

  async function onSaveProfile(e: FormEvent) {
    e.preventDefault();
    setSavingProfile(true);
    setMsg(null);
    setErr(null);
    try {
      const updated = await updateProfile(nombre);
      setUser(updated);
      setMsg("Perfil actualizado.");
    } catch (error) {
      setErr(error instanceof Error ? error.message : "No se pudo guardar el perfil");
    } finally {
      setSavingProfile(false);
    }
  }

  async function onChangePassword(e: FormEvent) {
    e.preventDefault();
    setSavingPass(true);
    setMsg(null);
    setErr(null);
    if (nueva !== confirmacion) {
      setErr("La confirmación no coincide con la nueva contraseña.");
      setSavingPass(false);
      return;
    }
    try {
      await changePassword(actual, nueva);
      setActual("");
      setNueva("");
      setConfirmacion("");
      setMsg("Contraseña actualizada.");
    } catch (error) {
      setErr(error instanceof Error ? error.message : "No se pudo cambiar la contraseña");
    } finally {
      setSavingPass(false);
    }
  }

  const iniciales = (user?.nombre ?? user?.email ?? "?")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]?.toUpperCase() ?? "")
    .join("") || "?";

  return (
    <div className="profile-page">
      <div className="profile-page-inner">
        <div className="panel profile-hero">
          <div className="profile-avatar" aria-hidden="true">
            {iniciales}
          </div>
          <div className="profile-hero-info">
            <h1 className="page-title" style={{ margin: 0 }}>
              {user?.nombre ?? "Mi perfil"}
            </h1>
            <div className="profile-hero-meta">
              <span className={`profile-role ${(user?.rol ?? "").toLowerCase()}`}>{user?.rol}</span>
              <span className="muted">{user?.email}</span>
            </div>
          </div>
        </div>

        {msg && <div className="success">{msg}</div>}
        {err && <div className="error">{err}</div>}

        <div className="profile-grid">
          <div className="panel">
            <h2 className="page-title" style={{ fontSize: 16, marginBottom: 4 }}>
              Datos de la cuenta
            </h2>
            <p className="muted" style={{ marginTop: 0, marginBottom: 14, fontSize: 13 }}>
              Email y rol son gestionados por administración.
            </p>
            <form onSubmit={onSaveProfile} className="form-stack">
              <div className="field">
                <label>Email</label>
                <input value={user?.email ?? ""} disabled />
              </div>
              <div className="field">
                <label>Rol</label>
                <input value={user?.rol ?? ""} disabled />
              </div>
              <div className="field">
                <label>Nombre visible</label>
                <input value={nombre} onChange={(e) => setNombre(e.target.value)} required minLength={2} />
              </div>
              <button className="btn" type="submit" disabled={savingProfile}>
                {savingProfile ? "Guardando…" : "Guardar perfil"}
              </button>
            </form>
          </div>

          <div className="panel">
            <h2 className="page-title" style={{ fontSize: 16, marginBottom: 4 }}>
              Cambiar contraseña
            </h2>
            <p className="muted" style={{ marginTop: 0, marginBottom: 14, fontSize: 13 }}>
              Mínimo 8 caracteres. Vas a seguir con la sesión abierta.
            </p>
            <form onSubmit={onChangePassword} className="form-stack">
            <div className="field password-field">
              <label>Contraseña actual</label>
              <input
                type={showActual ? "text" : "password"}
                value={actual}
                onChange={(e) => setActual(e.target.value)}
                required
                autoComplete="current-password"
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowActual((v) => !v)}
                title={showActual ? "Ocultar" : "Mostrar"}
              >
                {showActual ? <IconEyeOff size={16} /> : <IconEye size={16} />}
              </button>
            </div>
            <div className="field password-field">
              <label>Nueva contraseña</label>
              <input
                type={showNueva ? "text" : "password"}
                value={nueva}
                onChange={(e) => setNueva(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowNueva((v) => !v)}
                title={showNueva ? "Ocultar" : "Mostrar"}
              >
                {showNueva ? <IconEyeOff size={16} /> : <IconEye size={16} />}
              </button>
            </div>
            <div className="field">
              <label>Confirmar nueva</label>
              <input
                type="password"
                value={confirmacion}
                onChange={(e) => setConfirmacion(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
              />
            </div>
            <button className="btn" type="submit" disabled={savingPass}>
              {savingPass ? "Actualizando…" : "Actualizar contraseña"}
            </button>
          </form>
          </div>
        </div>
      </div>
    </div>
  );
}
