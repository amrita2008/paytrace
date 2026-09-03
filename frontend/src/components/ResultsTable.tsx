/** Polished reconciliation results table with filtering. */

import { useState, useEffect } from "react";
import type { PaginatedResults } from "../types";
import { fetchResults } from "../api";
import StatusBadge from "./StatusBadge";
import EmptyState from "./EmptyState";

interface Props {
  onSelect: (groupId: string) => void;
  initialExceptionFilter: string | null;
}

const STATUS_OPTIONS = ["matched", "mismatched", "duplicate", "ambiguous"];
const EXCEPTION_OPTIONS = [
  "AMOUNT_MISMATCH",
  "TIMING_MISMATCH",
  "DUPLICATE",
  "AMBIGUOUS",
  "MISSING_SETTLEMENT",
  "FAILED_OR_REFUNDED",
  "ORPHAN_BANK_ENTRY",
];

export default function ResultsTable({ onSelect, initialExceptionFilter }: Props) {
  const [data, setData] = useState<PaginatedResults | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [excFilter, setExcFilter] = useState(initialExceptionFilter ?? "");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Sync excFilter when initialExceptionFilter changes
  useEffect(() => {
    setExcFilter(initialExceptionFilter ?? "");
  }, [initialExceptionFilter]);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const params: Record<string, string> = {};
    if (statusFilter) params.status = statusFilter;
    if (excFilter) params.exception_type = excFilter;

    fetchResults(params as Record<string, string>)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [statusFilter, excFilter]);

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">Reconciliation Results</div>
          {data && (
            <div className="card-subtitle">
              {data.total} group{data.total !== 1 ? "s" : ""}
            </div>
          )}
        </div>
      </div>

      <div className="filter-bar" style={{ marginBottom: "var(--space-4)" }}>
        <div className="filter-group">
          <span className="filter-label">Status</span>
          <select
            className="filter-select"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">All</option>
            {STATUS_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {s.charAt(0).toUpperCase() + s.slice(1)}
              </option>
            ))}
          </select>
        </div>

        <div className="filter-group">
          <span className="filter-label">Exception</span>
          <select
            className="filter-select"
            value={excFilter}
            onChange={(e) => setExcFilter(e.target.value)}
          >
            <option value="">All</option>
            {EXCEPTION_OPTIONS.map((s) => (
              <option key={s} value={s}>
                {formatType(s)}
              </option>
            ))}
          </select>
        </div>

        {data && (
          <span className="filter-count">
            Showing {data.results.length} of {data.total}
          </span>
        )}
      </div>

      {loading && (
        <EmptyState title="Loading results..." loading />
      )}

      {error && (
        <EmptyState icon="⚠" title="Failed to load" description={error} />
      )}

      {data && data.results.length === 0 && (
        <EmptyState
          icon="∅"
          title="No matching results"
          description="Try adjusting your filters."
        />
      )}

      {data && data.results.length > 0 && (
        <div className="table-container">
          <table className="results-table">
            <thead>
              <tr>
                <th>Status</th>
                <th>Group</th>
                <th>Exception</th>
                <th>Payments</th>
                <th>Settlements</th>
                <th>Bank</th>
                <th>Score</th>
                <th>Review</th>
              </tr>
            </thead>
            <tbody>
              {data.results.map((r) => (
                <tr key={r.group_id} onClick={() => onSelect(r.group_id)}>
                  <td>
                    <StatusBadge status={r.status} />
                  </td>
                  <td className="cell-mono">{r.group_id}</td>
                  <td>
                    {r.exception_type ? (
                      <span className="badge badge-exception">
                        {formatType(r.exception_type)}
                      </span>
                    ) : (
                      <span className="cell-secondary">—</span>
                    )}
                  </td>
                  <td className="cell-secondary">{r.payment_ids.length}</td>
                  <td className="cell-secondary">{r.settlement_ids.length}</td>
                  <td className="cell-secondary">{r.bank_entry_ids.length}</td>
                  <td className="cell-secondary">
                    {r.match_score !== null ? r.match_score : "—"}
                  </td>
                  <td>
                    {r.human_review_required && (
                      <span className="badge badge-review">Review</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function formatType(type: string): string {
  return type
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
