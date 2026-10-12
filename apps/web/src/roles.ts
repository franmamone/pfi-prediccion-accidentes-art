export function esPreventor(rol: string | undefined | null): boolean {
  return rol === "Prevencionista";
}

export function puedeGestionar(rol: string | undefined | null): boolean {
  return rol === "Admin" || rol === "Coordinador";
}

export function esAdmin(rol: string | undefined | null): boolean {
  return rol === "Admin";
}

/** Marcar realizada / cancelar: Admin o Prevencionista (no Coordinador). */
export function puedeCerrarVisita(rol: string | undefined | null): boolean {
  return rol === "Admin" || rol === "Prevencionista";
}

export function landingFor(rol: string | undefined | null): string {
  return esPreventor(rol) ? "/agenda" : "/riesgo";
}
