import { useEffect, useState, type FormEvent } from "react";
import { Navigate } from "react-router-dom";
import {
  createUsuario,
  fetchUsuariosAdmin,
  reenviarInvitacion,
  updateUsuario,
  type DisponibilidadDia,
  type UsuarioAdmin,
} from "../api";
import { useAuth } from "../auth";
import { CABA_CENTER, CabaLocationPicker } from "../components/CabaLocationPicker";
import { Select } from "../components/Select";
import { TimeField } from "../components/TimeField";
import { EmptyState } from "../components/UiKit";
import { esAdmin } from "../roles";

const DIAS: { id: number; label: string }[] = [
  { id: 1, label: "Lun" },
  { id: 2, label: "Mar" },
  { id: 3, label: "Mié" },
  { id: 4, label: "Jue" },
  { id: 5, label: "Vie" },
  { id: 6, label: "Sáb" },
  { id: 7, label: "Dom" },
];

const CABA_DEFAULT = { lat: CABA_CENTER[0], lon: CABA_CENTER[1] };

type DispDraft = Record<number, { on: boolean; desde: string; hasta: string }>;

function emptyDisp(): DispDraft {
  const d: DispDraft = {};
  for (const day of DIAS) {
    d[day.id] = {
      on: day.id <= 5,
      desde: "09:00",
      hasta: "17:00",
    };
  }
  return d;
}

function fromDisponibilidad(rows?: DisponibilidadDia[]): DispDraft {
  const d = emptyDisp();
  for (const day of DIAS) d[day.id].on = false;
  for (const r of rows ?? []) {
    d[r.diaSemana] = { on: true, desde: r.horaDesde.slice(0, 5), hasta: r.horaHasta.slice(0, 5) };
  }
  return d;
}

function toDisponibilidad(d: DispDraft): DisponibilidadDia[] {
  return DIAS.filter((x) => d[x.id]?.on).map((x) => ({
    diaSemana: x.id,
    horaDesde: d[x.id].desde,
    horaHasta: d[x.id].hasta,
  }));
}

function rolBadgeClass(rol: string): string {
  const r = rol.toLowerCase();
  if (r === "admin") return "badge rol-admin";
  if (r === "coordinador") return "badge rol-coordinador";
  return "badge rol-prevencionista";
}

function estadoBadge(u: UsuarioAdmin): { label: string; className: string } {
  if (!u.activo) return { label: "Inactivo", className: "badge estado-cancelada" };
  if (u.debeCambiarPassword) return { label: "Pendiente invite", className: "badge estado-pendiente" };
  return { label: "Activo", className: "badge estado-realizada" };
}

function mfaBadge(u: UsuarioAdmin): { label: string; className: string } {
  if (u.mfaEnabled) return { label: "MFA activo", className: "badge estado-realizada" };
  if (u.mfaRequired) return { label: "MFA pendiente", className: "badge estado-pendiente" };
  return { label: "Sin MFA", className: "badge" };
}

