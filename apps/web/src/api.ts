export type Horizonte = "1m" | "3m";
export const HORIZONTE_OPERATIVO = "3m" as const;


export type User = {
  id: number;
  email: string;
  nombre: string;
  rol: string;
  zonaId: number | null;
  mfaRequired?: boolean;
  mfaEnabled?: boolean;
  mfaSetupRequired?: boolean;
  debeCambiarPassword?: boolean;
  latitud?: number | null;
  longitud?: number | null;
};

export type DisponibilidadDia = {
  diaSemana: number;
  horaDesde: string;
  horaHasta: string;
};

export type UsuarioAdmin = User & {
  activo: boolean;
  creadoEn?: string;
  disponibilidad?: DisponibilidadDia[];
};

export type CandidatoAsignacion = {
  id: number;
  email: string;
  nombre: string;
  latitud: number;
  longitud: number;
  visitasDelDia: number;
  horasCargaDia: number;
  distanciaKm: number;
  /** base | visita_anterior | visita_siguiente | visita_ruta */
  anclaOrigen: string;
  disponibleEnHora: boolean;
  horasOcupadas: string[];
  huecosDisponibles: string[];
};

export type CoberturaTopK = {
  k: number;
  cantidad: number;
  denominador: number;
  porcentaje: number;
  criterio: string;
};

export type Resumen = {
  periodo: string;
  horizonte: Horizonte;
  criticos: number;
  altos: number;
  enCooldown: number;
  obligacionPrs: number;
  capacidadCriticos: number;
  capacidadMensual: number;
  universo: number;
  estadosOperativos: {
    pendiente: number;
    programada: number;
    realizada: number;
    cancelada: number;
    suma: number;
    exclusivos: boolean;
    nota: string;
  };
  cobertura: {
    top50: CoberturaTopK;
    top225: CoberturaTopK;
    nota: string;
  };
  nota: string;
};

export type EstadoAgenda = "programada" | "realizada" | "cancelada";

export type UsuarioAsignable = {
  id: number;
  email: string;
  nombre: string;
  rol: string;
  zonaId: number | null;
};

export type AgendaResumen = {
  id: number;
  fechaPlanificada: string;
  horaPlanificada?: string | null;
  estado: EstadoAgenda;
  usuarioId: number;
  responsable: string | null;
  creadoEn?: string;
  actualizadoEn?: string;
};

export type AgendaItem = {
  id: number;
  usuarioId: number;
  responsable: UsuarioAsignable | null;
  idEstablecimiento: string;
  periodo: string;
  horizonte: Horizonte;
  fechaPlanificada: string;
  horaPlanificada?: string | null;
  motivoVisita: string;
  estado: EstadoAgenda;
  snapshotItemId: number | null;
  rankingOrigen: number | null;
  scoreOrigen: number | null;
  bandaOrigen: string | null;
  motivoOrigen: string | null;
  notas: string | null;
  creadoEn: string;
  actualizadoEn: string;
  canceladaEn: string | null;
  motivoCancelacion: string | null;
  visita: {
    id: number;
    fechaHoraReal: string;
    tipo: string;
    resultado: string;
    hallazgos: string | null;
    acciones: string | null;
    acta?: {
      id: number;
      resultadoGlobal: string;
      revisita: boolean;
      plazoRevisitaDias: number | null;
      hallazgosTotal: number;
      hallazgosAbiertos: number;
    } | null;
  } | null;
};

export type EstadoOperativo =
  | "pendiente"
  | "programada"
  | "reprogramada"
  | "realizada"
  | "reagendar";

export type RankingItem = {
  id: number;
  idEstablecimiento: string;
  idEmpleador: string | null;
  ranking: number;
  scoreRiesgo: number;
  efectividadHistorica: number | null;
  efectividadTopK: number | null;
  banda: "critico" | "alto" | "medio" | string;
  motivo: string | null;
  obligacionPrs: boolean;
  enCooldown: boolean;
  ultimaVisitaHaceMeses: number | null;
  sector: string | null;
  ciiuDivision: string | null;
  cantidadCapitas: number | null;
  dotacionNominaMes: number | null;
  alertaUmbral: boolean;
  motivoPrincipalTexto: string | null;
  estadoOperativo?: EstadoOperativo;
  agendaId?: number | null;
  agendaActiva?: AgendaResumen | null;
  visitaAppRecienteEn?: string | null;
  reagendaLimiteEn?: string | null;
  reagendaMesesPlazo?: number | null;
  reagendaVencida?: boolean;
};

