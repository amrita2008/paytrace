"""LLM response validation.

Reject-or-accept: never sanitize, repair, or transform suspicious output.
Invalid responses trigger deterministic fallback.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from backend.ai.models import ClaimType, InvestigationInput, InvestigationResult, ObservedFact


# Fields that must never appear in LLM output
_PROHIBITED_FIELDS = {
    "chain_of_thought",
    "chain-of-thought",
    "hidden_reasoning",
    "reasoning_trace",
    "model_thoughts",
    "internal_reasoning",
    "system_prompt",
    "raw_response",
}


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating an LLM response."""

    is_valid: bool
    result: InvestigationResult | None
    rejection_reason: str | None


def validate_llm_response(
    raw_response: str,
    context: InvestigationInput,
) -> ValidationResult:
    """Validate an LLM response against the investigation context.

    Returns ValidationResult with is_valid=True and parsed result
    if the response passes all checks. Otherwise returns is_valid=False
    with a safe rejection reason.

    This function NEVER repairs, sanitizes, or transforms the output.
    Suspicious output is rejected entirely.
    """
    # 1. Parse JSON
    try:
        parsed = json.loads(raw_response)
    except (json.JSONDecodeError, ValueError):
        return ValidationResult(
            is_valid=False,
            result=None,
            rejection_reason="malformed_json",
        )

    if not isinstance(parsed, dict):
        return ValidationResult(
            is_valid=False,
            result=None,
            rejection_reason="not_object",
        )

    # 2. Check for prohibited fields
    for field_name in _PROHIBITED_FIELDS:
        if field_name in parsed:
            return ValidationResult(
                is_valid=False,
                result=None,
                rejection_reason=f"prohibited_field:{field_name}",
            )

    # 3. Validate required fields exist
    required_fields = [
        "summary", "observed_facts", "likely_explanation",
        "unresolved_questions", "recommended_next_action",
        "confidence", "requires_human_review",
    ]
    for field_name in required_fields:
        if field_name not in parsed:
            return ValidationResult(
                is_valid=False,
                result=None,
                rejection_reason=f"missing_field:{field_name}",
            )

    # 4. Validate confidence range
    confidence = parsed.get("confidence")
    if not isinstance(confidence, (int, float)):
        return ValidationResult(
            is_valid=False,
            result=None,
            rejection_reason="invalid_confidence_type",
        )
    if confidence < 0.0 or confidence > 1.0:
        return ValidationResult(
            is_valid=False,
            result=None,
            rejection_reason="invalid_confidence_range",
        )

    # 5. Validate requires_human_review
    if not isinstance(parsed.get("requires_human_review"), bool):
        return ValidationResult(
            is_valid=False,
            result=None,
            rejection_reason="invalid_human_review_type",
        )

    # 6. Validate observed_facts
    raw_facts = parsed.get("observed_facts", [])
    if not isinstance(raw_facts, list):
        return ValidationResult(
            is_valid=False,
            result=None,
            rejection_reason="observed_facts_not_list",
        )

    # Build set of valid evidence IDs from context
    valid_evidence_ids = {ev.signal_id for ev in context.evidence}

    validated_facts: list[ObservedFact] = []
    for i, fact in enumerate(raw_facts):
        if not isinstance(fact, dict):
            return ValidationResult(
                is_valid=False,
                result=None,
                rejection_reason=f"fact_{i}:not_object",
            )

        # Validate claim_type
        claim_type = fact.get("claim_type")
        valid_claim_types = {ct.value for ct in ClaimType}
        if claim_type not in valid_claim_types:
            return ValidationResult(
                is_valid=False,
                result=None,
                rejection_reason=f"fact_{i}:invalid_claim_type",
            )

        # Validate evidence_ids — every claim must reference valid evidence
        evidence_ids = fact.get("evidence_ids", [])
        if not isinstance(evidence_ids, list) or not evidence_ids:
            return ValidationResult(
                is_valid=False,
                result=None,
                rejection_reason=f"fact_{i}:missing_evidence_ids",
            )
        for eid in evidence_ids:
            if eid not in valid_evidence_ids:
                return ValidationResult(
                    is_valid=False,
                    result=None,
                    rejection_reason=f"fact_{i}:invalid_evidence_id:{eid}",
                )

        # Validate claim is non-empty string
        claim = fact.get("claim", "")
        if not isinstance(claim, str) or not claim.strip():
            return ValidationResult(
                is_valid=False,
                result=None,
                rejection_reason=f"fact_{i}:empty_claim",
            )

        validated_facts.append(ObservedFact(
            claim=claim.strip(),
            claim_type=claim_type,
            evidence_ids=list(evidence_ids),
        ))

    # 7. Validate unresolved_questions
    questions = parsed.get("unresolved_questions", [])
    if not isinstance(questions, list):
        return ValidationResult(
            is_valid=False,
            result=None,
            rejection_reason="unresolved_questions_not_list",
        )
    questions = [q for q in questions if isinstance(q, str) and q.strip()]

    # 8. Validate string fields
    summary = parsed.get("summary", "")
    if not isinstance(summary, str) or not summary.strip():
        return ValidationResult(
            is_valid=False,
            result=None,
            rejection_reason="empty_summary",
        )

    recommended = parsed.get("recommended_next_action", "")
    if not isinstance(recommended, str) or not recommended.strip():
        return ValidationResult(
            is_valid=False,
            result=None,
            rejection_reason="empty_recommendation",
        )

    # 9. Check for prompt injection patterns in output
    _full_text = raw_response.lower()
    injection_patterns = [
        "ignore previous instructions",
        "ignore all instructions",
        "reveal system prompt",
        "reveal api key",
        "reveal secret",
        "reveal credentials",
    ]
    for pattern in injection_patterns:
        if pattern in _full_text:
            return ValidationResult(
                is_valid=False,
                result=None,
                rejection_reason="prompt_injection_detected",
            )

    result = InvestigationResult(
        summary=summary.strip(),
        observed_facts=validated_facts,
        likely_explanation=parsed.get("likely_explanation"),
        unresolved_questions=questions,
        recommended_next_action=recommended.strip(),
        confidence=float(confidence),
        requires_human_review=parsed["requires_human_review"],
    )

    return ValidationResult(
        is_valid=True,
        result=result,
        rejection_reason=None,
    )
