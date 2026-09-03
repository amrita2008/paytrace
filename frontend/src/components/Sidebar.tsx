/** PayTrace navigation sidebar. */

export type Page =
  | "overview"
  | "reconciliation"
  | "exceptions"
  | "ai-insights"
  | "settings";

interface Props {
  activePage: Page;
  onNavigate: (page: Page) => void;
  hasErrors: boolean;
  humanReviewCount: number;
}

const NAV_ITEMS: { id: Page; label: string; icon: string; section?: string }[] = [
  { id: "overview", label: "Overview", icon: "◉", section: "Main" },
  { id: "reconciliation", label: "Reconciliation", icon: "⊞" },
  { id: "exceptions", label: "Exceptions", icon: "⚠" },
  { id: "ai-insights", label: "AI Insights", icon: "✦", section: "Advanced" },
  { id: "settings", label: "Settings", icon: "⚙" },
];

export default function Sidebar({ activePage, onNavigate, hasErrors, humanReviewCount }: Props) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-brand-icon">P</div>
        <span className="sidebar-brand-name">PayTrace</span>
        <span className="sidebar-brand-tag">v0.1</span>
      </div>

      <nav className="sidebar-nav">
        {NAV_ITEMS.map((item) => (
          <div key={item.id}>
            {item.section && (
              <div className="sidebar-section-label">{item.section}</div>
            )}
            <button
              className={`sidebar-item${activePage === item.id ? " active" : ""}`}
              onClick={() => onNavigate(item.id)}
            >
              <span className="sidebar-item-icon">{item.icon}</span>
              {item.label}
              {item.id === "exceptions" && humanReviewCount > 0 && (
                <span className="sidebar-item-badge">{humanReviewCount}</span>
              )}
            </button>
          </div>
        ))}
      </nav>

      <div className="sidebar-footer">
        <span
          className="sidebar-status-dot"
          style={{ background: hasErrors ? "var(--color-mismatched)" : "var(--color-matched)" }}
        />
        {hasErrors ? "Error detected" : "System ready"}
      </div>
    </aside>
  );
}
