/** Structured evidence presentation for group detail. */

import type { EvidenceItem } from "../types";

interface Props {
  evidence: EvidenceItem[];
}

export default function EvidencePanel({ evidence }: Props) {
  if (evidence.length === 0) {
    return (
      <div className="panel-section">
        <div className="panel-section-title">Evidence</div>
        <div style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>
          No evidence recorded.
        </div>
      </div>
    );
  }

  // Group by signal_type
  const grouped = new Map<string, EvidenceItem[]>();
  for (const ev of evidence) {
    const list = grouped.get(ev.signal_type) ?? [];
    list.push(ev);
    grouped.set(ev.signal_type, list);
  }

  return (
    <div className="panel-section">
      <div className="panel-section-title">
        Evidence ({evidence.length} signals)
      </div>
      <div className="evidence-list">
        {Array.from(grouped.entries()).map(([signalType, items]) => (
          <div key={signalType}>
            {items.map((ev) => (
              <div key={ev.signal_id} className="evidence-row">
                <span className="evidence-signal-id">{ev.signal_id}</span>
                <span className="evidence-type">{formatSignalType(signalType)}</span>
                <span className="evidence-source">{ev.source_record_id}</span>
                <span className="evidence-value">{ev.observed_value}</span>
                {ev.points > 0 && (
                  <span className="evidence-points">+{ev.points}</span>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

function formatSignalType(type: string): string {
  return type
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