export function UsuariosPage() {
  const { user } = useAuth();
  const canAdmin = esAdmin(user?.rol);
  const [items, setItems] = useState<UsuarioAdmin[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [filtroRol, setFiltroRol] = useState("");
  const [editing, setEditing] = useState<UsuarioAdmin | null>(null);
  const [creating, setCreating] = useState(false);

  const [email, setEmail] = useState("");
  const [nombre, setNombre] = useState("");
  const [rol, setRol] = useState("Prevencionista");
  const [lat, setLat] = useState(String(CABA_DEFAULT.lat));
  const [lon, setLon] = useState(String(CABA_DEFAULT.lon));
  const [disp, setDisp] = useState<DispDraft>(emptyDisp);
  const [mfaRequired, setMfaRequired] = useState(true);
  const [resetMfa, setResetMfa] = useState(false);
  const [saving, setSaving] = useState(false);
  const showForm = creating || editing != null;

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetchUsuariosAdmin({ rol: filtroRol || undefined });
      setItems(res.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cargar");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!canAdmin) return;
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtroRol, canAdmin]);

  if (!canAdmin) return <Navigate to="/perfil" replace />;

  function openCreate() {
    setCreating(true);
    setEditing(null);
    setEmail("");
    setNombre("");
    setRol("Prevencionista");
    setLat(String(CABA_DEFAULT.lat));
    setLon(String(CABA_DEFAULT.lon));
    setDisp(emptyDisp());
    setMfaRequired(true);
    setResetMfa(false);
    setMsg(null);
    setFormError(null);
  }

  function openEdit(u: UsuarioAdmin) {
    setEditing(u);
    setCreating(false);
    setEmail(u.email);
    setNombre(u.nombre);
    setRol(u.rol);
    setLat(u.latitud != null ? String(u.latitud) : String(CABA_DEFAULT.lat));
    setLon(u.longitud != null ? String(u.longitud) : String(CABA_DEFAULT.lon));
    setDisp(fromDisponibilidad(u.disponibilidad));
    setMfaRequired(!!u.mfaRequired);
    setResetMfa(false);
    setMsg(null);
    setFormError(null);
  }

  function closeForm() {
    setCreating(false);
    setEditing(null);
    setFormError(null);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setFormError(null);
    setMsg(null);
    try {
      const latN = Number(lat);
      const lonN = Number(lon);
      const disponibilidad = rol === "Prevencionista" ? toDisponibilidad(disp) : undefined;
      if (creating) {
        await createUsuario({
          email: email.trim(),
          nombre: nombre.trim(),
          rol,
          latitud: rol === "Prevencionista" ? latN : null,
          longitud: rol === "Prevencionista" ? lonN : null,
          mfaRequired,
          disponibilidad,
        });
        setMsg(
          mfaRequired
            ? "Usuario creado. Se envió la invitación; al primer login deberá configurar MFA."
            : "Usuario creado. Se envió la invitación por mail.",
        );
      } else if (editing) {
        await updateUsuario(editing.id, {
          nombre: nombre.trim(),
          rol,
          latitud: rol === "Prevencionista" ? latN : null,
          longitud: rol === "Prevencionista" ? lonN : null,
          mfaRequired,
          resetMfa: mfaRequired && resetMfa ? true : undefined,
          disponibilidad,
        });
        setMsg("Usuario actualizado.");
      }
      closeForm();
      await load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "No se pudo guardar");
    } finally {
      setSaving(false);
    }
  }

  async function toggleActivo(u: UsuarioAdmin) {
    try {
      await updateUsuario(u.id, { activo: !u.activo });
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo cambiar el estado");
    }
  }

  async function reenviar(u: UsuarioAdmin) {
    try {
      await reenviarInvitacion(u.id);
      setMsg(`Invitación reenviada a ${u.email}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "No se pudo reenviar");
    }
  }

  return (
    <div className="usuarios-layout">
      {showForm && (
        <div className="modal-backdrop" role="presentation">
          <div
            className="modal panel usuario-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="usuario-modal-title"
          >
            <div className="usuario-modal-head">
              <h2 id="usuario-modal-title" className="page-title" style={{ fontSize: 18, margin: 0 }}>
                {creating ? "Invitar usuario" : "Editar usuario"}
              </h2>
              {editing && <p className="page-sub" style={{ margin: "6px 0 0" }}>{editing.email}</p>}
            </div>

            <form onSubmit={onSubmit} className="form-stack usuario-modal-form">
              <div className="usuario-modal-scroll">
                {creating && (
                  <div className="field">
                    <label>Email</label>
                    <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
                  </div>
                )}
                <div className="field">
                  <label>Nombre</label>
                  <input value={nombre} onChange={(e) => setNombre(e.target.value)} required minLength={2} />
                </div>
                <div className="field">
                  <label>Rol</label>
                  <Select
                    value={rol}
                    onChange={setRol}
                    ariaLabel="Rol"
                    options={[
                      { value: "Admin", label: "Admin" },
                      { value: "Coordinador", label: "Coordinador" },
                      { value: "Prevencionista", label: "Prevencionista" },
                    ]}
                  />
                </div>
                <div className="field">
                  <label className="disp-check" style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <input
                      type="checkbox"
                      checked={mfaRequired}
                      onChange={(e) => {
                        setMfaRequired(e.target.checked);
                        if (!e.target.checked) setResetMfa(false);
                      }}
                    />
                    Requiere MFA (Authenticator)
                  </label>
                </div>
                {editing?.mfaEnabled && mfaRequired && (
                  <div className="field">
                    <label className="disp-check" style={{ display: "flex", gap: 8, alignItems: "center" }}>
                      <input
                        type="checkbox"
                        checked={resetMfa}
                        onChange={(e) => setResetMfa(e.target.checked)}
                      />
                      Forzar nuevo QR (reiniciar MFA)
                    </label>
                  </div>
                )}
                {rol === "Prevencionista" && (
                  <>
                    <CabaLocationPicker
                      lat={Number(lat) || CABA_DEFAULT.lat}
                      lon={Number(lon) || CABA_DEFAULT.lon}
                      onChange={(la, lo) => {
                        setLat(String(la));
                        setLon(String(lo));
                      }}
                    />
                    <div className="field">
                      <label>Disponibilidad semanal</label>
                      <div className="disp-grid">
                        {DIAS.map((day) => (
                          <div key={day.id} className="disp-row">
                            <label className="disp-check">
                              <input
                                type="checkbox"
                                checked={disp[day.id]?.on ?? false}
                                onChange={(e) =>
                                  setDisp((prev) => ({
                                    ...prev,
                                    [day.id]: { ...prev[day.id], on: e.target.checked },
                                  }))
                                }
                              />
                              {day.label}
                            </label>
                            <TimeField
                              ariaLabel={`${day.label} desde`}
                              value={disp[day.id]?.desde ?? "09:00"}
                              onChange={(v) =>
                                setDisp((prev) => ({
                                  ...prev,
                                  [day.id]: { ...prev[day.id], desde: v },
                                }))
                              }
                            />
                            <TimeField
                              ariaLabel={`${day.label} hasta`}
                              value={disp[day.id]?.hasta ?? "17:00"}
                              onChange={(v) =>
                                setDisp((prev) => ({
                                  ...prev,
                                  [day.id]: { ...prev[day.id], hasta: v },
                                }))
                              }
                            />
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                )}
                {formError && <div className="error">{formError}</div>}
              </div>

              <div className="modal-actions usuario-modal-foot">
                <button type="button" className="ghost-btn" onClick={closeForm} disabled={saving}>
                  Cancelar
                </button>
                <button type="submit" className="btn success" disabled={saving}>
                  {saving ? "Guardando…" : creating ? "Crear e invitar" : "Guardar"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <div className="page-header-row">
        <div>
          <h1 className="page-title">Usuarios</h1>
        </div>
        <button type="button" className="btn success" onClick={openCreate}>
          Nuevo usuario
        </button>
      </div>

      {msg && <div className="success">{msg}</div>}
      {error && <div className="error">{error}</div>}

      <div className="filters panel usuarios-filters">
        <div className="field" style={{ margin: 0, minWidth: 200 }}>
          <label>Rol</label>
          <Select
            value={filtroRol}
            onChange={setFiltroRol}
            ariaLabel="Filtro rol"
            placeholder="Todos los roles"
            options={[
              { value: "", label: "Todos" },
              { value: "Admin", label: "Admin" },
              { value: "Coordinador", label: "Coordinador" },
              { value: "Prevencionista", label: "Prevencionista" },
            ]}
          />
        </div>
        <p className="muted" style={{ margin: 0, fontSize: 13, alignSelf: "end", paddingBottom: 8 }}>
          {loading ? "Cargando…" : `${items.length} usuario${items.length === 1 ? "" : "s"}`}
        </p>
      </div>

      {!loading && items.length === 0 ? (
        <div className="panel">
          <EmptyState title="Sin usuarios" detail="Creá el primero con el botón de arriba." />
        </div>
      ) : null}

      {!loading && items.length > 0 ? (
        <div className="table-wrap panel table-sticky" style={{ padding: 0 }}>
          <table className="data usuarios-table">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Email</th>
                <th>Rol</th>
                <th>Estado</th>
                <th>MFA</th>
                <th>Disponibilidad</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {items.map((u) => {
                const est = estadoBadge(u);
                const mfa = mfaBadge(u);
                const dias =
                  u.disponibilidad && u.disponibilidad.length > 0
                    ? u.disponibilidad
                        .map((d) => DIAS.find((x) => x.id === d.diaSemana)?.label ?? d.diaSemana)
                        .join(" · ")
                    : "—";
                return (
                  <tr
                    key={u.id}
                    className="usuarios-row row-clickable"
                    title="Clic para editar"
                    onClick={(e) => {
                      const target = e.target as HTMLElement;
                      if (target.closest("a, button")) return;
                      openEdit(u);
                    }}
                  >
                    <td className="usuarios-nombre">{u.nombre}</td>
                    <td className="mono">{u.email}</td>
                    <td>
                      <span className={rolBadgeClass(u.rol)}>{u.rol}</span>
                    </td>
                    <td>
                      <span className={est.className}>{est.label}</span>
                    </td>
                    <td>
                      <span className={mfa.className}>{mfa.label}</span>
                    </td>
                    <td className="muted" title={dias}>
                      {u.rol === "Prevencionista" ? dias : "—"}
                    </td>
                    <td>
                      <div className="usuarios-actions">
                        <button type="button" className="ghost-btn" onClick={() => openEdit(u)}>
                          Editar
                        </button>
                        <button type="button" className="ghost-btn" onClick={() => void toggleActivo(u)}>
                          {u.activo ? "Desactivar" : "Activar"}
                        </button>
                        {u.debeCambiarPassword && (
                          <button type="button" className="ghost-btn" onClick={() => void reenviar(u)}>
                            Reenviar
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}
