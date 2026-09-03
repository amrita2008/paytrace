/** Shared empty/loading/error state component. */

interface Props {
  icon?: string;
  title: string;
  description?: string;
  loading?: boolean;
}

export default function EmptyState({ icon, title, description, loading }: Props) {
  return (
    <div className="state-container">
      {loading ? (
        <div className="spinner" />
      ) : (
        icon && <div className="state-icon">{icon}</div>
      )}
      <div className="state-title">{title}</div>
      {description && <div className="state-desc">{description}</div>}
    </div>
  );
}
