"""FastAPI router for AI investigation endpoint.

Reuses the existing Phase 5 InvestigationService and provider architecture.
Never modifies the deterministic reconciliation result.
Never accesses evaluation/.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from backend.api.ai_schemas import InvestigationResponseSchema, ObservedFactSchema
from backend.api.reconciliation_runner import get_normalized_data, get_results

router = APIRouter(prefix="/api/v1/reconciliation", tags=["ai-investigation"])


def _get_provider():
    """Get LLM provider.

    Ollama is the default local provider.
    OpenAI can still be selected explicitly with PAYTRACE_LLM_PROVIDER=openai.
    """

    provider_name = os.getenv("PAYTRACE_LLM_PROVIDER", "").lower().strip()

    if provider_name == "openai":
        from backend.ai.providers.openai_provider import OpenAIProvider
        return OpenAIProvider()

    # Ollama is the default for PayTrace.
    from backend.ai.providers.ollama_provider import OllamaProvider
    return OllamaProvider()


@router.get(
    "/results/{group_id}/investigate",
    response_model=InvestigationResponseSchema,
)
def investigate_group(group_id: str) -> InvestigationResponseSchema:
    """Investigate a reconciliation exception using AI.

    Returns structured investigation result. On provider failure,
    returns a fallback record with validation_status="fallback".
    """
    results = get_results()

    # 1. Find group
    target = None
    for r in results:
        if r.group_id == group_id:
            target = r
            break

    if target is None:
        raise HTTPException(
            status_code=404,
            detail=f"Group {group_id} not found",
        )

    # 2. Must have an exception to investigate
    from backend.reconciliation.models import MatchStatus

    if target.status == MatchStatus.MATCHED and target.exception_type is None:
        raise HTTPException(
            status_code=400,
            detail="No exception to investigate -- this group is matched with no exceptions.",
        )

    # 3. Get normalized records and run investigation
    payments, settlements, banks = get_normalized_data()

    from backend.ai.investigation_service import InvestigationService

    service = InvestigationService(_get_provider())
    response = service.investigate(
        target,
        payments,
        settlements,
        banks,
    )

    # 4. Serialize using API schema
    result = response.result

    return InvestigationResponseSchema(
        investigation_id=response.record.investigation_id,
        group_id=response.record.group_id,
        exception_type=response.record.exception_type,
        summary=response.record.summary,
        observed_facts=[
            ObservedFactSchema(
                claim=f.claim,
                claim_type=f.claim_type,
                evidence_ids=f.evidence_ids,
            )
            for f in (result.observed_facts if result else [])
        ],
        likely_explanation=(
            result.likely_explanation if result else None
        ),
        unresolved_questions=(
            result.unresolved_questions if result else []
        ),
        recommended_action=response.record.recommendation,
        confidence=response.record.confidence,
        requires_human_review=response.record.requires_human_review,
        validation_status=response.record.validation_status,
        provider=response.record.provider_name,
        model=response.record.model_name,
    )
