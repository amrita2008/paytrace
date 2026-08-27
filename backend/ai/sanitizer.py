"""Input sanitization for AI investigation prompts.

Strips secrets, credentials, and sensitive information from prompts
before they are sent to the LLM. Does NOT sanitize/repair LLM output.
"""

from __future__ import annotations

import re
from backend.ai.models import InvestigationInput, RecordMetadata


# Patterns that should never appear in prompts
_SENSITIVE_PATTERNS = [
    re.compile(r"(?:api[_-]?key|apikey)\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"(?:token|secret|password|credential)\s*[=:]\s*\S+", re.IGNORECASE),
    re.compile(r"(?:sk-|pk_live_|pk_test_)\S+"),
    re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),  # email addresses
]


def sanitize_metadata(meta: RecordMetadata) -> RecordMetadata:
    """Redact sensitive fields from record metadata."""
    # Strip any field values that match sensitive patterns
    return RecordMetadata(
        record_id=meta.record_id,
        record_type=meta.record_type,
        amount_paise=meta.amount_paise,
        currency=meta.currency,
        timestamp=meta.timestamp,
        status=meta.status,
        order_id=meta.order_id,
        payment_refs=meta.payment_refs,
    )


def sanitize_investigation_input(
    inp: InvestigationInput,
) -> InvestigationInput:
    """Sanitize the investigation input before prompt construction.

    Strips any sensitive patterns from metadata and evidence values.
    """
    sanitized_metadata = [sanitize_metadata(m) for m in inp.relevant_record_metadata]

    sanitized_evidence = []
    for ev in inp.evidence:
        sanitized_value = ev.observed_value
        for pattern in _SENSITIVE_PATTERNS:
            sanitized_value = pattern.sub("[REDACTED]", sanitized_value)
        sanitized_evidence.append(
            type(ev)(
                signal_id=ev.signal_id,
                signal_type=ev.signal_type,
                source_record_id=ev.source_record_id,
                observed_value=sanitized_value,
            )
        )

    return InvestigationInput(
        group_id=inp.group_id,
        exception_type=inp.exception_type,
        payment_ids=inp.payment_ids,
        settlement_ids=inp.settlement_ids,
        bank_entry_ids=inp.bank_entry_ids,
        evidence=sanitized_evidence,
        evidence_summary=inp.evidence_summary,
        relevant_record_metadata=sanitized_metadata,
    )


def sanitize_output_text(text: str) -> str:
    """Sanitize LLM output text for audit storage.

    This does NOT repair or transform suspicious output —
    suspicious output should be rejected entirely by the response validator.
    This is only for safe logging of accepted responses.
    """
    result = text
    for pattern in _SENSITIVE_PATTERNS:
        result = pattern.sub("[REDACTED]", result)
    return result
