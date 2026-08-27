"""AI investigation service.

Orchestrates the investigation pipeline: build prompt → call LLM →
validate response → policy-check → produce InvestigationRecord.

The deterministic reconciliation result is NEVER modified by AI.
AI_REVIEWED means only that the exception was examined by AI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from backend.ai.models import (
    EvidenceItem,
    InvestigationInput,
    InvestigationRecord,
    InvestigationResult,
    ProviderErrorCategory,
    RecordMetadata,
)
from backend.ai.policy_validator import validate_investigation
from backend.ai.prompt_builder import build_investigation_prompt
from backend.ai.provider import LLMProviderInterface
from backend.ai.response_validator import validate_llm_response
from backend.ai.sanitizer import sanitize_investigation_input
from backend.reconciliation.models import (
    MatchEvidence,
    NormalizedPayment,
    NormalizedSettlement,
    NormalizedBankEntry,
    ReconciliationResult,
)


@dataclass(frozen=True)
class InvestigationResponse:
    """Complete response from the investigation service."""

    record: InvestigationRecord
    result: InvestigationResult | None  # None if investigation failed/fell back


class InvestigationService:
    """Orchestrates the AI investigation pipeline.

    The service:
    1. Builds structured input from a ReconciliationResult
    2. Sanitizes the input
    3. Builds a prompt
    4. Calls the LLM provider
    5. Validates the response
    6. Validates against policy
    7. Produces an InvestigationRecord

    Never modifies the ReconciliationResult.
    Never accesses evaluation/.
    Never exposes secrets.
    """

    def __init__(self, provider: LLMProviderInterface) -> None:
        self._provider = provider

    def investigate(
        self,
        result: ReconciliationResult,
        payments: list[NormalizedPayment],
        settlements: list[NormalizedSettlement],
        bank_entries: list[NormalizedBankEntry],
    ) -> InvestigationResponse:
        """Investigate a reconciliation exception.

        Returns an InvestigationResponse containing an InvestigationRecord
        and optionally the validated InvestigationResult.

        The original ReconciliationResult is never modified.
        """
        investigation_id = f"INV-{result.group_id}"

        # Build investigation input from the reconciliation result
        inp = self._build_input(result, payments, settlements, bank_entries)

        # Sanitize input
        sanitized = sanitize_investigation_input(inp)

        # Build prompt
        prompt = build_investigation_prompt(sanitized)

        # Call provider
        provider_response = self._provider.complete(prompt)

        if not provider_response.success:
            return self._fallback(
                investigation_id=investigation_id,
                context=sanitized,
                error_category=provider_response.error_category,
            )

        # Validate response
        validation = validate_llm_response(provider_response.content, sanitized)
        if not validation.is_valid:
            return self._fallback(
                investigation_id=investigation_id,
                context=sanitized,
                error_category=None,
                validation_reason=validation.rejection_reason,
            )

        # Policy validation
        policy = validate_investigation(validation.result, sanitized)
        if not policy.is_valid:
            return self._fallback(
                investigation_id=investigation_id,
                context=sanitized,
                error_category=None,
                validation_reason=policy.rejection_reason,
            )

        # Investigation accepted
        now = datetime.now(timezone.utc).isoformat()
        record = InvestigationRecord(
            investigation_id=investigation_id,
            group_id=result.group_id,
            exception_type=result.exception_type.value if result.exception_type else "none",
            evidence_ids=[ev.signal_id for ev in result.evidence],
            provider_name=self._provider.provider_name,
            model_name=self._provider.model_name,
            timestamp=now,
            summary=validation.result.summary,
            recommendation=validation.result.recommended_next_action,
            confidence=validation.result.confidence,
            validation_status="accepted",
            requires_human_review=validation.result.requires_human_review,
        )

        return InvestigationResponse(record=record, result=validation.result)

    def _build_input(
        self,
        result: ReconciliationResult,
        payments: list[NormalizedPayment],
        settlements: list[NormalizedSettlement],
        bank_entries: list[NormalizedBankEntry],
    ) -> InvestigationInput:
        """Build InvestigationInput from a ReconciliationResult."""
        payment_idx = {p.payment_id: p for p in payments}
        settlement_idx = {s.settlement_id: s for s in settlements}
        bank_idx = {b.bank_entry_id: b for b in bank_entries}

        evidence_items = [
            EvidenceItem(
                signal_id=ev.signal_id,
                signal_type=ev.signal_type.value,
                source_record_id=ev.source_record_id,
                observed_value=ev.observed_value,
            )
            for ev in result.evidence
        ]

        metadata: list[RecordMetadata] = []
        for pid in result.payment_ids:
            p = payment_idx.get(pid)
            if p:
                metadata.append(RecordMetadata(
                    record_id=p.payment_id,
                    record_type="payment",
                    amount_paise=p.amount_paise,
                    currency=p.currency,
                    timestamp=p.timestamp.isoformat(),
                    status=p.status.value,
                    order_id=p.order_id,
                ))
        for sid in result.settlement_ids:
            s = settlement_idx.get(sid)
            if s:
                metadata.append(RecordMetadata(
                    record_id=s.settlement_id,
                    record_type="settlement",
                    amount_paise=s.amount_paise,
                    currency=s.currency,
                    timestamp=s.timestamp.isoformat(),
                    status=s.status.value,
                    payment_refs=s.payment_refs,
                ))
        for bid in result.bank_entry_ids:
            b = bank_idx.get(bid)
            if b:
                metadata.append(RecordMetadata(
                    record_id=b.bank_entry_id,
                    record_type="bank_entry",
                    amount_paise=b.amount_paise,
                    currency=b.currency,
                    timestamp=b.timestamp.isoformat(),
                    status=b.ledger_status.value,
                ))

        return InvestigationInput(
            group_id=result.group_id,
            exception_type=result.exception_type.value if result.exception_type else "none",
            payment_ids=result.payment_ids,
            settlement_ids=result.settlement_ids,
            bank_entry_ids=result.bank_entry_ids,
            evidence=evidence_items,
            evidence_summary=result.evidence_summary,
            relevant_record_metadata=metadata,
        )

    def _fallback(
        self,
        investigation_id: str,
        context: InvestigationInput,
        error_category: ProviderErrorCategory | None = None,
        validation_reason: str | None = None,
    ) -> InvestigationResponse:
        """Produce a safe fallback investigation record.

        Never exposes raw errors, credentials, URLs, paths, or configuration.
        """
        now = datetime.now(timezone.utc).isoformat()

        # Safe error message — no raw details
        if error_category:
            safe_reason = f"provider_error:{error_category.value}"
        elif validation_reason:
            safe_reason = f"validation_rejected:{validation_reason}"
        else:
            safe_reason = "investigation_failed"

        record = InvestigationRecord(
            investigation_id=investigation_id,
            group_id=context.group_id,
            exception_type=context.exception_type,
            evidence_ids=[ev.signal_id for ev in context.evidence],
            provider_name=self._provider.provider_name,
            model_name=self._provider.model_name,
            timestamp=now,
            summary=f"Investigation failed: {safe_reason}",
            recommendation="Manual human review required. AI investigation was unable to produce a valid analysis.",
            confidence=0.0,
            validation_status="fallback",
            requires_human_review=True,
        )

        return InvestigationResponse(record=record, result=None)
