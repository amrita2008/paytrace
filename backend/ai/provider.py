"""Abstract LLM provider interface.

Provider-agnostic contract. Implementations adapter specific providers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from backend.ai.models import ProviderErrorCategory


@dataclass(frozen=True)
class ProviderResponse:
    """Structured response from an LLM provider."""

    content: str
    success: bool
    error_category: ProviderErrorCategory | None = None


class LLMProviderInterface(Protocol):
    """Contract for LLM providers.

    Implementations must not expose credentials, API keys, tokens,
    or internal configuration through any return value.
    """

    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    def complete(self, prompt: str) -> ProviderResponse:
        """Send a prompt and return a structured response.

        On failure, return ProviderResponse with success=False
        and a safe ProviderErrorCategory. Never raise raw exceptions.
        """
        ...
