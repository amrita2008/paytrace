/** Shared status badge component. */

const BADGE_CLASS: Record<string, string> = {
  matched: "badge-matched",
  mismatched: "badge-mismatched",
  duplicate: "badge-duplicate",
  ambiguous: "badge-ambiguous",
};

export default function StatusBadge({
  status,
  children,
}: {
  status: string;
  children?: React.ReactNode;
}) {
  const cls = BADGE_CLASS[status] ?? "badge-neutral";
  return (
    <span className={`badge ${cls}`}>
      {children ?? status}
    </span>
  );
}
