"""PayTrace AI investigation layer.

Provider-agnostic AI investigation for reconciliation exceptions.
AI investigates; PayTrace verifies.
"""

from backend.ai.models import (
    ClaimType,
    EvidenceItem,
    InvestigationInput,
    InvestigationRecord,
    InvestigationResult,
    ObservedFact,
    ProviderErrorCategory,
    RecordMetadata,
)
from backend.ai.investigation_service import InvestigationService, InvestigationResponse
from backend.ai.policy_validator import PolicyValidationResult, validate_investigation
from backend.ai.prompt_builder import build_investigation_prompt
from backend.ai.response_validator import ValidationResult, validate_llm_response
from backend.ai.sanitizer import sanitize_investigation_input, sanitize_metadata

__all__ = [
    "ClaimType",
    "EvidenceItem",
    "InvestigationInput",
    "InvestigationRecord",
    "InvestigationResult",
    "InvestigationResponse",
    "InvestigationService",
    "ObservedFact",
    "PolicyValidationResult",
    "ProviderErrorCategory",
    "RecordMetadata",
    "ValidationResult",
    "build_investigation_prompt",
    "sanitize_investigation_input",
    "sanitize_metadata",
    "validate_investigation",
    "validate_llm_response",
]
