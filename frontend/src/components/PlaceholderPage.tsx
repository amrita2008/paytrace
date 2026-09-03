/** Placeholder for navigation items not yet implemented. */

interface Props {
  title: string;
  description: string;
}

export default function PlaceholderPage({ title, description }: Props) {
  return (
    <div className="state-container">
      <div className="state-icon">🔒</div>
      <div className="state-title">{title}</div>
      <div className="state-desc">{description}</div>
    </div>
  );
}
