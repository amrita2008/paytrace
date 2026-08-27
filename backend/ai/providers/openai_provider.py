"""OpenAI GPT-4o-mini provider adapter.

Optional — requires the openai package and PAYTRACE_LLM_API_KEY.
Falls back safely if unavailable.
"""

from __future__ import annotations

import os

from backend.ai.models import ProviderErrorCategory
from backend.ai.provider import ProviderResponse


class OpenAIProvider:
    """OpenAI GPT-4o-mini adapter implementing LLMProviderInterface."""

    def __init__(self) -> None:
        self._api_key = os.getenv("PAYTRACE_LLM_API_KEY", "")
        self._model = os.getenv("PAYTRACE_LLM_MODEL", "gpt-4o-mini")

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    def complete(self, prompt: str) -> ProviderResponse:
        """Send prompt to OpenAI API and return structured response.

        Returns failure with safe error category on any error.
        Never raises exceptions or exposes credentials.
        """
        if not self._api_key:
            return ProviderResponse(
                content="",
                success=False,
                error_category=ProviderErrorCategory.CONFIGURATION_ERROR,
            )

        try:
            from openai import OpenAI
        except ImportError:
            return ProviderResponse(
                content="",
                success=False,
                error_category=ProviderErrorCategory.UNAVAILABLE,
            )

        try:
            client = OpenAI(api_key=self._api_key)
            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=500,
            )
            content = response.choices[0].message.content or ""
            return ProviderResponse(content=content, success=True)

        except Exception:
            # Return safe error category — never raw exception details
            return ProviderResponse(
                content="",
                success=False,
                error_category=ProviderErrorCategory.UNKNOWN,
            )
