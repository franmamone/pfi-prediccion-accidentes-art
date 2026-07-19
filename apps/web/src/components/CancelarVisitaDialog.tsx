import { useState, type FormEvent } from "react";
import { cancelarVisita, shortId, type AgendaItem } from "../api";
import { riesgoLabel } from "../labels";

type Props = {
  item: AgendaItem;
  onClose: () => void;
  onDone: () => void;
};

export function CancelarVisitaDialog({ item, onClose, onDone }: Props) {
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const text = motivo.trim();
    if (text.length < 3) {
      setError("Indicá un motivo de al menos 3 caracteres.");
      return;
    }
    if (text.length > 400) {
      setError("El motivo no puede superar 400 caracteres.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await cancelarVisita(item.id, text);
      onDone();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "No se pudo cancelar la visita");
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
        aria-labelledby="cancelar-title"
        onClick={(ev) => ev.stopPropagation()}
      >
        <h2 id="cancelar-title" className="page-title" style={{ fontSize: 18, marginBottom: 6 }}>
          Cancelar visita
        </h2>
        <p className="page-sub" style={{ marginBottom: 14 }}>
          {shortId(item.idEstablecimiento)}
          {item.rankingOrigen != null ? ` · #${item.rankingOrigen}` : ""}
          {item.bandaOrigen ? ` · ${riesgoLabel(item.bandaOrigen)}` : ""}
          {" · "}
          planificada {item.fechaPlanificada.slice(0, 10)}
        </p>
        <p className="page-sub" style={{ marginBottom: 12 }}>
          El establecimiento volverá a estar disponible en Priorización. La cancelación queda
          registrada en el historial.
        </p>

        <form onSubmit={submit} className="form-stack">
          <div className="field">
            <label htmlFor="motivo-cancelacion">Motivo de cancelación</label>
            <textarea
              id="motivo-cancelacion"
              rows={4}
              required
              minLength={3}
              maxLength={400}
              autoFocus
              value={motivo}
              onChange={(e) => setMotivo(e.target.value)}
              placeholder="Ej.: cliente ausente, reprogramación externa, error de agenda…"
            />
          </div>

          {error && <div className="error">{error}</div>}

          <div className="modal-actions">
            <button type="button" className="ghost-btn" onClick={onClose} disabled={saving}>
              Volver
            </button>
            <button type="submit" className="btn danger" disabled={saving || motivo.trim().length < 3}>
              {saving ? "Cancelando…" : "Confirmar cancelación"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
