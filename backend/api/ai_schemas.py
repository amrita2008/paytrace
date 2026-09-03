"""Pydantic response models for the AI investigation API endpoint.

These map from the internal Phase 5 domain models to JSON-serializable
API responses. No duplicate domain logic — just HTTP serialization.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ObservedFactSchema(BaseModel):
    """Single observed fact from the AI investigation."""

    claim: str
    claim_type: str = Field(..., pattern="^(fact|inference|unknown)$")
    evidence_ids: list[str] = Field(..., min_length=1)


class InvestigationResponseSchema(BaseModel):
    """Structured AI investigation result returned to the frontend."""

    investigation_id: str
    group_id: str
    exception_type: str
    summary: str
    observed_facts: list[ObservedFactSchema]
    likely_explanation: str | None = None
    unresolved_questions: list[str] = []
    recommended_action: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    requires_human_review: bool
    validation_status: str = Field(..., pattern="^(accepted|fallback)$")
    provider: str
    model: str
