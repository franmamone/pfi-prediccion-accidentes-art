import { useEffect, useState, type ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { prefersReducedMotion } from "../prefs";

export function PageTransition({ children }: { children: ReactNode }) {
  const location = useLocation();
  const [ready, setReady] = useState(true);

  useEffect(() => {
    if (prefersReducedMotion()) {
      setReady(true);
      return;
    }
    setReady(false);
    const id = window.requestAnimationFrame(() => setReady(true));
    return () => cancelAnimationFrame(id);
  }, [location.pathname]);

  return (
    <div key={location.pathname} className={`page-transition${ready ? " in" : ""}`}>
      {children}
    </div>
  );
}
