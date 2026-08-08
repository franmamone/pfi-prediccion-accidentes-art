export type HorizontePref = "1m" | "3m";

const KEYS = {
  sidebarCollapsed: "pfi_sidebar_collapsed",
  focusMode: "pfi_focus_mode",
  horizonte: "pfi_horizonte",
  detalleSections: "pfi_detalle_sections",
  riesgoScroll: "pfi_riesgo_scroll",
} as const;

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
  try {
    const v = localStorage.getItem(KEYS.horizonte);
    if (v === "1m" || v === "3m") return v;
  } catch {
    /* ignore */
  }
  return "1m";
}

export function setHorizontePref(value: HorizontePref) {
  try {
    localStorage.setItem(KEYS.horizonte, value);
  } catch {
    /* ignore */
  }
}

export type DetalleSectionKey =
  | "acierto"
  | "ficha"
  | "explicacion"
  | "historial"
  | "visitas"
  | "resumenIa"
  | "shap";

export function getDetalleSections(): Record<DetalleSectionKey, boolean> {
  const defaults: Record<DetalleSectionKey, boolean> = {
    acierto: true,
    ficha: true,
    explicacion: true,
    historial: true,
    visitas: true,
    resumenIa: true,
    shap: true,
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
