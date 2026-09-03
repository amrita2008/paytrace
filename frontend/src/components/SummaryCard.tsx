/** KPI summary cards with fintech-style design. */

import type { ReconciliationSummary } from "../types";

interface Props {
  data: ReconciliationSummary;
}

export default function SummaryCard({ data }: Props) {
  const matchedCount = data.status_counts["matched"] ?? 0;
  const matchRate =
    data.total_groups > 0
      ? ((matchedCount / data.total_groups) * 100).toFixed(1)
      : "0.0";
  const exceptionTotal = Object.values(data.exception_type_counts).reduce(
    (s, c) => s + c,
    0
  );

  return (
    <div>
      {/* Primary KPIs */}
      <div className="kpi-grid">
        <div className="kpi-card primary">
          <div className="kpi-value">{data.total_groups}</div>
          <div className="kpi-label">Reconciliation Groups</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-value">{data.total_payments}</div>
          <div className="kpi-label">Payments</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-value">{data.total_settlements}</div>
          <div className="kpi-label">Settlements</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-value">{data.total_bank_entries}</div>
          <div className="kpi-label">Bank Entries</div>
        </div>
      </div>

      {/* Secondary KPIs */}
      <div className="kpi-grid" style={{ marginTop: "var(--space-4)" }}>
        <div className="kpi-card success">
          <div className="kpi-value">{matchRate}%</div>
          <div className="kpi-label">Match Rate</div>
        </div>
        <div className="kpi-card danger">
          <div className="kpi-value">{exceptionTotal}</div>
          <div className="kpi-label">Total Exceptions</div>
        </div>
        <div className="kpi-card warning">
          <div className="kpi-value">{data.human_review_required_count}</div>
          <div className="kpi-label">Requires Review</div>
        </div>
        <div className="kpi-card">
          <div className="kpi-value">{matchedCount}</div>
          <div className="kpi-label">Matched Groups</div>
        </div>
      </div>

      {/* Status badges */}
      <div className="summary-status-row">
        {Object.entries(data.status_counts).map(([status, count]) => (
          <span key={status} className={`badge badge-${status === "matched" ? "matched" : status === "mismatched" ? "mismatched" : status === "duplicate" ? "duplicate" : status === "ambiguous" ? "ambiguous" : "neutral"}`}>
            {status}: {count}
          </span>
        ))}
      </div>

      {/* Timestamp */}
      <div className="summary-timestamp">
        Processed: {new Date(data.processing_timestamp).toLocaleString()}
      </div>
    </div>
  );
}
