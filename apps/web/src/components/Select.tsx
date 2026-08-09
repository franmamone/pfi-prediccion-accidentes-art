import { useEffect, useMemo, useRef, useState } from "react";

export type SelectOption = { value: string; label: string };

type Props = {
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  ariaLabel?: string;
  disabled?: boolean;
  searchable?: boolean;
  className?: string;
};

export function Select({
  value,
  onChange,
  options,
  placeholder = "Seleccionar…",
  ariaLabel,
  disabled,
  searchable,
  className,
}: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  const conBusqueda = searchable ?? options.length > 8;
  const selected = options.find((o) => o.value === value) ?? null;

  const filtered = useMemo(() => {
    if (!conBusqueda || !query.trim()) return options;
    const q = query.trim().toLowerCase();
    return options.filter((o) => o.label.toLowerCase().includes(q));
  }, [options, query, conBusqueda]);

  useEffect(() => {
    if (!open) return;
    function onDocClick(ev: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(ev.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, [open]);

  useEffect(() => {
    if (open) {
      setQuery("");
      const idx = filtered.findIndex((o) => o.value === value);
      setActive(idx >= 0 ? idx : 0);
      if (conBusqueda) window.setTimeout(() => searchRef.current?.focus(), 10);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function commit(opt: SelectOption) {
    onChange(opt.value);
    setOpen(false);
  }

  function onKeyDown(ev: React.KeyboardEvent) {
    if (ev.key === "Escape") {
      setOpen(false);
      return;
    }
    if (!open && (ev.key === "ArrowDown" || ev.key === "Enter" || ev.key === " ")) {
      ev.preventDefault();
      setOpen(true);
      return;
    }
    if (ev.key === "ArrowDown") {
      ev.preventDefault();
      setActive((a) => Math.min(a + 1, filtered.length - 1));
    } else if (ev.key === "ArrowUp") {
      ev.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (ev.key === "Enter") {
      ev.preventDefault();
      const opt = filtered[active];
      if (opt) commit(opt);
    }
  }

  return (
    <div
      ref={rootRef}
      className={`ui-select${open ? " open" : ""}${disabled ? " disabled" : ""}${className ? ` ${className}` : ""}`}
      onKeyDown={onKeyDown}
    >
      <button
        type="button"
        className="ui-select-trigger"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={ariaLabel}
        disabled={disabled}
        onClick={() => setOpen((o) => !o)}
      >
        <span className={selected ? "ui-select-value" : "ui-select-placeholder"}>
          {selected ? selected.label : placeholder}
        </span>
        <svg className="ui-select-chevron" width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
          <path d="M6 9l6 6 6-6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <div className="ui-select-pop" role="listbox">
          {conBusqueda && (
            <div className="ui-select-search">
              <input
                ref={searchRef}
                type="text"
                value={query}
                placeholder="Buscar…"
                onChange={(e) => {
                  setQuery(e.target.value);
                  setActive(0);
                }}
              />
            </div>
          )}
          <div className="ui-select-list">
            {filtered.length === 0 ? (
              <div className="ui-select-empty">Sin resultados</div>
            ) : (
              filtered.map((o, i) => (
                <button
                  key={o.value || "__all__"}
                  type="button"
                  role="option"
                  aria-selected={o.value === value}
                  className={`ui-select-option${o.value === value ? " selected" : ""}${i === active ? " active" : ""}`}
                  onMouseEnter={() => setActive(i)}
                  onClick={() => commit(o)}
                >
                  <span>{o.label}</span>
                  {o.value === value && (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                      <path d="M5 13l4 4L19 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  )}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
