import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  fetchActaContextoCierre,
  fetchActaItemsRgrl,
  realizarVisita,
  shortId,
  type AgendaItem,
  type ChecklistItemActa,
  type HallazgoActaDraft,
  type RgrlCatalogItem,
} from "../api";
import { IconMic } from "../icons";
import { riesgoLabel } from "../labels";
import { Select } from "./Select";

type Props = {
  item: AgendaItem;
  onClose: () => void;
  onDone: () => void;
};

type ChecklistEstado = ChecklistItemActa["estado"];

type SpeechRecognitionLike = {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  onresult: ((ev: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: (() => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechWindow = Window & {
  SpeechRecognition?: new () => SpeechRecognitionLike;
  webkitSpeechRecognition?: new () => SpeechRecognitionLike;
};

const CHECKLIST_ESTADOS: { value: ChecklistEstado; label: string }[] = [
  { value: "ok", label: "OK" },
  { value: "observacion", label: "Obs." },
  { value: "no_aplica", label: "N/A" },
];

const REAGENDA_OPCIONES = [
  { value: "", label: "No requiere otra visita" },
  { value: "1", label: "Antes de 1 mes" },
  { value: "2", label: "Antes de 2 meses" },
  { value: "3", label: "Antes de 3 meses" },
  { value: "6", label: "Antes de 6 meses" },
];

const CHECKLIST_ACROS = ["RGRL", "EPP", "PRS", "PESE", "SRT", "ART", "RAR", "IGE"];

const CHECKLIST_SECCIONES: { origenes: string[]; titulo: string }[] = [
  { origenes: ["nucleo"], titulo: "Básicos" },
  { origenes: ["historial"], titulo: "Historial del establecimiento" },
  { origenes: ["accidente"], titulo: "Por accidentes" },
  { origenes: ["base"], titulo: "Complementarios" },
];

type ExtraHallazgo = { id: string; itemId: string; tema: string; texto: string };

function newExtraId() {
  return `extra-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

function normalizeFocusKey(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{M}/gu, "")
    .replace(/[¿?¡!]/g, " ")
    .replace(/\b(art|arts|cap|dec|res|ley)\b.*$/i, "")
    .replace(/[^a-z0-9\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function focusOverlaps(a: string, b: string): boolean {
  const na = normalizeFocusKey(a);
  const nb = normalizeFocusKey(b);
  if (!na || !nb) return false;
  if (na === nb) return true;
  if (na.length >= 14 && nb.includes(na)) return true;
  if (nb.length >= 14 && na.includes(nb)) return true;
  return false;
}

function groupChecklist(items: ChecklistItemActa[]) {
  const used = new Set<string>();
  const groups = CHECKLIST_SECCIONES.map((sec) => {
    const list = items.filter((c) => sec.origenes.includes(c.origen ?? ""));
    list.forEach((c) => used.add(c.id));
    return { titulo: sec.titulo, items: list };
  }).filter((g) => g.items.length > 0);
  const resto = items.filter((c) => !used.has(c.id));
  if (resto.length > 0) groups.push({ titulo: "Otros focos", items: resto });
  return groups;
}

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
    .replace(/(\.\.\.|…)+\s*$/g, "")
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

function speechSupported(): boolean {
  const w = window as SpeechWindow;
  return Boolean(w.SpeechRecognition || w.webkitSpeechRecognition);
}

export function RealizarVisitaDialog({ item, onClose, onDone }: Props) {
  const [checklist, setChecklist] = useState<ChecklistItemActa[]>([]);
  /** Texto de hallazgo por ítem Obs. (clave = checklist id). */
  const [obsNotas, setObsNotas] = useState<Record<string, string>>({});
  /** Hallazgos fuera de la lista sugerida (ítem RGRL + texto). */
  const [extras, setExtras] = useState<ExtraHallazgo[]>([]);
  const [rgrlItems, setRgrlItems] = useState<RgrlCatalogItem[]>([]);
  const [abiertosPrevios, setAbiertosPrevios] = useState<number>(0);
  const [loadingCtx, setLoadingCtx] = useState(true);
  const [listeningId, setListeningId] = useState<string | null>(null);
  const [micError, setMicError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [reagendaMeses, setReagendaMeses] = useState("");
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const canMic = speechSupported();

  const rgrlOptionsDisponibles = useMemo(() => {
    const usados = new Set(extras.map((x) => x.itemId).filter(Boolean));
    return rgrlItems
      .filter((it) => !usados.has(it.id))
      .filter((it) => !checklist.some((c) => focusOverlaps(c.label, it.label)))
      .map((it) => ({ value: it.id, label: it.label }));
  }, [rgrlItems, checklist, extras]);

  useEffect(() => {
    let cancelled = false;
    setLoadingCtx(true);
    setRgrlItems([]);
    setObsNotas({});
    setExtras([]);

    fetchActaContextoCierre(item.idEstablecimiento)
      .then((ctx) => {
        if (cancelled) return;
        setChecklist(
          (ctx.checklistSugerido ?? []).map((c) => ({
            id: c.id,
            label: formatChecklistLabel(c.label),
            estado: "no_aplica" as const,
            origen: c.origen,
          })),
        );
        setAbiertosPrevios(ctx.hallazgosAbiertos?.length ?? 0);
      })
      .catch(() => {
        if (!cancelled) {
          setChecklist([
            { id: "core-0", label: "Orden y limpieza de áreas de trabajo", estado: "no_aplica", origen: "nucleo" },
            { id: "core-1", label: "Uso y estado de EPP", estado: "no_aplica", origen: "nucleo" },
            { id: "core-2", label: "Documentación de higiene y seguridad vigente", estado: "no_aplica", origen: "nucleo" },
            { id: "base-0", label: "Señalización de riesgos y vías de evacuación", estado: "no_aplica", origen: "base" },
            { id: "base-1", label: "Protecciones de máquinas y resguardos", estado: "no_aplica", origen: "base" },
          ]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingCtx(false);
      });

    fetchActaItemsRgrl()
      .then((cat) => {
        if (!cancelled) setRgrlItems(cat.items ?? []);
      })
      .catch(() => {
        if (!cancelled) setRgrlItems([]);
      });

    return () => {
      cancelled = true;
      recognitionRef.current?.stop();
    };
  }, [item.idEstablecimiento]);

  function setChecklistEstado(id: string, estado: ChecklistEstado) {
    setChecklist((prev) => prev.map((c) => (c.id === id ? { ...c, estado } : c)));
    if (estado !== "observacion") {
      setObsNotas((prev) => {
        if (!(id in prev)) return prev;
        const copy = { ...prev };
        delete copy[id];
        return copy;
      });
      if (listeningId === id) stopListening();
    } else {
      setObsNotas((prev) => (id in prev ? prev : { ...prev, [id]: "" }));
    }
  }

  function stopListening() {
    try {
      recognitionRef.current?.stop();
    } catch {
      /* ignore */
    }
    recognitionRef.current = null;
    setListeningId(null);
  }

  function appendTranscript(targetId: string, chunk: string) {
    if (targetId.startsWith("extra-")) {
      setExtras((prev) =>
        prev.map((x) => {
          if (x.id !== targetId) return x;
          const cur = x.texto.trim();
          return { ...x, texto: cur ? `${cur} ${chunk}` : chunk };
        }),
      );
      return;
    }
    setObsNotas((prev) => {
      const cur = (prev[targetId] ?? "").trim();
      return { ...prev, [targetId]: cur ? `${cur} ${chunk}` : chunk };
    });
  }

  function toggleMic(itemId: string) {
    setMicError(null);
    setError(null);
    if (!canMic) {
      setMicError("Tu navegador no soporta dictado por micrófono. Escribí el texto a mano.");
      return;
    }
    if (listeningId === itemId) {
      stopListening();
      return;
    }
    stopListening();

    const w = window as SpeechWindow;
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
    if (!Ctor) return;

    const rec = new Ctor();
    rec.lang = "es-AR";
    rec.continuous = false;
    rec.interimResults = false;
    rec.onresult = (ev) => {
      const chunk = Array.from(ev.results)
        .map((r) => r[0]?.transcript ?? "")
        .join(" ")
        .trim();
      if (!chunk) return;
      appendTranscript(itemId, chunk);
    };
    rec.onerror = () => {
      setMicError("No se pudo usar el micrófono. Revisá el permiso del navegador.");
      setListeningId(null);
      recognitionRef.current = null;
    };
    rec.onend = () => {
      setListeningId(null);
      recognitionRef.current = null;
    };
    recognitionRef.current = rec;
    setListeningId(itemId);
    try {
      rec.start();
    } catch {
      setMicError("No se pudo iniciar el micrófono.");
      setListeningId(null);
      recognitionRef.current = null;
    }
  }

  function addExtraHallazgo() {
    setExtras((prev) => [...prev, { id: newExtraId(), itemId: "", tema: "", texto: "" }]);
    setError(null);
  }

  function setExtraItemRgrl(extraId: string, itemId: string) {
    const picked = rgrlItems.find((it) => it.id === itemId);
    setExtras((prev) =>
      prev.map((row) =>
        row.id === extraId
          ? { ...row, itemId, tema: picked?.label ?? "" }
          : row,
      ),
    );
    setError(null);
  }

  function removeExtraHallazgo(id: string) {
    if (listeningId === id) stopListening();
    setExtras((prev) => prev.filter((x) => x.id !== id));
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    stopListening();

    const obsItems = checklist.filter((c) => c.estado === "observacion");
    for (const c of obsItems) {
      if (!(obsNotas[c.id] ?? "").trim()) {
        setError(`Completá la observación de «${c.label}».`);
        return;
      }
    }
    for (const x of extras) {
      if (!x.itemId || !x.tema.trim()) {
        setError("Elegí el ítem RGRL del hallazgo agregado.");
        return;
      }
      if (!x.texto.trim()) {
        setError("Completá el texto del hallazgo agregado, o quitalo.");
        return;
      }
    }

    const hallazgosActa: HallazgoActaDraft[] = [
      ...obsItems.map((c) => ({
        severidad: "media" as const,
        hallazgo: (obsNotas[c.id] ?? "").trim(),
        itemRgrl: c.label,
        checklistItemId: c.id,
        checklistLabel: c.label,
        estado: "abierto" as const,
        origen: "manual" as const,
      })),
      ...extras.map((x) => ({
        severidad: "media" as const,
        hallazgo: x.texto.trim(),
        itemRgrl: x.tema.trim(),
        checklistLabel: x.tema.trim(),
        estado: "abierto" as const,
        origen: "manual" as const,
      })),
    ];

    // Resultado implícito: con Obs. → observación; si no → ok (sin UI).
    const resultadoGlobal = hallazgosActa.length > 0 ? "observacion" : "ok";

    setSaving(true);
    setError(null);
    try {
      const meses = Number(reagendaMeses);
      await realizarVisita(item.id, {
        resultadoGlobal,
        revisita: false,
        reagendaMesesPlazo: meses === 1 || meses === 2 || meses === 3 || meses === 6 ? meses : null,
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
    <div className="modal-backdrop" role="presentation">
      <div
        className="modal panel acta-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="realizar-title"
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
              <legend>Focos sugeridos</legend>
              {loadingCtx ? (
                <p className="muted">Cargando ítems…</p>
              ) : (
                <div className="acta-checklist">
                  {groupChecklist(checklist).map((grupo) => (
                    <section key={grupo.titulo} className="acta-check-section">
                      <h3 className="acta-check-section-title">{grupo.titulo}</h3>
                      <ul className="acta-checklist-group">
                        {grupo.items.map((c) => {
                          const isObs = c.estado === "observacion";
                          return (
                            <li key={c.id} className={`acta-check-item${isObs ? " has-obs" : ""}`}>
                              <div className="acta-check-row">
                                <div className="acta-check-text">
                                  <span className="acta-check-detail">{c.label}</span>
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
                              </div>
                              {isObs && (
                                <div className="acta-obs-note">
                                  <label className="acta-obs-note-label" htmlFor={`obs-${c.id}`}>
                                    Observación / hallazgo
                                  </label>
                                  <div className="acta-obs-note-row">
                                    <textarea
                                      id={`obs-${c.id}`}
                                      rows={2}
                                      value={obsNotas[c.id] ?? ""}
                                      onChange={(e) =>
                                        setObsNotas((prev) => ({ ...prev, [c.id]: e.target.value }))
                                      }
                                      placeholder="Qué observaste y qué conviene pedir al establecimiento…"
                                    />
                                    <button
                                      type="button"
                                      className={`acta-mic-btn${listeningId === c.id ? " listening" : ""}`}
                                      onClick={() => toggleMic(c.id)}
                                      disabled={saving}
                                      title={
                                        canMic
                                          ? listeningId === c.id
                                            ? "Detener dictado"
                                            : "Dictar por micrófono (navegador)"
                                          : "Dictado no disponible en este navegador"
                                      }
                                      aria-label={
                                        listeningId === c.id ? "Detener dictado" : "Dictar por micrófono"
                                      }
                                    >
                                      <IconMic size={18} />
                                    </button>
                                  </div>
                                </div>
                              )}
                            </li>
                          );
                        })}
                      </ul>
                    </section>
                  ))}
                </div>
              )}
              {micError && <div className="error" style={{ marginTop: 8 }}>{micError}</div>}
            </fieldset>

            <fieldset className="acta-fieldset">
              <legend>Otros hallazgos</legend>
              {extras.length > 0 && (
                <ul className="acta-checklist-group acta-extras">
                  {extras.map((x) => {
                    const optionsForRow = [
                      ...(x.itemId && x.tema
                        ? [{ value: x.itemId, label: x.tema }]
                        : []),
                      ...rgrlOptionsDisponibles,
                    ];
                    return (
                      <li key={x.id} className="acta-check-item has-obs">
                        <div className="acta-extra-head">
                          <span className="acta-obs-note-label">Ítem RGRL</span>
                          <button
                            type="button"
                            className="ghost-btn acta-extra-remove"
                            onClick={() => removeExtraHallazgo(x.id)}
                            disabled={saving}
                          >
                            Quitar
                          </button>
                        </div>
                        <Select
                          className="acta-extra-tema"
                          value={x.itemId}
                          onChange={(v) => setExtraItemRgrl(x.id, v)}
                          options={optionsForRow}
                          placeholder={
                            rgrlItems.length === 0
                              ? "Catálogo RGRL no disponible"
                              : "Buscar ítem del RGRL…"
                          }
                          ariaLabel="Ítem RGRL del hallazgo"
                          disabled={saving || rgrlItems.length === 0}
                          searchable
                        />
                        <div className="acta-obs-note">
                          <label className="acta-obs-note-label" htmlFor={`obs-${x.id}`}>
                            Observación / hallazgo
                          </label>
                          <div className="acta-obs-note-row">
                            <textarea
                              id={`obs-${x.id}`}
                              rows={2}
                              value={x.texto}
                              onChange={(e) =>
                                setExtras((prev) =>
                                  prev.map((row) =>
                                    row.id === x.id ? { ...row, texto: e.target.value } : row,
                                  ),
                                )
                              }
                              placeholder="Qué observaste y qué conviene pedir al establecimiento…"
                              disabled={saving}
                            />
                            <button
                              type="button"
                              className={`acta-mic-btn${listeningId === x.id ? " listening" : ""}`}
                              onClick={() => toggleMic(x.id)}
                              disabled={saving}
                              title={
                                canMic
                                  ? listeningId === x.id
                                    ? "Detener dictado"
                                    : "Dictar por micrófono (navegador)"
                                  : "Dictado no disponible en este navegador"
                              }
                              aria-label={
                                listeningId === x.id ? "Detener dictado" : "Dictar por micrófono"
                              }
                            >
                              <IconMic size={18} />
                            </button>
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              )}
              <button
                type="button"
                className="ghost-btn acta-add-extra"
                onClick={addExtraHallazgo}
                disabled={saving || loadingCtx || rgrlItems.length === 0}
              >
                Agregar hallazgo
              </button>
            </fieldset>

            <fieldset className="acta-fieldset acta-reagenda">
              <legend>Próxima visita</legend>
              <p className="muted" style={{ margin: "0 0 10px", fontSize: 13 }}>
                Si hay incumplimientos o seguimiento, indicá en cuántos meses como máximo debe
                agendarse otra visita. El coordinador lo verá en Priorización.
              </p>
              <div className="field" style={{ margin: 0 }}>
                <label htmlFor="reagenda-meses">Reagendar antes de</label>
                <Select
                  value={reagendaMeses}
                  onChange={setReagendaMeses}
                  ariaLabel="Plazo máximo para próxima visita"
                  options={REAGENDA_OPCIONES}
                />
              </div>
            </fieldset>

            {error && <div className="error">{error}</div>}
          </div>

          <div className="modal-actions acta-modal-foot">
            <button type="button" className="ghost-btn" onClick={onClose} disabled={saving}>
              Volver
            </button>
            <button type="submit" className="btn success" disabled={saving || loadingCtx}>
              {saving ? "Guardando…" : "Confirmar realizada"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