export type ExplicacionBullet = {
  titulo: string;
  detalle: string;
  severidad: string;
};

export type AciertoHistorico = {
  disponible: boolean;
  porcentaje: number | null;
  referenciaTopK: number | null;
  etiqueta: string;
  detalle: string;
  holdoutAnio: number;
  horizonte: Horizonte;
};

export type ComoSeCalcula = {
  puntaje: string;
  explicacionPrioridad?: string;
  aciertoHistorico: string;
  shap?: string;
  fuente: string;
};

export type FactorShap = {
  orden: number;
  feature: string;
  tema: string | null;
  etiqueta: string;
  valorObservado: string | null;
  shapValue: number;
  direccion: "aumenta" | "reduce" | string;
  descripcion: string | null;
  intensidadRelativa: number;
};

export type FactoresShap = {
  disponible: boolean;
  aumentaron: FactorShap[];
  redujeron: FactorShap[];
  todas: FactorShap[];
  advertencia: string;
};

export type AgendaEvento = {
  id: number;
  agendaItemId: number;
  snapshotItemId: number | null;
  idEstablecimiento: string;
  tipo: "programada" | "reprogramada" | "realizada" | "cancelada" | string;
  actor: {
    id: number;
    nombre: string | null;
    email: string | null;
    rol: string | null;
  } | null;
  ocurridoEn: string;
  estadoAnterior: string | null;
  estadoNuevo: string | null;
  datos: unknown;
  operacionId: string;
  legadoSinActor: boolean;
};

export type DetalleEstablecimiento = {
  item: RankingItem;
  periodo: string;
  horizonte: Horizonte;
  contexto: {
    totalEnRanking: number;
    percentilScore: number;
    promedioScore: number;
    establecimientosMismaCiiu: number;
    promedioCapitas: number;
    promedioUltimaVisitaMeses: number;
  };
  aciertoHistorico: AciertoHistorico;
  comoSeCalcula: ComoSeCalcula;
  explicacion: ExplicacionBullet[];
  factoresShap?: FactoresShap;
  agendaActiva?: AgendaItem | null;
  visitaAppReciente?: {
    id: number;
    fechaHoraReal: string;
    tipo: string;
    resultado: string;
  } | null;
};

export type TopCategoria = { k: string; n: number };

export type DossierAccidentes = {
  total: number;
  ultimos_12m: number;
  por_anio: Record<string, number>;
  top_forma: TopCategoria[];
  top_zona: TopCategoria[];
  top_naturaleza: TopCategoria[];
  top_gravedad: TopCategoria[];
  recientes: { fecha: string | null; forma: string | null; relato: string | null }[];
};

export type DossierVisitas = {
  total: number;
  ultima_fecha: string | null;
  recientes: {
    fecha: string | null;
    resultado: string | null;
    observaciones: string | null;
    incumplimientos: string | null;
  }[];
};

export type ResumenIa = {
  resumen: string;
  modelo: string;
  generadoEn: string;
  horizonte: Horizonte;
  desdeCache?: boolean;
};

export type DossierEstablecimiento = {
  disponible: boolean;
  nota?: string;
  idEstablecimiento?: string;
  referencia?: string | null;
  fuente?: string | null;
  generadoEn?: string;
  accidentes?: DossierAccidentes | null;
  visitas?: DossierVisitas | null;
  resumenIa?: ResumenIa | null;
};

export function fetchDossier(id: string, horizonte: Horizonte) {
  return request<DossierEstablecimiento>(
    `/api/establecimientos/${encodeURIComponent(id)}/dossier?horizonte=${horizonte}`,
  );
}

