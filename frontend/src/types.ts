/** TypeScript interfaces for PayTrace API responses.
 *  Mirrors backend/api/schemas.py exactly.
 */

export interface ReconciliationSummary {
  total_groups: number;
  total_payments: number;
  total_settlements: number;
  total_bank_entries: number;
  status_counts: Record<string, number>;
  exception_type_counts: Record<string, number>;
  human_review_required_count: number;
  processing_timestamp: string;
}

export interface ResultSummary {
  group_id: string;
  status: string;
  payment_ids: string[];
  settlement_ids: string[];
  bank_entry_ids: string[];
  match_score: number | null;
  match_method: string | null;
  exception_type: string | null;
  resolution_status: string;
  evidence_summary: string | null;
  human_review_required: boolean;
  evidence_count: number;
}

export interface PaginatedResults {
  results: ResultSummary[];
  total: number;
  filters_applied: Record<string, string>;
}

export interface EvidenceItem {
  signal_id: string;
  source_record_id: string;
  signal_type: string;
  observed_value: string;
  points: number;
}

export interface GroupDetail {
  group_id: string;
  status: string;
  payment_ids: string[];
  settlement_ids: string[];
  bank_entry_ids: string[];
  match_score: number | null;
  match_method: string | null;
  exception_type: string | null;
  resolution_status: string;
  evidence: EvidenceItem[];
  evidence_summary: string | null;
  human_review_required: boolean;
}

export interface ObservedFact {
  claim: string;
  claim_type: string;
  evidence_ids: string[];
}

export interface InvestigationResult {
  investigation_id: string;
  group_id: string;
  exception_type: string;
  summary: string;
  observed_facts: ObservedFact[];
  likely_explanation: string | null;
  unresolved_questions: string[];
  recommended_action: string;
  confidence: number;
  requires_human_review: boolean;
  validation_status: string;
  provider: string;
  model: string;
}
