import { useEffect } from "react";

/** Evita que el scroll del modal/lista arrastre la página de detrás. */
export function useLockBodyScroll(locked = true) {
  useEffect(() => {
    if (!locked) return;
    const body = document.body;
    const html = document.documentElement;
    const prevBody = body.style.overflow;
    const prevHtml = html.style.overflow;
    body.style.overflow = "hidden";
    html.style.overflow = "hidden";
    return () => {
      body.style.overflow = prevBody;
      html.style.overflow = prevHtml;
    };
  }, [locked]);
}
