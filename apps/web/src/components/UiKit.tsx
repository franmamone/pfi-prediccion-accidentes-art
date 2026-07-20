import { useEffect, useRef, useState, type ReactNode } from "react";
import { prefersReducedMotion } from "../prefs";

export function Skeleton({
  height = 16,
  width = "100%",
  className = "",
}: {
  height?: number | string;
  width?: number | string;
  className?: string;
}) {
  return (
    <div
      className={`skeleton ${className}`.trim()}
      style={{ height, width }}
      aria-hidden="true"
    />
  );
}

export function SkeletonStats({ count = 4 }: { count?: number }) {
  return (
    <div className="stats" aria-busy="true" aria-label="Cargando indicadores">
      {Array.from({ length: count }).map((_, i) => (
        <div className="stat skeleton-stat" key={i}>
          <Skeleton height={12} width="55%" />
          <Skeleton height={28} width="40%" className="skeleton-gap" />
        </div>
      ))}
    </div>
  );
}

export function SkeletonPanel({ lines = 4 }: { lines?: number }) {
  return (
    <div className="panel" aria-busy="true">
      <Skeleton height={18} width="35%" />
      <div className="skeleton-stack">
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton key={i} height={12} width={`${88 - i * 8}%`} />
        ))}
      </div>
    </div>
  );
}

export function SkeletonTable({ rows = 8 }: { rows?: number }) {
  return (
    <div className="panel table-wrap" aria-busy="true" aria-label="Cargando tabla">
      <div className="skeleton-stack" style={{ padding: 14 }}>
        <Skeleton height={16} width="100%" />
        {Array.from({ length: rows }).map((_, i) => (
          <Skeleton key={i} height={14} width={`${96 - (i % 4) * 6}%`} />
        ))}
      </div>
    </div>
  );
}

export function EmptyState({
  title,
  detail,
  action,
}: {
  title: string;
  detail?: string;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state" role="status">
      <div className="empty-state-mark" aria-hidden="true" />
      <h3>{title}</h3>
      {detail ? <p>{detail}</p> : null}
      {action ? <div className="empty-state-action">{action}</div> : null}
    </div>
  );
}

export function AnimatedNumber({
  value,
  decimals = 0,
  suffix = "",
}: {
  value: number;
  decimals?: number;
  suffix?: string;
}) {
  const [display, setDisplay] = useState(prefersReducedMotion() ? value : 0);
  const fromRef = useRef(0);

  useEffect(() => {
    if (prefersReducedMotion()) {
      setDisplay(value);
      return;
    }
    const from = fromRef.current;
    const to = value;
    const start = performance.now();
    const duration = 650;
    let raf = 0;
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      const current = from + (to - from) * eased;
      setDisplay(current);
      if (t < 1) raf = requestAnimationFrame(tick);
      else fromRef.current = to;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);

  return (
    <>
      {display.toLocaleString("es-AR", {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
      })}
      {suffix}
    </>
  );
}

export function Reveal({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [visible, setVisible] = useState(prefersReducedMotion());

  useEffect(() => {
    if (prefersReducedMotion()) return;
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          obs.disconnect();
        }
      },
      { threshold: 0.18 },
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  return (
    <div ref={ref} className={`reveal${visible ? " reveal-in" : ""} ${className}`.trim()}>
      {children}
    </div>
  );
}
