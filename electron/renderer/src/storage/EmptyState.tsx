export function EmptyState({
  title,
  detail,
  actionLabel,
  onAction,
}: {
  title: string;
  detail?: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="empty-state">
      <h2>{title}</h2>
      {detail && <p>{detail}</p>}
      {actionLabel && onAction && (
        <button className="ghost-action" type="button" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </div>
  );
}
