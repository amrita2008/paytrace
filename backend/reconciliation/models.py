"""Reconciliation domain models.

Enums, normalized record models, match evidence, match candidates,
and reconciliation results. No business logic — pure data contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from backend.models.canonical import (
    BankEntryType,
    BankLedgerStatus,
    PaymentStatus,
    SettlementStatus,
    Source,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MatchStatus(str, Enum):
    """Reconciliation outcome for a group of records."""

    MATCHED = "matched"
    MISMATCHED = "mismatched"
    MISSING = "missing"
    DUPLICATE = "duplicate"
    AMBIGUOUS = "ambiguous"
    UNRESOLVED = "unresolved"


class ExceptionType(str, Enum):
    """Failure classification — matches synthetic data generator exactly."""

    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    TIMING_MISMATCH = "TIMING_MISMATCH"
    DUPLICATE = "DUPLICATE"
    AMBIGUOUS = "AMBIGUOUS"
    MISSING_SETTLEMENT = "MISSING_SETTLEMENT"
    FAILED_OR_REFUNDED = "FAILED_OR_REFUNDED"
    ORPHAN_BANK_ENTRY = "ORPHAN_BANK_ENTRY"


class ResolutionStatus(str, Enum):
    """Exception lifecycle status."""

    OPEN = "open"
    INVESTIGATING = "investigating"
    AI_REVIEWED = "ai_reviewed"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    UNRESOLVED = "unresolved"


class MatchMethod(str, Enum):
    """How a match was found."""

    EXACT_KEY = "exact_key"
    FUZZY = "fuzzy"
    BATCH_SETTLE = "batch_settle"


class SignalType(str, Enum):
    """Controlled signal type for match evidence.

    Extensible — new types can be added without breaking existing code.
    """

    EXACT_IDENTIFIER = "EXACT_IDENTIFIER"
    EXACT_AMOUNT = "EXACT_AMOUNT"
    CURRENCY_MATCH = "CURRENCY_MATCH"
    TIMESTAMP_WITHIN_WINDOW = "TIMESTAMP_WITHIN_WINDOW"
    PAYMENT_REFERENCE = "PAYMENT_REFERENCE"
    BATCH_AMOUNT_MATCH = "BATCH_AMOUNT_MATCH"
    DUPLICATE_IDENTIFIER = "DUPLICATE_IDENTIFIER"
    MISSING_RECORD = "MISSING_RECORD"
    TIMESTAMP_EXCEEDED = "TIMESTAMP_EXCEEDED"


# ---------------------------------------------------------------------------
# Normalized Record Models
# ---------------------------------------------------------------------------


def _require_tz_aware(dt: datetime, field_name: str) -> None:
    """Raise ValueError if datetime is not timezone-aware."""
    if dt.tzinfo is None:
        raise ValueError(f"{field_name} must be timezone-aware, got naive datetime")


@dataclass(frozen=True)
class NormalizedPayment:
    """Normalized payment record for reconciliation.

    Contains only fields required for deterministic matching.
    No PII, no secrets, no raw source data.
    """

    payment_id: str
    order_id: str
    amount_paise: int
    fee_paise: int
    net_amount_paise: int
    currency: str
    status: PaymentStatus
    timestamp: datetime
    gateway_reference: str

    def __post_init__(self) -> None:
        if self.amount_paise <= 0:
            raise ValueError(f"amount_paise must be positive, got {self.amount_paise}")
        _require_tz_aware(self.timestamp, "timestamp")


@dataclass(frozen=True)
class NormalizedSettlement:
    """Normalized settlement record for reconciliation.

    payment_refs may be empty for ambiguous cases where the
    true payment relationship is intentionally unknown.
    """

    settlement_id: str
    amount_paise: int
    fee_paise: int
    net_amount_paise: int
    currency: str
    status: SettlementStatus
    timestamp: datetime
    payment_refs: list[str]
    gateway_settlement_reference: str
    is_known_exception: bool = False

    def __post_init__(self) -> None:
        if self.amount_paise <= 0:
            raise ValueError(f"amount_paise must be positive, got {self.amount_paise}")
        _require_tz_aware(self.timestamp, "timestamp")


@dataclass(frozen=True)
class NormalizedBankEntry:
    """Normalized bank/ledger record for reconciliation."""

    bank_entry_id: str
    amount_paise: int
    currency: str
    entry_type: BankEntryType
    ledger_status: BankLedgerStatus
    timestamp: datetime
    reference: str

    def __post_init__(self) -> None:
        if self.amount_paise <= 0:
            raise ValueError(f"amount_paise must be positive, got {self.amount_paise}")
        _require_tz_aware(self.timestamp, "timestamp")


# ---------------------------------------------------------------------------
# Match Evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MatchEvidence:
    """Structured, auditable evidence for a matching decision.

    Each evidence item represents one deterministic signal that
    contributed to a match score. No chain-of-thought, no hidden
    reasoning, no raw LLM responses.
    """

    signal_id: str
    source_record_id: str
    signal_type: SignalType
    observed_value: str
    points: int


# ---------------------------------------------------------------------------
# Match Candidate
# ---------------------------------------------------------------------------


@dataclass
class MatchCandidate:
    """A possible relationship between two records.

    No LLM dependency. Score is deterministic and bounded 0-100.
    """

    source_record_id: str
    candidate_record_id: str
    candidate_source: Source
    match_score: int
    signals_active: list[MatchEvidence]
    is_definitive: bool
    reason: str


# ---------------------------------------------------------------------------
# Reconciliation Result
# ---------------------------------------------------------------------------


@dataclass
class ReconciliationResult:
    """Result of reconciling a group of records.

    Sufficient for: API responses, database persistence,
    evaluation, and AI investigation — but none of those
    integrations exist in Phase 3A.
    """

    group_id: str
    status: MatchStatus
    payment_ids: list[str]
    settlement_ids: list[str]
    bank_entry_ids: list[str]
    match_score: int | None
    match_method: MatchMethod | None
    exception_type: ExceptionType | None
    resolution_status: ResolutionStatus
    evidence: list[MatchEvidence]
    evidence_summary: str | None
    human_review_required: bool
