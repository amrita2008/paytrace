/** Polished group detail slide-out panel with evidence and AI investigation. */

import { useState, useEffect } from "react";
import type { GroupDetail as GroupDetailType } from "../types";
import { fetchGroupDetail } from "../api";
import StatusBadge from "./StatusBadge";
import EvidencePanel from "./EvidencePanel";
import AiInvestigation from "./AiInvestigation";

interface Props {
  groupId: string;
  onClose: () => void;
}

export default function GroupDetail({ groupId, onClose }: Props) {
  const [data, setData] = useState<GroupDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchGroupDetail(groupId)
      .then(setData)
      .catch((e: Error) => setError(e.message))
      .finally(() => setLoading(false));
  }, [groupId]);

  return (
    <div className="panel-overlay" onClick={onClose}>
      <div className="panel" onClick={(e) => e.stopPropagation()}>
        <div className="panel-header">
          <div className="panel-title">
            {loading ? "Loading..." : data?.group_id ?? "Error"}
          </div>
          <button className="panel-close" onClick={onClose}>
            ×
          </button>
        </div>

        <div className="panel-body">
          {loading && (
            <div style={{ display: "flex", justifyContent: "center", padding: "var(--space-8)" }}>
              <div className="spinner" />
            </div>
          )}

          {error && (
            <div className="state-container">
              <div className="state-icon">⚠</div>
              <div className="state-title">Failed to load</div>
              <div className="state-desc">{error}</div>
            </div>
          )}

          {data && <DetailBody data={data} />}
        </div>
      </div>
    </div>
  );
}

function DetailBody({ data }: { data: GroupDetailType }) {
  return (
    <>
      {/* Status badges */}
      <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
        <StatusBadge status={data.status} />
        {data.exception_type && (
          <span className="badge badge-exception">{formatType(data.exception_type)}</span>
        )}
        {data.human_review_required && (
          <span className="badge badge-review">Human Review Required</span>
        )}
      </div>

      {/* Summary */}
      {data.evidence_summary && (
        <div style={{ fontSize: "var(--text-base)", color: "var(--color-text-secondary)", lineHeight: "var(--leading-relaxed)" }}>
          {data.evidence_summary}
        </div>
      )}

      {/* Info */}
      <div className="panel-section">
        <div className="panel-section-title">Reconciliation</div>
        <div className="panel-info-row">
          <span className="panel-info-label">Resolution</span>
          <span className="panel-info-value">{formatType(data.resolution_status)}</span>
        </div>
        {data.match_method && (
          <div className="panel-info-row">
            <span className="panel-info-label">Match Method</span>
            <span className="panel-info-value">{formatType(data.match_method)}</span>
          </div>
        )}
        {data.match_score !== null && (
          <div className="panel-info-row">
            <span className="panel-info-label">Match Score</span>
            <span className="panel-info-value">{data.match_score}</span>
          </div>
        )}
      </div>

      {/* Payments */}
      <div className="panel-section">
        <div className="panel-section-title">
          Payments ({data.payment_ids.length})
        </div>
        <div className="panel-id-list">
          {data.payment_ids.length > 0 ? (
            data.payment_ids.map((id) => (
              <span key={id} className="id-chip">{id}</span>
            ))
          ) : (
            <span style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>None</span>
          )}
        </div>
      </div>

      {/* Settlements */}
      <div className="panel-section">
        <div className="panel-section-title">
          Settlements ({data.settlement_ids.length})
        </div>
        <div className="panel-id-list">
          {data.settlement_ids.length > 0 ? (
            data.settlement_ids.map((id) => (
              <span key={id} className="id-chip">{id}</span>
            ))
          ) : (
            <span style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>None</span>
          )}
        </div>
      </div>

      {/* Bank Entries */}
      <div className="panel-section">
        <div className="panel-section-title">
          Bank Entries ({data.bank_entry_ids.length})
        </div>
        <div className="panel-id-list">
          {data.bank_entry_ids.length > 0 ? (
            data.bank_entry_ids.map((id) => (
              <span key={id} className="id-chip">{id}</span>
            ))
          ) : (
            <span style={{ color: "var(--color-text-muted)", fontSize: "var(--text-sm)" }}>None</span>
          )}
        </div>
      </div>

      {/* Evidence */}
      <EvidencePanel evidence={data.evidence} />

      {/* AI Investigation */}
      <AiInvestigation
        groupId={data.group_id}
        status={data.status}
        exceptionType={data.exception_type}
      />
    </>
  );
}

function formatType(type: string): string {
  return type
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
