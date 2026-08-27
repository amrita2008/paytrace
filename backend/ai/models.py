"""AI investigation domain models.

Structured input/output schemas for the AI investigation layer.
No chain-of-thought, no hidden reasoning, no raw LLM responses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


# ---------------------------------------------------------------------------
# Investigation input models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceItem:
    """Simplified evidence for the investigation prompt."""

    signal_id: str
    signal_type: str
    source_record_id: str
    observed_value: str


@dataclass(frozen=True)
class RecordMetadata:
    """Minimal record metadata provided to the AI."""

    record_id: str
    record_type: str  # "payment" | "settlement" | "bank_entry"
    amount_paise: int | None = None
    currency: str | None = None
    timestamp: str | None = None
    status: str | None = None
    order_id: str | None = None
    payment_refs: list[str] | None = None


@dataclass(frozen=True)
class InvestigationInput:
    """What the AI receives about an exception — nothing more."""

    group_id: str
    exception_type: str
    payment_ids: list[str]
    settlement_ids: list[str]
    bank_entry_ids: list[str]
    evidence: list[EvidenceItem]
    evidence_summary: str | None
    relevant_record_metadata: list[RecordMetadata]


# ---------------------------------------------------------------------------
# Investigation output models
# ---------------------------------------------------------------------------


class ClaimType(str, Enum):
    """Classification of each factual claim the AI makes."""

    FACT = "fact"
    INFERENCE = "inference"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ObservedFact:
    """A single factual claim with an evidence citation."""

    claim: str
    claim_type: str  # ClaimType value
    evidence_ids: list[str]  # must reference supplied evidence IDs


@dataclass(frozen=True)
class InvestigationResult:
    """Structured AI investigation output — auditable, no CoT."""

    summary: str
    observed_facts: list[ObservedFact]
    likely_explanation: str | None
    unresolved_questions: list[str]
    recommended_next_action: str
    confidence: float  # 0.0–1.0
    requires_human_review: bool


# ---------------------------------------------------------------------------
# Investigation record (audit storage)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InvestigationRecord:
    """Audit record for an AI investigation — persisted for traceability.

    Never contains: raw LLM response, chain-of-thought, hidden reasoning,
    API keys, secrets, credentials, or unnecessary PII.
    """

    investigation_id: str
    group_id: str
    exception_type: str
    evidence_ids: list[str]
    provider_name: str
    model_name: str
    timestamp: str
    summary: str
    recommendation: str
    confidence: float
    validation_status: str  # "accepted" | "rejected" | "fallback"
    requires_human_review: bool


# ---------------------------------------------------------------------------
# Provider error categories (safe, no raw details)
# ---------------------------------------------------------------------------


class ProviderErrorCategory(str, Enum):
    """Controlled error categories — never expose raw exceptions."""

    UNAVAILABLE = "unavailable"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    MALFORMED_RESPONSE = "malformed_response"
    CONFIGURATION_ERROR = "configuration_error"
    UNKNOWN = "unknown"
