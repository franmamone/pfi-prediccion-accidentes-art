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
import { DateField } from "./DateField";
import { Select } from "./Select";
import { TimeField } from "./TimeField";

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
  const [hora, setHora] = useState("09:00");
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
    if (!fecha) {
      setError("Elegí una fecha planificada.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await programarVisita({
        rankingItemId: item.id,
        fechaPlanificada: fecha,
        horaPlanificada: hora,
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
        className="modal panel programar-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="programar-title"
        onClick={(ev) => ev.stopPropagation()}
      >
        <div className="programar-modal-head">
          <h2 id="programar-title" className="page-title programar-modal-title">
            Programar visita
          </h2>
          <p className="page-sub programar-modal-sub">
            {shortId(item.idEstablecimiento)} · #{item.ranking} · {riesgoLabel(item.banda)} ·{" "}
            {motivoLabel(item.motivo)}
          </p>
        </div>

        <form onSubmit={submit} className="form-stack programar-form">
          <div className="programar-modal-scroll">
            <div className="fecha-hora-row">
              <div className="field">
                <label htmlFor="fecha-planificada">Fecha</label>
                <DateField
                  ariaLabel="Fecha planificada"
                  min={todayIso()}
                  value={fecha}
                  onChange={setFecha}
                />
              </div>
              <div className="field">
                <label htmlFor="hora-planificada">Hora</label>
                <TimeField
                  ariaLabel="Hora planificada"
                  value={hora}
                  onChange={setHora}
                />
              </div>
            </div>
            <div className="field">
              <label htmlFor="responsable">Responsable</label>
              <Select
                value={String(usuarioId)}
                onChange={(v) => setUsuarioId(Number(v))}
                ariaLabel="Responsable"
                placeholder="Elegí un responsable…"
                options={usuarios.map((u) => ({ value: String(u.id), label: `${u.nombre} (${u.rol})` }))}
              />
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
          </div>

          <div className="modal-actions programar-modal-foot">
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
