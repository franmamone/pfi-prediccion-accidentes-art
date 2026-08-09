export function esPreventor(rol: string | undefined | null): boolean {
  return rol === "Prevencionista";
}

export function puedeGestionar(rol: string | undefined | null): boolean {
  return rol === "Admin" || rol === "Coordinador";
}

export function landingFor(rol: string | undefined | null): string {
  return esPreventor(rol) ? "/agenda" : "/riesgo";
}
