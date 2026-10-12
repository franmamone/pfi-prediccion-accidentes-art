const POST_LOGIN_KEY = "prevex.postLoginNext";

/** Solo paths relativos internos (evita open redirect). */
export function sanitizeNextPath(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const next = raw.trim();
  if (!next.startsWith("/") || next.startsWith("//") || next.includes("://")) return null;
  return next;
}

export function rememberPostLoginNext(path: string | null) {
  if (!path) {
    sessionStorage.removeItem(POST_LOGIN_KEY);
    return;
  }
  sessionStorage.setItem(POST_LOGIN_KEY, path);
}

export function takePostLoginNext(): string | null {
  const raw = sessionStorage.getItem(POST_LOGIN_KEY);
  sessionStorage.removeItem(POST_LOGIN_KEY);
  return sanitizeNextPath(raw);
}

export function peekPostLoginNext(): string | null {
  return sanitizeNextPath(sessionStorage.getItem(POST_LOGIN_KEY));
}
