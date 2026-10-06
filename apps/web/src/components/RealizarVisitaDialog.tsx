import { useEffect, useState, type FormEvent } from "react";
import {
  fetchActaContextoCierre,
  realizarVisita,
  shortId,
  sugerirActaHallazgos,
  type AgendaItem,
  type ChecklistItemActa,
  type HallazgoActaDraft,
} from "../api";
import { riesgoLabel } from "../labels";
import { DateField } from "./DateField";
import { TimeField } from "./TimeField";

type Props = {
  item: AgendaItem;
  onClose: () => void;
  onDone: () => void;
};

type ChecklistEstado = ChecklistItemActa["estado"];

const CHECKLIST_ESTADOS: { value: ChecklistEstado; label: string }[] = [
  { value: "ok", label: "OK" },
  { value: "observacion", label: "Obs." },
  { value: "no_aplica", label: "N/A" },
];

const RESULTADOS: { value: "ok" | "observacion" | "critico"; label: string }[] = [
  { value: "ok", label: "OK" },
  { value: "observacion", label: "Con observaciones" },
  { value: "critico", label: "Crítico" },
];

function emptyHallazgo(): HallazgoActaDraft {
  return {
    severidad: "media",
    hallazgo: "",
    recomendacion: "",
    plazoDias: 30,
    normaRef: "",
    estado: "abierto",
    origen: "manual",
  };
}

const CHECKLIST_ACROS = ["RGRL", "EPP", "PRS", "PESE", "SRT", "ART", "RAR", "IGE"];

function formatChecklistLabel(raw: string): string {
  let t = raw
    .trim()
    .replace(/[\n\r]+/g, " ")
    .replace(/(\d)[\u2014\u2013—–-](\d)/g, "$1-$2")
    .replace(/[\u2014\u2013]/g, ":")
    .replace(/\s+[-–—]\s+/g, ": ")
    .replace(/\s{2,}/g, " ")
    .replace(/:{2,}/g, ":")
    .replace(/^:\s*/, "")
    .trim();

  const parts = t
    .split(":")
    .map((p) => p.trim())
    .filter(Boolean)
    .map(formatChecklistSegment);
  return parts.join(": ");
}

function formatChecklistSegment(segment: string): string {
  const s = segment.trim();
  if (!s) return s;
  // Prefijos RGRL cortos: dejar limpios para usarlos como título.
  const rgrl = s.match(/^(rgrl)(\s+industria|\s+obra|\s+comercio|\s+agro)?$/i);
  if (rgrl) {
    return ["RGRL", rgrl[2]?.trim().toLowerCase()].filter(Boolean).join(" ");
  }

  const letters = s.replace(/[^A-Za-zÁÉÍÓÚÜÑáéíóúüñ]/g, "");
  if (letters.length < 3) return s;
  const upper = (letters.match(/[A-ZÁÉÍÓÚÜÑ]/g) ?? []).length;
  const needsFix = upper / letters.length >= 0.45 || /[A-ZÁÉÍÓÚÑ]{5,}/.test(s);
  if (!needsFix) return s;

  let out = s.toLowerCase();
  out = out.replace(/(^\s*\p{L})|([.!?]\s+\p{L})/gu, (m) => m.toUpperCase());
  for (const a of CHECKLIST_ACROS) {
    out = out.replace(new RegExp(`\\b${a}\\b`, "gi"), a);
  }
  out = out.replace(/^\p{L}/u, (c) => c.toUpperCase());
  return out;
}

function splitChecklistLabel(label: string): { title: string | null; detail: string } {
  const formatted = formatChecklistLabel(label);

  // "RGRL industria: …" / "RGRL: …"
  const rgrl = formatted.match(/^(RGRL(?:\s+(?:industria|obra|comercio|agro))?):\s*(.+)$/i);
  if (rgrl) {
    return { title: rgrl[1].toUpperCase(), detail: rgrl[2] };
  }

  const sep = formatted.indexOf(": ");
  if (sep > 0 && sep < 90) {
    return {
      title: formatted.slice(0, sep).toUpperCase(),
      detail: formatted.slice(sep + 2),
    };
  }
  return { title: null, detail: formatted };
}