export function generarResumenIa(id: string, horizonte: Horizonte, refrescar = false) {
  const qs = new URLSearchParams({ horizonte });
  if (refrescar) qs.set("refrescar", "true");
  return request<ResumenIa>(
    `/api/establecimientos/${encodeURIComponent(id)}/resumen-ia?${qs.toString()}`,
    { method: "POST" },
  );
}

export type CopilotoRespuesta = {
  respuesta: string;
  tema: string;
  seccion: string;
  actividad: string | null;
  modelo: string;
  sinFundamento: boolean;
  desdeCache: boolean;
  generadoEn?: string | null;
};

export function preguntarCopiloto(
  id: string,
  body: { tema: string; actividad?: string; refrescar?: boolean },
) {
  return request<CopilotoRespuesta>(
    `/api/establecimientos/${encodeURIComponent(id)}/copiloto`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export type CopilotoGuardado = {
  id: number;
  pregunta: string;
  respuesta: string;
  tema: string | null;
  seccion: string | null;
  modelo: string | null;
  guardadoEn: string;
  actualizado?: boolean;
};

export function fetchCopilotoGuardados(id: string) {
  return request<{ total: number; items: CopilotoGuardado[] }>(
    `/api/establecimientos/${encodeURIComponent(id)}/copiloto/guardados`,
  );
}

export function guardarCopilotoRespuesta(
  id: string,
  body: {
    pregunta: string;
    respuesta: string;
    tema?: string;
    seccion?: string;
    modelo?: string;
  },
) {
  return request<CopilotoGuardado>(
    `/api/establecimientos/${encodeURIComponent(id)}/copiloto/guardados`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export function eliminarCopilotoGuardado(id: string, guardadoId: number) {
  return request<{ ok: boolean; id: number }>(
    `/api/establecimientos/${encodeURIComponent(id)}/copiloto/guardados/${guardadoId}`,
    { method: "DELETE" },
  );
}

export type Serie = { clave: string; valor: number; scorePromedio?: number };

export type ShapAgregadoFactor = {
  feature: string;
  tema: string | null;
  etiqueta: string;
  ordenImportancia: number;
  meanAbsShap: number;
  meanShap: number;
  pctAumenta: number;
  itemsCohorte: number;
  metodo: string;
};

export type CoberturaSeriePunto = {
  snapshotId: number;
  periodoDecision: string;
  topK: number;
  ventanaInicio: string;
  ventanaFin: string;
  denominador: number;
  cubiertos: number;
  porcentaje: number;
  estado: string;
  activadoEn: string | null;
};

export type PrecisionSeriePunto = {
  snapshotId: number;
  periodo: string;
  topK: number;
  estado: string;
  denominador: number;
  positivos: number | null;
  porcentaje: number | null;
  ventanaInicio: string;
  ventanaFin: string;
  esHoldoutSeed: boolean;
};

export type AnaliticaEstadisticas = {
  snapshotId: number;
  periodo: string;
  horizonte: Horizonte;
  datosHasta: string | null;
  activadoEn: string | null;
  shapAgregado: {
    disponible: boolean;
    top50: ShapAgregadoFactor[];
    top225: ShapAgregadoFactor[];
    top1000: ShapAgregadoFactor[];
    advertencia: string;
  };
  coberturaCohorte: {
    top50: CoberturaSeriePunto | null;
    top225: CoberturaSeriePunto | null;
    top1000: CoberturaSeriePunto | null;
    serieTop50: CoberturaSeriePunto[];
    serieTop225: CoberturaSeriePunto[];
    serieTop1000: CoberturaSeriePunto[];
    nota: string;
  };
  precisionObservada: {
    top50: PrecisionSeriePunto | null;
    top225: PrecisionSeriePunto | null;
    top1000: PrecisionSeriePunto | null;
    serieTop50: PrecisionSeriePunto[];
    serieTop225: PrecisionSeriePunto[];
    serieTop1000: PrecisionSeriePunto[];
    holdoutReferenciaTop225Pct: number;
    holdoutReferenciaTop1000Pct: number;
    nota: string;
  };
  metodologia: {
    cobertura: string;
    precision: string;
    shap: string;
  };
};

export type Estadisticas = {
  periodo: string;
  horizonte: Horizonte;
  snapshotId?: number;
  total: number;
  scorePromedio: number;
  scoreMediana: number;
  byBanda: Serie[];
  byMotivo: Serie[];
  byCiiu: Serie[];
  bySector: Serie[];
  scoreBuckets: Serie[];
  aciertoBuckets: Serie[];
  visitasBuckets: Serie[];
  flags: {
    enCooldown: number;
    sinCooldown: number;
    obligacionPrs: number;
    alertaUmbral: number;
  };
  analitica?: AnaliticaEstadisticas;
};

const TOKEN_KEY = "pfi_token";
const USER_KEY = "pfi_user";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function getStoredUser(): User | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as User;
  } catch {
    return null;
  }
}

export function storeUser(user: User): void {
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(path, { ...init, headers });
  if (response.status === 401) {
    clearSession();
    throw new Error("Sesión expirada. Volvé a iniciar sesión.");
  }

  const text = await response.text();
  const parseJson = (): unknown => {
    if (!text.trim()) return null;
    try {
      return JSON.parse(text) as unknown;
    } catch {
      throw new Error(
        text.trim() || `La API respondió con un cuerpo inválido (HTTP ${response.status}).`,
      );
    }
  };

  if (!response.ok) {
    const parsed = parseJson() as { error?: string; title?: string; detail?: string } | null;
    const message =
      parsed?.error ||
      parsed?.detail ||
      parsed?.title ||
      text.trim() ||
      `Error HTTP ${response.status}`;
    throw new Error(message);
  }

  if (response.status === 204 || !text.trim()) {
    return undefined as T;
  }

  return parseJson() as T;
}

export type LoginResult =
  | { mfaRequired: true; mfaToken: string; user: User }
  | { mfaRequired?: false; user: User; access_token: string };

export async function login(email: string, password: string): Promise<LoginResult> {
  const data = await request<LoginResult & { access_token?: string; mfaToken?: string }>(
    "/api/auth/login",
    {
      method: "POST",
      body: JSON.stringify({ email, password }),
    },
  );
  if (data.mfaRequired && data.mfaToken) {
    return { mfaRequired: true, mfaToken: data.mfaToken, user: data.user };
  }
  if (!data.access_token) throw new Error("Respuesta de login inválida.");
  localStorage.setItem(TOKEN_KEY, data.access_token);
  storeUser(data.user);
  return { user: data.user, access_token: data.access_token };
}

export async function completeMfaLogin(mfaToken: string, code: string) {
  const data = await request<{ user: User; access_token: string }>("/api/auth/mfa", {
    method: "POST",
    body: JSON.stringify({ mfaToken, code }),
  });
  localStorage.setItem(TOKEN_KEY, data.access_token);
  storeUser(data.user);
  return data;
}

export function forgotPassword(email: string) {
  return request<{ ok: boolean }>("/api/auth/forgot-password", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export function resetPassword(token: string, nueva: string) {
  return request<{ ok: boolean }>("/api/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, nueva }),
  });
}

export function acceptInvite(token: string, nueva: string) {
  return request<{ ok: boolean; email?: string }>("/api/auth/aceptar-invitacion", {
    method: "POST",
    body: JSON.stringify({ token, nueva }),
  });
}

export function fetchUsuariosAdmin(params?: { rol?: string; activo?: boolean }) {
  const qs = new URLSearchParams();
  if (params?.rol) qs.set("rol", params.rol);
  if (params?.activo != null) qs.set("activo", String(params.activo));
  const q = qs.toString();
  return request<{ total: number; items: UsuarioAdmin[] }>(`/api/usuarios${q ? `?${q}` : ""}`);
}

export function createUsuario(body: {
  email: string;
  nombre: string;
  rol: string;
  zonaId?: number | null;
  latitud?: number | null;
  longitud?: number | null;
  mfaRequired?: boolean;
  disponibilidad?: DisponibilidadDia[];
}) {
  return request<UsuarioAdmin>("/api/usuarios", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateUsuario(
  id: number,
  body: {
    nombre?: string;
    rol?: string;
    activo?: boolean;
    zonaId?: number | null;
    latitud?: number | null;
    longitud?: number | null;
    mfaRequired?: boolean;
    resetMfa?: boolean;
    disponibilidad?: DisponibilidadDia[];
  },
) {
  return request<UsuarioAdmin>(`/api/usuarios/${id}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function reenviarInvitacion(id: number) {
  return request<{ ok: boolean }>(`/api/usuarios/${id}/reenviar-invitacion`, { method: "POST" });
}

export function setupMfa() {
  return request<{ secret: string; otpauthUrl: string }>("/api/me/mfa/setup", { method: "POST" });
}

export function confirmMfa(code: string) {
  return request<{ ok: boolean }>("/api/me/mfa/confirm", {
    method: "POST",
    body: JSON.stringify({ code }),
  });
}

export function fetchCandidatosAsignacion(fecha: string, hora: string, idEstablecimiento: string) {
  const qs = new URLSearchParams({ fecha, hora, idEstablecimiento });
  return request<{
    establecimiento: {
      idEstablecimiento: string;
      latitud: number;
      longitud: number;
      duracionEstimadaHoras?: number;
      tamano?: string;
      cantidadCapitas?: number | null;
    };
    gapHoras: number;
    duracionDefaultHoras?: number;
    pasoMinutos: number;
    recomendadoId: number | null;
    candidatos: CandidatoAsignacion[];
  }>(`/api/agenda/candidatos?${qs}`);
}

export function fetchCapacidadAgenda() {
  return request<{
    preventoresActivos: number;
    nota: string;
    semana: { fecha: string; visitas: number }[];
  }>("/api/agenda/capacidad");
}

export function fetchResumen(horizonte: Horizonte) {
  return request<Resumen>(`/api/resumen?horizonte=${horizonte}`);
}

export function fetchRiesgo(params: {
  horizonte: Horizonte;
  banda?: string;
  sector?: string;
  q?: string;
  motivo?: string;
  enCooldown?: string;
  obligacionPrs?: string;
  alertaUmbral?: string;
  programada?: string;
  estadoOperativo?: string;
  scoreMin?: string;
  scoreMax?: string;
  top?: number;
  page?: number;
  pageSize?: number;
}) {
  const qs = new URLSearchParams();
  qs.set("horizonte", params.horizonte);
  if (params.banda) qs.set("banda", params.banda);
  if (params.sector) qs.set("sector", params.sector);
  if (params.q) qs.set("q", params.q);
  if (params.motivo) qs.set("motivo", params.motivo);
  if (params.enCooldown) qs.set("enCooldown", params.enCooldown);
  if (params.obligacionPrs) qs.set("obligacionPrs", params.obligacionPrs);
  if (params.alertaUmbral) qs.set("alertaUmbral", params.alertaUmbral);
  if (params.programada) qs.set("programada", params.programada);
  if (params.estadoOperativo) qs.set("estadoOperativo", params.estadoOperativo);
  if (params.scoreMin) qs.set("scoreMin", params.scoreMin);
  if (params.scoreMax) qs.set("scoreMax", params.scoreMax);
  if (params.top) qs.set("top", String(params.top));
  if (params.page) qs.set("page", String(params.page));
  if (params.pageSize) qs.set("pageSize", String(params.pageSize));
  return request<{
    periodo: string;
    horizonte: Horizonte;
    total: number;
    page: number;
    pageSize: number;
    sectores?: string[];
    items: RankingItem[];
  }>(`/api/riesgo?${qs.toString()}`);
}

export function fetchEstablecimiento(id: string, horizonte: Horizonte) {
  return request<DetalleEstablecimiento>(
    `/api/establecimientos/${encodeURIComponent(id)}?horizonte=${horizonte}`,
  );
}

export function fetchEstadisticas(horizonte: Horizonte) {
  return request<Estadisticas>(`/api/estadisticas?horizonte=${horizonte}`);
}

export function updateProfile(nombre: string) {
  return request<User>("/api/me", {
    method: "PUT",
    body: JSON.stringify({ nombre }),
  });
}

export function changePassword(actual: string, nueva: string) {
  return request<{ ok: boolean }>("/api/me/password", {
    method: "PUT",
    body: JSON.stringify({ actual, nueva }),
  });
}

export function fetchUsuariosAsignables() {
  return request<UsuarioAsignable[]>("/api/usuarios/asignables");
}

export function fetchAgenda(params: {
  estado?: EstadoAgenda | "";
  desde?: string;
  hasta?: string;
  usuarioId?: string;
}) {
  const qs = new URLSearchParams();
  if (params.estado) qs.set("estado", params.estado);
  if (params.desde) qs.set("desde", params.desde);
  if (params.hasta) qs.set("hasta", params.hasta);
  if (params.usuarioId) qs.set("usuarioId", params.usuarioId);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return request<{ total: number; items: AgendaItem[] }>(`/api/agenda${suffix}`);
}

export function fetchAgendaById(id: number) {
  return request<AgendaItem>(`/api/agenda/${id}`);
}

export function programarVisita(body: {
  rankingItemId: number;
  fechaPlanificada: string;
  horaPlanificada?: string;
  horizonte: Horizonte;
  usuarioId?: number;
  notas?: string;
}) {
  return request<AgendaItem>("/api/agenda", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function reprogramarVisita(
  id: number,
  body: {
    fechaPlanificada?: string;
    horaPlanificada?: string;
    usuarioId?: number;
    notas?: string;
  },
) {
  return request<AgendaItem>(`/api/agenda/${id}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function realizarVisita(
  id: number,
  body: {
    fechaHoraReal?: string;
    hallazgos?: string;
    acciones?: string;
    notas?: string;
    resultadoGlobal?: "ok" | "observacion" | "critico" | string;
    revisita?: boolean;
    plazoRevisitaDias?: number;
    fechaRevisita?: string;
    horaRevisita?: string;
    notasActa?: string;
    /** Meses máx. para próxima visita (1|2|3|6). Omitir = no requiere. */
    reagendaMesesPlazo?: number | null;
    checklist?: ChecklistItemActa[];
    hallazgosActa?: HallazgoActaDraft[];
  },
) {
  return request<AgendaItem>(`/api/agenda/${id}/realizar`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export type ChecklistItemActa = {
  id: string;
  label: string;
  estado: "ok" | "observacion" | "no_aplica" | "no_verificado" | string;
  origen?: string;
};

export type HallazgoActaDraft = {
  severidad: "baja" | "media" | "alta" | string;
  hallazgo: string;
  recomendacion?: string;
  plazoDias?: number;
  normaRef?: string;
  itemRgrl?: string;
  /** Vincula el hallazgo al ítem del checklist marcado como Obs. */
  checklistItemId?: string;
  checklistLabel?: string;
  estado?: "abierto" | "cerrado" | string;
  origen?: "manual" | "sugerido_aceptado" | string;
};

export type HallazgoAbierto = {
  id: number;
  severidad: string;
  hallazgo: string;
  recomendacion: string | null;
  plazoDias: number | null;
  normaRef: string | null;
  itemRgrl: string | null;
  estado: string;
  origen: string;
  creadoEn: string;
  actaId?: number;
};

export function fetchActaContextoCierre(idEstablecimiento: string) {
  return request<{
    idEstablecimiento: string;
    hallazgosAbiertos: HallazgoAbierto[];
    checklistSugerido: ChecklistItemActa[];
  }>(`/api/establecimientos/${encodeURIComponent(idEstablecimiento)}/acta/contexto-cierre`);
}

export type RgrlCatalogItem = {
  id: string;
  label: string;
  actividad?: string | null;
  normaRef?: string | null;
};

export function fetchActaItemsRgrl() {
  return request<{ total: number; items: RgrlCatalogItem[] }>("/api/acta/items-rgrl");
}

export function fetchHallazgosAbiertos(idEstablecimiento: string) {
  return request<{ total: number; items: HallazgoAbierto[] }>(
    `/api/establecimientos/${encodeURIComponent(idEstablecimiento)}/hallazgos-abiertos`,
  );
}

export type VisitaHistorialHallazgo = {
  id: number;
  severidad: string;
  hallazgo: string;
  recomendacion: string | null;
  plazoDias: number | null;
  normaRef: string | null;
  itemRgrl: string | null;
  estado: string;
  origen: string;
};

export type VisitaHistorialItem = {
  id: number;
  fechaHoraReal: string;
  tipo: string;
  resultado: string;
  hallazgos: string | null;
  acciones: string | null;
  agendaItemId: number | null;
  responsable: { id: number; nombre: string; email: string } | null;
  acta: {
    id: number;
    resultadoGlobal: string;
    revisita: boolean;
    plazoRevisitaDias: number | null;
    notas: string | null;
    checklist: ChecklistItemActa[] | null;
    hallazgosTotal: number;
    hallazgosAbiertos: number;
    hallazgos: VisitaHistorialHallazgo[];
  } | null;
};

export function fetchVisitasEstablecimiento(idEstablecimiento: string) {
  return request<{ total: number; items: VisitaHistorialItem[] }>(
    `/api/establecimientos/${encodeURIComponent(idEstablecimiento)}/visitas`,
  );
}

export function patchHallazgo(id: number, body: { estado: "abierto" | "cerrado" | string }) {
  return request<HallazgoAbierto>(`/api/hallazgos/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function sugerirActaHallazgos(
  idEstablecimiento: string,
  body: {
    checklist?: ChecklistItemActa[];
    notas?: string;
    hallazgosPrevios?: HallazgoActaDraft[];
  },
) {
  return request<{
    modelo: string;
    hallazgos: HallazgoActaDraft[];
    nota: string | null;
  }>(`/api/establecimientos/${encodeURIComponent(idEstablecimiento)}/acta/sugerir`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Mejora el borrador escrito por el preventor y completa campos del hallazgo. */
export function mejorarHallazgoActa(
  idEstablecimiento: string,
  body: {
    borrador: string;
    recomendacion?: string;
    itemLabel?: string;
    severidad?: string;
  },
) {
  return request<{
    modelo: string;
    hallazgo: HallazgoActaDraft;
    nota: string | null;
  }>(`/api/establecimientos/${encodeURIComponent(idEstablecimiento)}/acta/mejorar-hallazgo`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function cancelarVisita(id: number, motivoCancelacion: string) {
  return request<AgendaItem>(`/api/agenda/${id}/cancelar`, {
    method: "POST",
    body: JSON.stringify({ motivoCancelacion }),
  });
}

export function fetchAgendaEventos(agendaId: number) {
  return request<{ total: number; items: AgendaEvento[]; nota: string | null }>(
    `/api/agenda/${agendaId}/eventos`,
  );
}

export function fetchAuditoriaAgenda(params: {
  tipo?: string;
  idEstablecimiento?: string;
  agendaItemId?: string;
  actorUsuarioId?: string;
  page?: number;
  pageSize?: number;
}) {
  const qs = new URLSearchParams();
  if (params.tipo) qs.set("tipo", params.tipo);
  if (params.idEstablecimiento) qs.set("idEstablecimiento", params.idEstablecimiento);
  if (params.agendaItemId) qs.set("agendaItemId", params.agendaItemId);
  if (params.actorUsuarioId) qs.set("actorUsuarioId", params.actorUsuarioId);
  if (params.page) qs.set("page", String(params.page));
  if (params.pageSize) qs.set("pageSize", String(params.pageSize));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return request<{ total: number; page: number; pageSize: number; items: AgendaEvento[] }>(
    `/api/auditoria/agenda${suffix}`,
  );
}

export function shortId(id: string): string {
  return id.length > 10 ? `${id.slice(0, 6)}…${id.slice(-4)}` : id;
}
