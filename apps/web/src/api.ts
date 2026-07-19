export type Horizonte = "1m" | "3m";

export type User = {
  id: number;
  email: string;
  nombre: string;
  rol: string;
  zonaId: number | null;
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
  nota: string;
};

export type RankingItem = {
  id: number;
  idEstablecimiento: string;
  idEmpleador: string | null;
  ranking: number;
  scoreRiesgo: number;
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

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(path, { ...init, headers });
  if (response.status === 401) {
    clearSession();
    throw new Error("Sesión expirada. Volvé a iniciar sesión.");
  }
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Error HTTP ${response.status}`);
  }
  return (await response.json()) as T;
}

export async function login(email: string, password: string): Promise<{ user: User; access_token: string }> {
  const data = await request<{ user: User; access_token: string }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(data.user));
  return data;
}

export function fetchResumen(horizonte: Horizonte) {
  return request<Resumen>(`/api/resumen?horizonte=${horizonte}`);
}

export function fetchRiesgo(params: {
  horizonte: Horizonte;
  banda?: string;
  sector?: string;
  q?: string;
  top?: number;
}) {
  const qs = new URLSearchParams();
  qs.set("horizonte", params.horizonte);
  if (params.banda) qs.set("banda", params.banda);
  if (params.sector) qs.set("sector", params.sector);
  if (params.q) qs.set("q", params.q);
  if (params.top) qs.set("top", String(params.top));
  return request<{ periodo: string; horizonte: Horizonte; total: number; items: RankingItem[] }>(
    `/api/riesgo?${qs.toString()}`,
  );
}

export function fetchEstablecimiento(id: string, horizonte: Horizonte) {
  return request<RankingItem>(`/api/establecimientos/${encodeURIComponent(id)}?horizonte=${horizonte}`);
}

export function shortId(id: string): string {
  return id.length > 10 ? `${id.slice(0, 6)}…${id.slice(-4)}` : id;
}
