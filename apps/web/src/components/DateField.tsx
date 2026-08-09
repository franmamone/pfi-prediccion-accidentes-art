import { useEffect, useMemo, useRef, useState } from "react";

type Props = {
  value: string; // ISO yyyy-mm-dd ("" = sin fecha)
  onChange: (value: string) => void;
  min?: string; // ISO yyyy-mm-dd
  ariaLabel?: string;
  placeholder?: string;
  disabled?: boolean;
  className?: string;
};

const DOW = ["LU", "MA", "MI", "JU", "VI", "SA", "DO"];

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function toIso(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function parseIso(s: string): Date | null {
  if (!s) return null;
  const [y, m, d] = s.split("-").map(Number);
  if (!y || !m || !d) return null;
  return new Date(y, m - 1, d);
}

function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1);
}

function sameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  );
}

function monthMatrix(view: Date): Date[][] {
  const first = startOfMonth(view);
  const offset = (first.getDay() + 6) % 7; // lunes primero
  const start = new Date(first);
  start.setDate(1 - offset);
  const weeks: Date[][] = [];
  for (let w = 0; w < 6; w++) {
    const row: Date[] = [];
    for (let i = 0; i < 7; i++) {
      const dt = new Date(start);
      dt.setDate(start.getDate() + w * 7 + i);
      row.push(dt);
    }
    weeks.push(row);
  }
  return weeks;
}

const titleFmt = new Intl.DateTimeFormat("es-AR", { month: "long", year: "numeric" });
const valueFmt = new Intl.DateTimeFormat("es-AR", {
  weekday: "short",
  day: "numeric",
  month: "short",
  year: "numeric",
});

function capitalize(s: string): string {
  return s ? s.charAt(0).toUpperCase() + s.slice(1) : s;
}

export function DateField({
  value,
  onChange,
  min,
  ariaLabel,
  placeholder = "Elegí una fecha…",
  disabled,
  className,
}: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  const selected = useMemo(() => parseIso(value), [value]);
  const minDate = useMemo(() => parseIso(min ?? ""), [min]);
  const today = useMemo(() => {
    const d = new Date();
    return new Date(d.getFullYear(), d.getMonth(), d.getDate());
  }, []);

  const [view, setView] = useState<Date>(() => startOfMonth(selected ?? today));

  useEffect(() => {
    if (open) setView(startOfMonth(selected ?? today));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEffect(() => {
    if (!open) return;
    function onDocClick(ev: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(ev.target as Node)) setOpen(false);
    }
    function onKey(ev: KeyboardEvent) {
      if (ev.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  const weeks = useMemo(() => monthMatrix(view), [view]);

  function isDisabled(d: Date): boolean {
    return minDate != null && d < minDate;
  }

  function commit(d: Date) {
    if (isDisabled(d)) return;
    onChange(toIso(d));
    setOpen(false);
  }

  return (
    <div
      ref={rootRef}
      className={`ui-select ui-date${open ? " open" : ""}${disabled ? " disabled" : ""}${className ? ` ${className}` : ""}`}
    >
      <button
        type="button"
        className="ui-select-trigger"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={ariaLabel}
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
      >
        <span className={selected ? "ui-select-value" : "ui-select-placeholder"}>
          {selected ? capitalize(valueFmt.format(selected)) : placeholder}
        </span>
        <svg className="ui-date-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <rect x="3" y="4.5" width="18" height="16" rx="2.5" stroke="currentColor" strokeWidth="1.6" />
          <path d="M3 9h18M8 3v3M16 3v3" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
        </svg>
      </button>

      {open && (
        <div className="ui-select-pop ui-date-pop" role="dialog" aria-label={ariaLabel ?? "Calendario"}>
          <div className="ui-date-head">
            <span className="ui-date-title">{capitalize(titleFmt.format(view))}</span>
            <div className="ui-date-nav">
              <button
                type="button"
                aria-label="Mes anterior"
                onClick={() => setView(new Date(view.getFullYear(), view.getMonth() - 1, 1))}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M15 6l-6 6 6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
              <button
                type="button"
                aria-label="Mes siguiente"
                onClick={() => setView(new Date(view.getFullYear(), view.getMonth() + 1, 1))}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path d="M9 6l6 6-6 6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </button>
            </div>
          </div>

          <div className="ui-date-grid">
            {DOW.map((d) => (
              <span key={d} className="ui-date-dow">
                {d}
              </span>
            ))}
            {weeks.flat().map((d) => {
              const fuera = d.getMonth() !== view.getMonth();
              const dis = isDisabled(d);
              const sel = selected != null && sameDay(d, selected);
              const hoy = sameDay(d, today);
              return (
                <button
                  key={toIso(d)}
                  type="button"
                  disabled={dis}
                  className={`ui-date-cell${fuera ? " out" : ""}${sel ? " selected" : ""}${hoy && !sel ? " today" : ""}`}
                  onClick={() => commit(d)}
                >
                  {d.getDate()}
                </button>
              );
            })}
          </div>

          <div className="ui-date-foot">
            <button type="button" onClick={() => onChange("")}>
              Borrar
            </button>
            <button type="button" onClick={() => commit(today)} disabled={isDisabled(today)}>
              Hoy
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
