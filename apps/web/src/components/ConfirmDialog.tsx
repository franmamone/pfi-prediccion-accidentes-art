type Props = {
  title: string;
  detail?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onClose: () => void;
};

export function ConfirmDialog({
  title,
  detail,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  danger = false,
  onConfirm,
  onClose,
}: Props) {
  return (
    <div className="modal-backdrop" role="presentation" onClick={onClose}>
      <div
        className="modal panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        onClick={(ev) => ev.stopPropagation()}
      >
        <h2 id="confirm-dialog-title" className="page-title" style={{ fontSize: 18, marginBottom: 6 }}>
          {title}
        </h2>
        {detail ? (
          <p className="page-sub" style={{ marginBottom: 16 }}>
            {detail}
          </p>
        ) : (
          <div style={{ marginBottom: 10 }} />
        )}
        <div className="modal-actions">
          <button type="button" className="ghost-btn" onClick={onClose} autoFocus>
            {cancelLabel}
          </button>
          <button
            type="button"
            className={danger ? "btn danger" : "btn"}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
