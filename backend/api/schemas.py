"""Pydantic response models for the PayTrace API.

These models define the JSON response structure for the frontend.
They are thin wrappers — serialization happens in routes.py from
the existing dataclass domain models.
"""

from __future__ import annotations

from pydantic import BaseModel


class ReconciliationSummaryResponse(BaseModel):
    """Aggregate statistics from the reconciliation engine."""

    total_groups: int
    total_payments: int
    total_settlements: int
    total_bank_entries: int
    status_counts: dict[str, int]
    exception_type_counts: dict[str, int]
    human_review_required_count: int
    processing_timestamp: str


class ResultSummary(BaseModel):
    """Summary of a single reconciliation group (list view, no evidence detail)."""

    group_id: str
    status: str
    payment_ids: list[str]
    settlement_ids: list[str]
    bank_entry_ids: list[str]
    match_score: int | None
    match_method: str | None
    exception_type: str | None
    resolution_status: str
    evidence_summary: str | None
    human_review_required: bool
    evidence_count: int


class PaginatedResultsResponse(BaseModel):
    """Paginated list of reconciliation groups."""

    results: list[ResultSummary]
    total: int
    filters_applied: dict[str, str]


class EvidenceResponse(BaseModel):
    """A single structured evidence item."""

    signal_id: str
    source_record_id: str
    signal_type: str
    observed_value: str
    points: int


class GroupDetailResponse(BaseModel):
    """Full detail for a single reconciliation group, including evidence."""

    group_id: str
    status: str
    payment_ids: list[str]
    settlement_ids: list[str]
    bank_entry_ids: list[str]
    match_score: int | None
    match_method: str | None
    exception_type: str | None
    resolution_status: str
    evidence: list[EvidenceResponse]
    evidence_summary: str | None
    human_review_required: bool
