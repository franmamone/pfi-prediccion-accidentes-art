import { useEffect, useId, useRef } from "react";
import { IconInfo } from "../icons";

type InfoHintProps = {
  title: string;
  body: string;
  footer?: string;
  open: boolean;
  onToggle: () => void;
};

export function InfoHint({ title, body, footer, open, onToggle }: InfoHintProps) {
  const panelId = useId();
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onToggle();
    };
    const onPointer = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) {
        onToggle();
      }
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onPointer);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onPointer);
    };
  }, [open, onToggle]);

  return (
    <div className="info-hint" ref={rootRef}>
      <button
        type="button"
        className={`info-circle-btn${open ? " open" : ""}`}
        aria-label={`Cómo se calcula: ${title}`}
        title="Cómo se calcula"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={onToggle}
      >
        <IconInfo size={14} />
      </button>
      {open && (
        <div className="info-calc-panel" id={panelId} role="region" aria-label={`Cómo se calcula: ${title}`}>
          <div className="info-calc-panel-head">¿Cómo se calcula?</div>
          <p>{body}</p>
          {footer ? <p className="muted info-calc-panel-footer">{footer}</p> : null}
        </div>
      )}
    </div>
  );
}

type SectionTitleProps = {
  id?: string;
  children: string;
  infoTitle: string;
  infoBody?: string | null;
  infoFooter?: string;
  open: boolean;
  onToggle: () => void;
};

export function SectionTitleWithInfo({
  id,
  children,
  infoTitle,
  infoBody,
  infoFooter,
  open,
  onToggle,
}: SectionTitleProps) {
  return (
    <div className="section-title-row">
      <h2 id={id} className="page-title section-title-text">
        {children}
      </h2>
      {infoBody ? (
        <InfoHint
          title={infoTitle}
          body={infoBody}
          footer={infoFooter}
          open={open}
          onToggle={onToggle}
        />
      ) : null}
    </div>
  );
}
