import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";

export type ToastKind = "success" | "error" | "info";

export type Toast = {
  id: number;
  kind: ToastKind;
  title: string;
  detail?: string;
};

type ToastApi = {
  push: (toast: Omit<Toast, "id">) => void;
  success: (title: string, detail?: string) => void;
  error: (title: string, detail?: string) => void;
  info: (title: string, detail?: string) => void;
};

const ToastContext = createContext<ToastApi | null>(null);

let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => {
    setItems((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const push = useCallback(
    (toast: Omit<Toast, "id">) => {
      const id = nextId++;
      setItems((prev) => [...prev.slice(-4), { ...toast, id }]);
      window.setTimeout(() => dismiss(id), 4200);
    },
    [dismiss],
  );

  const api = useMemo<ToastApi>(
    () => ({
      push,
      success: (title, detail) => push({ kind: "success", title, detail }),
      error: (title, detail) => push({ kind: "error", title, detail }),
      info: (title, detail) => push({ kind: "info", title, detail }),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-stack" aria-live="polite" aria-relevant="additions">
        {items.map((t) => (
          <div key={t.id} className={`toast toast-${t.kind}`} role="status">
            <span className="toast-icon" aria-hidden="true" />
            <div className="toast-body">
              <strong>{t.title}</strong>
              {t.detail ? <p>{t.detail}</p> : null}
            </div>
            <button
              type="button"
              className="toast-close"
              aria-label="Cerrar notificación"
              onClick={() => dismiss(t.id)}
            >
              ×
            </button>
            <span className="toast-progress" aria-hidden="true" />
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast fuera de ToastProvider");
  return ctx;
}
