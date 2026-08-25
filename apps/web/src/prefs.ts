export type HorizontePref = "1m" | "3m";

const KEYS = {
  sidebarCollapsed: "pfi_sidebar_collapsed",
  focusMode: "pfi_focus_mode",
  horizonte: "pfi_horizonte",
  detalleSections: "pfi_detalle_sections_v2",
  detalleTab: "pfi_detalle_tab_v1",
  estadisticasSections: "pfi_estadisticas_sections_v1",
  riesgoScroll: "pfi_riesgo_scroll",
  agendaVista: "pfi_agenda_vista",
} as const;

export type AgendaVista = "mes" | "semana" | "dia";
const AGENDA_VISTAS: AgendaVista[] = ["mes", "semana", "dia"];

export function getAgendaVista(): AgendaVista {
  try {
    const v = localStorage.getItem(KEYS.agendaVista) as AgendaVista | null;
    if (v && AGENDA_VISTAS.includes(v)) return v;
  } catch {
    /* ignore */
  }
  return "semana";
}

export function setAgendaVista(v: AgendaVista): AgendaVista {
  try {
    localStorage.setItem(KEYS.agendaVista, v);
  } catch {
    /* ignore */
  }
  return v;
}

function readBool(key: string, fallback = false): boolean {
  try {
    const v = localStorage.getItem(key);
    if (v === "1" || v === "true") return true;
    if (v === "0" || v === "false") return false;
  } catch {
    /* ignore */
  }
  return fallback;
}

function writeBool(key: string, value: boolean) {
  try {
    localStorage.setItem(key, value ? "1" : "0");
  } catch {
    /* ignore */
  }
}

export function getSidebarCollapsed(): boolean {
  return readBool(KEYS.sidebarCollapsed, false);
}

export function setSidebarCollapsed(value: boolean) {
  writeBool(KEYS.sidebarCollapsed, value);
}

export function getFocusMode(): boolean {
  return readBool(KEYS.focusMode, false);
}

export function setFocusMode(value: boolean) {
  writeBool(KEYS.focusMode, value);
}

export function getHorizontePref(): HorizontePref {
  return "3m";
}

export function setHorizontePref(_value: HorizontePref) {
  try {
    localStorage.setItem(KEYS.horizonte, "3m");
  } catch {
    /* ignore */
  }
}

export type DetalleSectionKey =
  | "ficha"
  | "historial"
  | "visitas"
  | "resumenIa"
  | "shap"
  | "movimientos";

export function getDetalleSections(): Record<DetalleSectionKey, boolean> {
  const defaults: Record<DetalleSectionKey, boolean> = {
    resumenIa: true,
    historial: true,
    visitas: false,
    ficha: false,
    shap: false,
    movimientos: false,
  };
  try {
    const raw = localStorage.getItem(KEYS.detalleSections);
    if (!raw) return defaults;
    const parsed = JSON.parse(raw) as Partial<Record<DetalleSectionKey, boolean>>;
    return { ...defaults, ...parsed };
  } catch {
    return defaults;
  }
}

export function setDetalleSection(key: DetalleSectionKey, open: boolean) {
  const next = { ...getDetalleSections(), [key]: open };
  try {
    localStorage.setItem(KEYS.detalleSections, JSON.stringify(next));
  } catch {
    /* ignore */
  }
  return next;
}

const DETALLE_TABS: DetalleSectionKey[] = [
  "ficha",
  "historial",
  "visitas",
  "resumenIa",
  "shap",
  "movimientos",
];

export function getDetalleTab(): DetalleSectionKey {
  try {
    const raw = localStorage.getItem(KEYS.detalleTab);
    if (raw && (DETALLE_TABS as string[]).includes(raw)) {
      return raw as DetalleSectionKey;
    }
  } catch {
    /* ignore */
  }
  return "historial";
}

export function setDetalleTab(key: DetalleSectionKey) {
  try {
    localStorage.setItem(KEYS.detalleTab, key);
  } catch {
    /* ignore */
  }
  return key;
}

export type EstadisticasSectionKey =
  | "operativa"
  | "shap"
  | "composicion"
  | "sectores";

const ESTADISTICAS_TABS: EstadisticasSectionKey[] = [
  "operativa",
  "shap",
  "composicion",
  "sectores",
];

export function getEstadisticasTab(): EstadisticasSectionKey {
  try {
    const raw = localStorage.getItem(KEYS.estadisticasSections);
    if (raw && (ESTADISTICAS_TABS as string[]).includes(raw)) {
      return raw as EstadisticasSectionKey;
    }
  } catch {
    /* ignore */
  }
  return "operativa";
}

export function setEstadisticasTab(key: EstadisticasSectionKey) {
  try {
    localStorage.setItem(KEYS.estadisticasSections, key);
  } catch {
    /* ignore */
  }
  return key;
}

export function saveRiesgoScroll(y: number) {
  try {
    sessionStorage.setItem(KEYS.riesgoScroll, String(Math.max(0, Math.round(y))));
  } catch {
    /* ignore */
  }
}

export function consumeRiesgoScroll(): number | null {
  try {
    const raw = sessionStorage.getItem(KEYS.riesgoScroll);
    if (raw == null) return null;
    sessionStorage.removeItem(KEYS.riesgoScroll);
    const n = Number(raw);
    return Number.isFinite(n) ? n : null;
  } catch {
    return null;
  }
}

export function prefersReducedMotion(): boolean {
  if (typeof window === "undefined" || !window.matchMedia) return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}
