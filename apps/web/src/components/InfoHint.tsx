import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { IconInfo } from "../icons";

const MOBILE_MQ = "(max-width: 640px)";

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
  const panelRef = useRef<HTMLDivElement>(null);
  const [alignEnd, setAlignEnd] = useState(false);
  const [mobileCenter, setMobileCenter] = useState(
    () => typeof window !== "undefined" && window.matchMedia(MOBILE_MQ).matches,
  );

  useEffect(() => {
    const mq = window.matchMedia(MOBILE_MQ);
    const sync = () => setMobileCenter(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

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

  useLayoutEffect(() => {
    if (!open || mobileCenter || !rootRef.current || !panelRef.current) {
      setAlignEnd(false);
      return;
    }
    const rootRect = rootRef.current.getBoundingClientRect();
    const panelWidth = panelRef.current.offsetWidth;
    const margin = 12;
    const overflowsRight = rootRect.left + panelWidth > window.innerWidth - margin;
    const nearRightEdge = rootRect.right > window.innerWidth * 0.55;
    setAlignEnd(overflowsRight || nearRightEdge);
  }, [open, body, footer, mobileCenter]);

  return (
    <div
      className={`info-hint${alignEnd ? " align-end" : ""}${mobileCenter ? " info-hint-mobile" : ""}`}
      ref={rootRef}
    >
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
      {open && mobileCenter ? (
        <button
          type="button"
          className="info-calc-backdrop"
          aria-label="Cerrar información"
          onClick={onToggle}
        />
      ) : null}
      {open && (
        <div
          ref={panelRef}
          className="info-calc-panel"
          id={panelId}
          role="region"
          aria-label={`Cómo se calcula: ${title}`}
        >
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
