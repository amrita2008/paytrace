"""FastAPI APIRouter for PayTrace reconciliation endpoints.

Thin integration layer: API → reconciliation_runner → existing domain models → Pydantic response schemas.
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from fastapi import APIRouter, Query

from backend.api.reconciliation_runner import (
    get_processing_timestamp,
    get_results,
    get_source_counts,
)
from backend.api.schemas import (
    EvidenceResponse,
    GroupDetailResponse,
    PaginatedResultsResponse,
    ReconciliationSummaryResponse,
    ResultSummary,
)
from backend.reconciliation.models import (
    ExceptionType,
    MatchEvidence,
    MatchStatus,
    ReconciliationResult,
)

router = APIRouter(prefix="/api/v1/reconciliation", tags=["reconciliation"])


def _serialize_evidence(e: MatchEvidence) -> dict:
    """Serialize a MatchEvidence dataclass to a dict."""
    return {
        "signal_id": e.signal_id,
        "source_record_id": e.source_record_id,
        "signal_type": e.signal_type.value,
        "observed_value": e.observed_value,
        "points": e.points,
    }


def _serialize_result_brief(r: ReconciliationResult) -> dict:
    """Serialize a ReconciliationResult for list view (no evidence detail)."""
    return {
        "group_id": r.group_id,
        "status": r.status.value,
        "payment_ids": r.payment_ids,
        "settlement_ids": r.settlement_ids,
        "bank_entry_ids": r.bank_entry_ids,
        "match_score": r.match_score,
        "match_method": r.match_method.value if r.match_method else None,
        "exception_type": r.exception_type.value if r.exception_type else None,
        "resolution_status": r.resolution_status.value,
        "evidence_summary": r.evidence_summary,
        "human_review_required": r.human_review_required,
        "evidence_count": len(r.evidence),
    }


def _serialize_result_full(r: ReconciliationResult) -> dict:
    """Serialize a ReconciliationResult for detail view (with evidence)."""
    return {
        "group_id": r.group_id,
        "status": r.status.value,
        "payment_ids": r.payment_ids,
        "settlement_ids": r.settlement_ids,
        "bank_entry_ids": r.bank_entry_ids,
        "match_score": r.match_score,
        "match_method": r.match_method.value if r.match_method else None,
        "exception_type": r.exception_type.value if r.exception_type else None,
        "resolution_status": r.resolution_status.value,
        "evidence": [_serialize_evidence(e) for e in r.evidence],
        "evidence_summary": r.evidence_summary,
        "human_review_required": r.human_review_required,
    }


@router.get("/summary", response_model=ReconciliationSummaryResponse)
def reconciliation_summary() -> ReconciliationSummaryResponse:
    """Aggregate reconciliation statistics."""
    results = get_results()
    pay_count, setl_count, bank_count = get_source_counts()

    status_counts: dict[str, int] = {}
    exception_type_counts: dict[str, int] = {}
    human_review_count = 0

    for r in results:
        sv = r.status.value
        status_counts[sv] = status_counts.get(sv, 0) + 1

        if r.exception_type:
            ev = r.exception_type.value
            exception_type_counts[ev] = exception_type_counts.get(ev, 0) + 1

        if r.human_review_required:
            human_review_count += 1

    return ReconciliationSummaryResponse(
        total_groups=len(results),
        total_payments=pay_count,
        total_settlements=setl_count,
        total_bank_entries=bank_count,
        status_counts=status_counts,
        exception_type_counts=exception_type_counts,
        human_review_required_count=human_review_count,
        processing_timestamp=get_processing_timestamp(),
    )


@router.get("/results", response_model=PaginatedResultsResponse)
def reconciliation_results(
    status: Optional[MatchStatus] = Query(None, description="Filter by match status"),
    exception_type: Optional[ExceptionType] = Query(None, description="Filter by exception type"),
    human_review: Optional[bool] = Query(None, description="Filter by human_review_required"),
) -> PaginatedResultsResponse:
    """List reconciliation groups with optional filters."""
    results = get_results()
    filters_applied: dict[str, str] = {}

    filtered = results
    if status is not None:
        filtered = [r for r in filtered if r.status == status]
        filters_applied["status"] = status.value

    if exception_type is not None:
        filtered = [r for r in filtered if r.exception_type == exception_type]
        filters_applied["exception_type"] = exception_type.value

    if human_review is not None:
        filtered = [r for r in filtered if r.human_review_required == human_review]
        filters_applied["human_review"] = str(human_review).lower()

    return PaginatedResultsResponse(
        results=[_serialize_result_brief(r) for r in filtered],
        total=len(filtered),
        filters_applied=filters_applied,
    )


@router.get("/results/{group_id}", response_model=GroupDetailResponse)
def reconciliation_group_detail(group_id: str) -> GroupDetailResponse:
    """Full detail for a single reconciliation group."""
    results = get_results()

    for r in results:
        if r.group_id == group_id:
            return GroupDetailResponse(**_serialize_result_full(r))

    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail=f"Reconciliation group {group_id} not found")
