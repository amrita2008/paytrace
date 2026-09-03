/** Exception overview section — shows exception types with severity. */

import type { ReconciliationSummary } from "../types";

interface Props {
  data: ReconciliationSummary;
  activeException: string | null;
  onSelectException: (type: string | null) => void;
}

const EXCEPTION_CONFIG: Record<string, { severity: string; desc: string }> = {
  AMOUNT_MISMATCH: {
    severity: "critical",
    desc: "Settlement amounts differ from expected payment totals",
  },
  MISSING_SETTLEMENT: {
    severity: "critical",
    desc: "Payments without a corresponding settlement record",
  },
  FAILED_OR_REFUNDED: {
    severity: "critical",
    desc: "Payments that failed or were refunded",
  },
  TIMING_MISMATCH: {
    severity: "warning",
    desc: "Settlement timing exceeds expected window",
  },
  ORPHAN_BANK_ENTRY: {
    severity: "warning",
    desc: "Bank entries without matching settlement records",
  },
  DUPLICATE: {
    severity: "info",
    desc: "Duplicate payment identifiers detected",
  },
  AMBIGUOUS: {
    severity: "info",
    desc: "Settlements with multiple possible payment matches",
  },
};

export default function ExceptionOverview({
  data,
  activeException,
  onSelectException,
}: Props) {
  const entries = Object.entries(data.exception_type_counts).sort(
    (a, b) => b[1] - a[1]
  );

  const totalExceptions = entries.reduce((sum, [, c]) => sum + c, 0);

  if (totalExceptions === 0) return null;

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">Exceptions Requiring Attention</div>
          <div className="card-subtitle">
            {totalExceptions} exception{totalExceptions !== 1 ? "s" : ""} across{" "}
            {entries.length} type{entries.length !== 1 ? "s" : ""}
          </div>
        </div>
        {activeException && (
          <button
            className="btn btn-ghost"
            onClick={() => onSelectException(null)}
          >
            Clear filter
          </button>
        )}
      </div>
      <div className="exception-grid">
        {entries.map(([type, count]) => {
          const config = EXCEPTION_CONFIG[type] ?? {
            severity: "neutral",
            desc: type,
          };
          return (
            <button
              key={type}
              className={`exception-card${activeException === type ? " active" : ""}`}
              onClick={() =>
                onSelectException(activeException === type ? null : type)
              }
            >
              <div className={`exception-indicator ${config.severity}`} />
              <div className="exception-body">
                <div className="exception-count">{count}</div>
                <div className="exception-type">{formatType(type)}</div>
                <div className="exception-desc">{config.desc}</div>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function formatType(type: string): string {
  return type
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
