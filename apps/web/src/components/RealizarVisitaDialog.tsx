import { useState, type FormEvent } from "react";
import { realizarVisita, shortId, type AgendaItem } from "../api";
import { riesgoLabel } from "../labels";

type Props = {
  item: AgendaItem;
  onClose: () => void;
  onDone: () => void;
};

export function RealizarVisitaDialog({ item, onClose, onDone }: Props) {
  const [hallazgos, setHallazgos] = useState("");
  const [acciones, setAcciones] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await realizarVisita(item.id, {
        hallazgos: hallazgos.trim() || undefined,
        acciones: acciones.trim() || undefined,
      });
      onDone();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "No se pudo marcar como realizada");
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
        aria-labelledby="realizar-title"
        onClick={(ev) => ev.stopPropagation()}
      >
        <h2 id="realizar-title" className="page-title" style={{ fontSize: 18, marginBottom: 6 }}>
          Marcar visita como realizada
        </h2>
        <p className="page-sub" style={{ marginBottom: 14 }}>
          {shortId(item.idEstablecimiento)}
          {item.rankingOrigen != null ? ` · #${item.rankingOrigen}` : ""}
          {item.bandaOrigen ? ` · ${riesgoLabel(item.bandaOrigen)}` : ""}
          {" · "}
          planificada {item.fechaPlanificada.slice(0, 10)}
        </p>

        <form onSubmit={submit} className="form-stack">
          <div className="field">
            <label htmlFor="hallazgos">Hallazgos (opcional)</label>
            <textarea
              id="hallazgos"
              rows={3}
              value={hallazgos}
              onChange={(e) => setHallazgos(e.target.value)}
              placeholder="Observaciones de la visita…"
            />
          </div>
          <div className="field">
            <label htmlFor="acciones">Acciones (opcional)</label>
            <textarea
              id="acciones"
              rows={3}
              value={acciones}
              onChange={(e) => setAcciones(e.target.value)}
              placeholder="Acciones acordadas o pendientes…"
            />
          </div>

          {error && <div className="error">{error}</div>}

          <div className="modal-actions">
            <button type="button" className="ghost-btn" onClick={onClose} disabled={saving}>
              Volver
            </button>
            <button type="submit" className="btn" disabled={saving}>
              {saving ? "Guardando…" : "Confirmar realizada"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