function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function addDaysIso(days: number): string {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function RealizarVisitaDialog({ item, onClose, onDone }: Props) {
  const [resultadoGlobal, setResultadoGlobal] = useState<"ok" | "observacion" | "critico">(
    "observacion",
  );
  const [revisita, setRevisita] = useState(false);
  const [fechaRevisita, setFechaRevisita] = useState(addDaysIso(30));
  const [horaRevisita, setHoraRevisita] = useState("09:00");
  const [notasActa, setNotasActa] = useState("");
  const [checklist, setChecklist] = useState<ChecklistItemActa[]>([]);
  const [hallazgos, setHallazgos] = useState<HallazgoActaDraft[]>([emptyHallazgo()]);
  const [abiertosPrevios, setAbiertosPrevios] = useState<number>(0);
  const [loadingCtx, setLoadingCtx] = useState(true);
  const [sugeriendo, setSugeriendo] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoadingCtx(true);
    fetchActaContextoCierre(item.idEstablecimiento)
      .then((ctx) => {
        if (cancelled) return;
        setChecklist(
          (ctx.checklistSugerido ?? []).map((c) => ({
            id: c.id,
            label: formatChecklistLabel(c.label),
            estado: "ok",
          })),
        );
        setAbiertosPrevios(ctx.hallazgosAbiertos?.length ?? 0);
      })
      .catch(() => {
        if (!cancelled) {
          setChecklist([
            { id: "base-0", label: "Orden y limpieza", estado: "ok" },
            { id: "base-1", label: "EPP", estado: "ok" },
            { id: "base-2", label: "Señalización", estado: "ok" },
          ]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingCtx(false);
      });
    return () => {
      cancelled = true;
    };
  }, [item.idEstablecimiento]);

  function setChecklistEstado(id: string, estado: ChecklistEstado) {
    setChecklist((prev) => prev.map((c) => (c.id === id ? { ...c, estado } : c)));
  }

  function updateHallazgo(index: number, patch: Partial<HallazgoActaDraft>) {
    setHallazgos((prev) => prev.map((h, i) => (i === index ? { ...h, ...patch } : h)));
  }

  function removeHallazgo(index: number) {
    setHallazgos((prev) => (prev.length <= 1 ? [emptyHallazgo()] : prev.filter((_, i) => i !== index)));
  }

  async function onSugerir() {
    setSugeriendo(true);
    setError(null);
    try {
      const res = await sugerirActaHallazgos(item.idEstablecimiento, {
        checklist,
        notas: notasActa.trim() || undefined,
      });
      const drafts = (res.hallazgos ?? []).filter((h) => h.hallazgo?.trim());
      if (drafts.length === 0) {
        setError("La IA no devolvió borradores útiles. Probá marcar observaciones en el checklist.");
        return;
      }
      setHallazgos((prev) => {
        const keep = prev.filter((h) => h.hallazgo.trim());
        return [
          ...keep,
          ...drafts.map((d) => ({
            severidad: (d.severidad as HallazgoActaDraft["severidad"]) || "media",
            hallazgo: d.hallazgo,
            recomendacion: d.recomendacion ?? "",
            plazoDias: d.plazoDias ?? 30,
            normaRef: d.normaRef ?? "",
            itemRgrl: d.itemRgrl ?? "",
            estado: "abierto" as const,
            origen: "sugerido_aceptado" as const,
          })),
        ];
      });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "No se pudieron sugerir hallazgos");
    } finally {
      setSugeriendo(false);
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    const hallazgosActa = hallazgos
      .map((h) => ({
        ...h,
        hallazgo: h.hallazgo.trim(),
        recomendacion: h.recomendacion?.trim() || undefined,
        normaRef: h.normaRef?.trim() || undefined,
        itemRgrl: h.itemRgrl?.trim() || undefined,
      }))
      .filter((h) => h.hallazgo.length > 0);

    if (hallazgosActa.length === 0 && resultadoGlobal !== "ok") {
      setError("Agregá al menos un hallazgo o marcá el resultado como OK.");
      return;
    }
    if (revisita && !fechaRevisita) {
      setError("Indicá la fecha de la revisita.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      await realizarVisita(item.id, {
        resultadoGlobal,
        revisita,
        fechaRevisita: revisita ? fechaRevisita : undefined,
        horaRevisita: revisita ? horaRevisita : undefined,
        notasActa: notasActa.trim() || undefined,
        checklist,
        hallazgosActa,
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
        className="modal panel acta-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="realizar-title"
        onClick={(ev) => ev.stopPropagation()}
      >
        <div className="acta-modal-head">
          <h2 id="realizar-title" className="page-title" style={{ fontSize: 18, marginBottom: 6 }}>
            Acta de visita
          </h2>
          <p className="page-sub" style={{ marginBottom: 0 }}>
            {shortId(item.idEstablecimiento)}
            {item.rankingOrigen != null ? ` · #${item.rankingOrigen}` : ""}
            {item.bandaOrigen ? ` · ${riesgoLabel(item.bandaOrigen)}` : ""}
            {" · "}
            planificada {item.fechaPlanificada.slice(0, 10)}
            {abiertosPrevios > 0 ? ` · ${abiertosPrevios} pendientes previos` : ""}
          </p>
        </div>

        <form onSubmit={submit} className="form-stack acta-form">
          <div className="acta-modal-scroll">
          <fieldset className="acta-fieldset">
            <legend>Resultado global</legend>
            <div className="acta-resultado-row">
              {RESULTADOS.map((r) => (
                <label key={r.value} className={`acta-choice${resultadoGlobal === r.value ? " active" : ""}`}>
                  <input
                    type="radio"
                    name="resultado"
                    value={r.value}
                    checked={resultadoGlobal === r.value}
                    onChange={() => setResultadoGlobal(r.value)}
                  />
                  {r.label}
                </label>
              ))}
            </div>
            <label className="acta-check-inline">
              <input
                type="checkbox"
                checked={revisita}
                onChange={(e) => setRevisita(e.target.checked)}
              />
              Requiere revisita
            </label>
            {revisita && (
              <div className="fecha-hora-row" style={{ marginTop: 10 }}>
                <div className="field">
                  <label htmlFor="fecha-rev">Fecha de revisita</label>
                  <DateField
                    ariaLabel="Fecha de revisita"
                    min={todayIso()}
                    value={fechaRevisita}
                    onChange={setFechaRevisita}
                  />
                </div>
                <div className="field">
                  <label htmlFor="hora-rev">Hora</label>
                  <TimeField
                    ariaLabel="Hora de revisita"
                    value={horaRevisita}
                    onChange={setHoraRevisita}
                  />
                </div>
              </div>
            )}
          </fieldset>

          <fieldset className="acta-fieldset">
            <legend>Checklist sugerido</legend>
            {loadingCtx ? (
              <p className="muted">Cargando ítems…</p>
            ) : (
              <ul className="acta-checklist">
                {checklist.map((c) => {
                  const { title, detail } = splitChecklistLabel(c.label);
                  return (
                    <li key={c.id} className="acta-check-item">
                      <div className="acta-check-text">
                        {title ? <strong className="acta-check-title">{title}</strong> : null}
                        <span className="acta-check-detail">{detail}</span>
                      </div>
                      <div className="acta-check-states" role="group" aria-label={c.label}>
                        {CHECKLIST_ESTADOS.map((st) => (
                          <button
                            key={st.value}
                            type="button"
                            className={`acta-state-btn${c.estado === st.value ? " active" : ""}`}
                            onClick={() => setChecklistEstado(c.id, st.value)}
                          >
                            {st.label}
                          </button>
                        ))}
                      </div>
                    </li>
                  );
                })}
              </ul>
            )}
          </fieldset>

          <fieldset className="acta-fieldset">
            <legend>Hallazgos</legend>
            <div className="acta-hallazgos">
              {hallazgos.map((h, idx) => (
                <div key={idx} className="acta-hallazgo">
                  <div className="acta-hallazgo-head">
                    <select
                      value={h.severidad}
                      aria-label="Severidad"
                      onChange={(e) =>
                        updateHallazgo(idx, {
                          severidad: e.target.value as HallazgoActaDraft["severidad"],
                        })
                      }
                    >
                      <option value="baja">Baja</option>
                      <option value="media">Media</option>
                      <option value="alta">Alta</option>
                    </select>
                    <select
                      value={h.estado}
                      aria-label="Estado"
                      onChange={(e) =>
                        updateHallazgo(idx, {
                          estado: e.target.value as HallazgoActaDraft["estado"],
                        })
                      }
                    >
                      <option value="abierto">Abierto</option>
                      <option value="cerrado">Cerrado</option>
                    </select>
                    {h.origen === "sugerido_aceptado" && (
                      <span className="badge-sev media">IA</span>
                    )}
                    <button
                      type="button"
                      className="ghost-btn danger"
                      onClick={() => removeHallazgo(idx)}
                      aria-label="Quitar hallazgo"
                    >
                      Quitar
                    </button>
                  </div>
                  <textarea
                    rows={2}
                    placeholder="Descripción del hallazgo…"
                    value={h.hallazgo}
                    onChange={(e) => updateHallazgo(idx, { hallazgo: e.target.value })}
                  />
                  <textarea
                    rows={2}
                    placeholder="Recomendación / acción…"
                    value={h.recomendacion ?? ""}
                    onChange={(e) => updateHallazgo(idx, { recomendacion: e.target.value })}
                  />
                  <div className="acta-hallazgo-meta">
                    <label>
                      Plazo (días)
                      <input
                        type="number"
                        min={1}
                        max={365}
                        value={h.plazoDias ?? ""}
                        onChange={(e) =>
                          updateHallazgo(idx, {
                            plazoDias: e.target.value ? Number(e.target.value) : undefined,
                          })
                        }
                      />
                    </label>
                    <label className="grow">
                      Norma / ref.
                      <input
                        type="text"
                        value={h.normaRef ?? ""}
                        onChange={(e) => updateHallazgo(idx, { normaRef: e.target.value })}
                        placeholder="Res. SRT …"
                      />
                    </label>
                  </div>
                </div>
              ))}
            </div>
            <div className="row-actions" style={{ marginTop: 8 }}>
              <button type="button" className="ghost-btn" onClick={() => setHallazgos((p) => [...p, emptyHallazgo()])}>
                Agregar hallazgo
              </button>
              <button type="button" className="ghost-btn" disabled={sugeriendo || saving} onClick={() => void onSugerir()}>
                {sugeriendo ? "Sugiriendo…" : "Sugerir con IA"}
              </button>
            </div>
          </fieldset>

          <div className="field">
            <label htmlFor="notas-acta">Notas (opcional)</label>
            <textarea
              id="notas-acta"
              rows={2}
              value={notasActa}
              onChange={(e) => setNotasActa(e.target.value)}
              placeholder="Comentarios libres del cierre…"
            />
          </div>

          {error && <div className="error">{error}</div>}
          </div>

          <div className="modal-actions acta-modal-foot">
            <button type="button" className="ghost-btn" onClick={onClose} disabled={saving}>
              Volver
            </button>
            <button type="submit" className="btn" disabled={saving || loadingCtx}>
              {saving ? "Guardando…" : "Confirmar realizada"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
