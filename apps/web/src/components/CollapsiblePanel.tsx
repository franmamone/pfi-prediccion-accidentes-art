import { useId, type ReactNode } from "react";

type Props = {
  id: string;
  title: string;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
  trailing?: ReactNode;
  className?: string;
};

export function CollapsiblePanel({
  id,
  title,
  open,
  onToggle,
  children,
  trailing,
  className = "",
}: Props) {
  const contentId = useId();

  return (
    <section className={`panel collapsible-panel ${className}`.trim()} aria-labelledby={id}>
      <div className="collapsible-head">
        <button
          type="button"
          className="collapsible-toggle"
          aria-expanded={open}
          aria-controls={contentId}
          onClick={onToggle}
        >
          <span className={`collapsible-chevron${open ? " open" : ""}`} aria-hidden="true">
            ▾
          </span>
          <h2 id={id} className="page-title section-title-text">
            {title}
          </h2>
        </button>
        {trailing ? <div className="collapsible-trailing">{trailing}</div> : null}
      </div>
      {open ? (
        <div id={contentId} className="collapsible-body">
          {children}
        </div>
      ) : null}
    </section>
  );
}
