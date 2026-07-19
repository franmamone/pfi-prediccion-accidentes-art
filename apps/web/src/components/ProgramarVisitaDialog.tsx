import { useEffect, useState, type FormEvent } from "react";
import {
  fetchUsuariosAsignables,
  programarVisita,
  shortId,
  type Horizonte,
  type RankingItem,
  type UsuarioAsignable,
} from "../api";
import { useAuth } from "../auth";
import { motivoLabel, riesgoLabel } from "../labels";

type Props = {
  item: RankingItem;
  horizonte: Horizonte;
  onClose: () => void;
  onDone: () => void;
};

function todayIso(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function ProgramarVisitaDialog({ item, horizonte, onClose, onDone }: Props) {
  const { user } = useAuth();
  const [usuarios, setUsuarios] = useState<UsuarioAsignable[]>([]);
  const [fecha, setFecha] = useState(todayIso());
  const [usuarioId, setUsuarioId] = useState<number>(user?.id ?? 0);
  const [notas, setNotas] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchUsuariosAsignables()
      .then((rows) => {
        setUsuarios(rows);
        if (rows.length && !rows.some((u) => u.id === usuarioId)) {
          setUsuarioId(rows[0].id);
        }
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "No se pudieron cargar responsables");
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await programarVisita({
        rankingItemId: item.id,
        fechaPlanificada: fecha,
        horizonte,
        usuarioId: usuarioId || undefined,
        notas: notas.trim() || undefined,
      });
      onDone();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "No se pudo programar la visita");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="programar-title"
        onClick={(ev) => ev.stopPropagation()}
      >
        <h2 id="programar-title" className="page-title" style={{ fontSize: 18, marginBottom: 6 }}>
          Programar visita
        </h2>
        <p className="page-sub" style={{ marginBottom: 14 }}>
          {shortId(item.idEstablecimiento)} · #{item.ranking} · {riesgoLabel(item.banda)} ·{" "}
          {motivoLabel(item.motivo)}
        </p>

        <form onSubmit={submit} className="form-stack">
          <div className="field">
            <label htmlFor="fecha-planificada">Fecha planificada</label>
            <input
              id="fecha-planificada"
              type="date"
              required
              min={todayIso()}
              value={fecha}
              onChange={(e) => setFecha(e.target.value)}
            />
          </div>
          <div className="field">
            <label htmlFor="responsable">Responsable</label>
            <select
              id="responsable"
              value={usuarioId}
              onChange={(e) => setUsuarioId(Number(e.target.value))}
              required
            >
              {usuarios.map((u) => (
                <option key={u.id} value={u.id}>
                  {u.nombre} ({u.rol})
                </option>
              ))}
            </select>
          </div>
          <div className="field">
            <label htmlFor="notas">Notas (opcional)</label>
            <textarea
              id="notas"
              rows={3}
              value={notas}
              onChange={(e) => setNotas(e.target.value)}
              placeholder="Observaciones para el prevencionista…"
            />
          </div>

          {error && <div className="error">{error}</div>}

          <div className="modal-actions">
            <button type="button" className="ghost-btn" onClick={onClose} disabled={saving}>
              Cancelar
            </button>
            <button type="submit" className="btn" disabled={saving || !usuarioId}>
              {saving ? "Guardando…" : "Programar visita"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
