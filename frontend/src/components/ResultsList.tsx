import { useState, useEffect } from "react";
import type { ResultSummary, PaginatedResults } from "../types";
import { fetchResults } from "../api";

interface Props {
  onSelect: (groupId: string) => void;
}

const STATUS_OPTIONS = ["", "matched", "mismatched", "duplicate", "ambiguous"];
const EXCEPTION_OPTIONS = [
  "",
  "AMOUNT_MISMATCH",
  "TIMING_MISMATCH",
  "DUPLICATE",
  "AMBIGUOUS",
  "MISSING_SETTLEMENT",
  "FAILED_OR_REFUNDED",
  "ORPHAN_BANK_ENTRY",
];

const STATUS_COLOR: Record<string, string> = {
  matched: "#16a34a",
  mismatched: "#dc2626",
  duplicate: "#d97706",
  ambiguous: "#7c3aed",
  missing: "#6b7280",
  unresolved: "#6b7280",
};

export default function ResultsList({ onSelect }: Props) {
  const [data, setData] = useState<PaginatedResults | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [excFilter, setExcFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const params: Record<string, string> = {};
    if (statusFilter) params.status = statusFilter;
    if (excFilter) params.exception_type = excFilter;

    fetchResults(params as any)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [statusFilter, excFilter]);

  return (
    <div style={styles.card}>
      <h2 style={styles.title}>Reconciliation Results</h2>

      <div style={styles.filters}>
        <label style={styles.filterLabel}>
          Status:
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={styles.select}
          >
            <option value="">All</option>
            {STATUS_OPTIONS.filter(Boolean).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>

        <label style={styles.filterLabel}>
          Exception:
          <select
            value={excFilter}
            onChange={(e) => setExcFilter(e.target.value)}
            style={styles.select}
          >
            <option value="">All</option>
            {EXCEPTION_OPTIONS.filter(Boolean).map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
      </div>

      {loading && <p style={styles.loading}>Loading...</p>}
      {error && <p style={styles.error}>{error}</p>}

      {data && (
        <>
          <p style={styles.count}>
            {data.total} group{data.total !== 1 ? "s" : ""} found
          </p>
          <div style={styles.list}>
            {data.results.map((r) => (
              <ResultRow key={r.group_id} result={r} onSelect={onSelect} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}

function ResultRow({
  result,
  onSelect,
}: {
  result: ResultSummary;
  onSelect: (id: string) => void;
}) {
  const color = STATUS_COLOR[result.status] ?? "#6b7280";
  return (
    <div style={styles.row} onClick={() => onSelect(result.group_id)}>
      <div style={styles.rowHeader}>
        <span style={{ ...styles.statusBadge, backgroundColor: color }}>
          {result.status}
        </span>
        <strong style={styles.groupId}>{result.group_id}</strong>
        {result.exception_type && (
          <span style={styles.excBadge}>{result.exception_type}</span>
        )}
        {result.human_review_required && (
          <span style={styles.reviewBadge}>Review</span>
        )}
      </div>
      {result.evidence_summary && (
        <p style={styles.summary}>{result.evidence_summary}</p>
      )}
      <div style={styles.rowMeta}>
        <span>{result.payment_ids.length} payment(s)</span>
        <span>{result.settlement_ids.length} settlement(s)</span>
        <span>{result.bank_entry_ids.length} bank(s)</span>
        <span>{result.evidence_count} evidence</span>
        {result.match_score !== null && (
          <span>Score: {result.match_score}</span>
        )}
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  card: {
    background: "#fff",
    borderRadius: 12,
    padding: 24,
    boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
    marginBottom: 24,
  },
  title: { margin: "0 0 16px 0", fontSize: 20 },
  filters: { display: "flex", gap: 16, marginBottom: 16, flexWrap: "wrap" },
  filterLabel: { fontSize: 13, color: "#555", display: "flex", alignItems: "center", gap: 6 },
  select: {
    padding: "4px 8px",
    borderRadius: 6,
    border: "1px solid #ddd",
    fontSize: 13,
  },
  loading: { color: "#888" },
  error: { color: "#dc2626" },
  count: { fontSize: 13, color: "#666", margin: "0 0 12px 0" },
  list: { display: "flex", flexDirection: "column" as const, gap: 8 },
  row: {
    border: "1px solid #e5e7eb",
    borderRadius: 8,
    padding: 12,
    cursor: "pointer",
    transition: "border-color 0.15s",
  },
  rowHeader: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    flexWrap: "wrap",
  },
  statusBadge: {
    color: "#fff",
    padding: "2px 8px",
    borderRadius: 4,
    fontSize: 12,
    fontWeight: 600,
  },
  groupId: { fontSize: 14 },
  excBadge: {
    background: "#fef3c7",
    color: "#92400e",
    padding: "2px 8px",
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 500,
  },
  reviewBadge: {
    background: "#fee2e2",
    color: "#991b1b",
    padding: "2px 8px",
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 500,
  },
  summary: {
    margin: "6px 0 4px 0",
    fontSize: 13,
    color: "#555",
  },
  rowMeta: {
    display: "flex",
    gap: 12,
    fontSize: 12,
    color: "#888",
  },
};
