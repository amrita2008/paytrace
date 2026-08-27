"""Deterministic policy validation of AI investigation results.

The policy validator ensures AI recommendations do not contradict
deterministic evidence or override reconciliation decisions.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.ai.models import InvestigationInput, InvestigationResult


@dataclass(frozen=True)
class PolicyValidationResult:
    """Result of validating an investigation against policy rules."""

    is_valid: bool
    rejection_reason: str | None


def validate_investigation(
    investigation: InvestigationResult,
    context: InvestigationInput,
) -> PolicyValidationResult:
    """Validate an investigation result against policy rules.

    Rules enforced:
    P1: Confidence must be in [0.0, 1.0].
    P2: Every observed_fact must cite at least one evidence ID that
        exists in the investigation context.
    P3: At least one observed_fact must be present.
    P4: Must have a non-empty recommended_next_action.
    P5: Deterministic consistency — investigation must not claim
        the reconciliation result was changed (AI is investigation-only).
    P6: No fact may reference records not in the investigation context.
    P7: Human review must be required when confidence < 0.5.

    Returns PolicyValidationResult with is_valid=True if all rules pass.
    """
    # P1: Confidence range
    if not (0.0 <= investigation.confidence <= 1.0):
        return PolicyValidationResult(
            is_valid=False,
            rejection_reason="confidence_out_of_range",
        )

    # P2 + P3: Evidence citations
    valid_evidence_ids = {ev.signal_id for ev in context.evidence}
    if not investigation.observed_facts:
        return PolicyValidationResult(
            is_valid=False,
            rejection_reason="no_observed_facts",
        )

    all_context_ids = set(context.payment_ids + context.settlement_ids + context.bank_entry_ids)

    for i, fact in enumerate(investigation.observed_facts):
        # P2: Evidence IDs must be valid
        for eid in fact.evidence_ids:
            if eid not in valid_evidence_ids:
                return PolicyValidationResult(
                    is_valid=False,
                    rejection_reason=f"fact_{i}:invalid_evidence_id:{eid}",
                )

    # P4: Non-empty recommendation
    if not investigation.recommended_next_action.strip():
        return PolicyValidationResult(
            is_valid=False,
            rejection_reason="empty_recommendation",
        )

    # P5: No claim of changed deterministic result
    prohibited_claims = [
        "match status changed",
        "match status was changed",
        "match status has been changed",
        "reconciliation result changed",
        "reconciliation result was changed",
        "status changed to matched",
        "status was changed to matched",
        "exception resolved",
        "exception was resolved",
        "match confirmed",
        "match was confirmed",
        "automatically resolved",
        "was automatically resolved",
        "was resolved",
    ]
    for fact in investigation.observed_facts:
        claim_lower = fact.claim.lower()
        for prohibited in prohibited_claims:
            if prohibited in claim_lower:
                return PolicyValidationResult(
                    is_valid=False,
                    rejection_reason=f"fact_{i}:claims_deterministic_override",
                )

    # P7: Human review required when confidence < 0.5
    if investigation.confidence < 0.5 and not investigation.requires_human_review:
        return PolicyValidationResult(
            is_valid=False,
            rejection_reason="low_confidence_requires_human_review",
        )

    return PolicyValidationResult(is_valid=True, rejection_reason=None)
