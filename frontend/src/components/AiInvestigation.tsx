/** AI Investigation panel — displays structured investigation result. */

import { useState } from "react";
import type { InvestigationResult } from "../types";
import { fetchInvestigation } from "../api";

interface Props {
  groupId: string;
  status: string;
  exceptionType: string | null;
}

export default function AiInvestigation({ groupId, status, exceptionType }: Props) {
  const [data, setData] = useState<InvestigationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const canInvestigate = !(status === "matched" && !exceptionType);

  const handleInvestigate = async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchInvestigation(groupId);
      setData(result);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Investigation failed");
    } finally {
      setLoading(false);
    }
  };

  if (!canInvestigate) return null;

  return (
    <div className="ai-section">
      {!data && !loading && !error && (
        <button className="ai-investigate-btn" onClick={handleInvestigate}>
          <span className="ai-btn-icon">✦</span>
          Investigate with AI
        </button>
      )}

      {loading && (
        <div className="ai-loading">
          <div className="spinner" />
          <span>Investigating...</span>
        </div>
      )}

      {error && (
        <div className="ai-error">
          <span className="ai-error-icon">⚠</span>
          <span>{error}</span>
          <button className="btn-ghost" onClick={handleInvestigate}>Retry</button>
        </div>
      )}

      {data && <InvestigationBody data={data} />}
    </div>
  );
}

function InvestigationBody({ data }: { data: InvestigationResult }) {
  const confidencePct = Math.round(data.confidence * 100);
  const confidenceColor =
    data.confidence >= 0.7 ? "var(--color-matched)" :
    data.confidence >= 0.4 ? "var(--color-duplicate)" :
    "var(--color-mismatched)";

  return (
    <div className="ai-result">
      <div className="ai-result-header">
        <div className="ai-result-title">
          <span className="ai-result-icon">✦</span>
          AI Investigation
        </div>
        <div className="ai-result-badges">
          {data.validation_status === "fallback" && (
            <span className="badge badge-review">Fallback — No LLM</span>
          )}
          {data.requires_human_review && (
            <span className="badge badge-review">Human Review Required</span>
          )}
        </div>
      </div>

      <div className="ai-section-block">
        <div className="ai-section-label">Summary</div>
        <div className="ai-section-text">{data.summary}</div>
      </div>

      {data.likely_explanation && (
        <div className="ai-section-block">
          <div className="ai-section-label">Likely Root Cause</div>
          <div className="ai-section-text">{data.likely_explanation}</div>
        </div>
      )}

      {data.observed_facts.length > 0 && (
        <div className="ai-section-block">
          <div className="ai-section-label">Supporting Evidence</div>
          <div className="ai-facts">
            {data.observed_facts.map((fact, i) => (
              <div key={i} className="ai-fact">
                <span className={`ai-fact-badge ${fact.claim_type}`}>
                  {fact.claim_type}
                </span>
                <span className="ai-fact-claim">{fact.claim}</span>
                <span className="ai-fact-refs">
                  {fact.evidence_ids.join(", ")}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {data.unresolved_questions.length > 0 && (
        <div className="ai-section-block">
          <div className="ai-section-label">Unresolved Questions</div>
          <ul className="ai-questions">
            {data.unresolved_questions.map((q, i) => (
              <li key={i}>{q}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="ai-section-block">
        <div className="ai-section-label">Recommended Action</div>
        <div className="ai-section-text ai-action">{data.recommended_action}</div>
      </div>

      <div className="ai-meta">
        <div className="ai-confidence">
          <span className="ai-section-label">Confidence</span>
          <div className="ai-confidence-bar">
            <div
              className="ai-confidence-fill"
              style={{ width: `${confidencePct}%`, background: confidenceColor }}
            />
          </div>
          <span className="ai-confidence-value">{confidencePct}%</span>
        </div>
        <div className="ai-provider-info">
          {data.provider}/{data.model}
        </div>
      </div>
    </div>
  );
}
