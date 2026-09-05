"""Ollama local LLM provider adapter.

Connects to a local Ollama instance via its OpenAI-compatible API.
No API key required. No external network calls.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from backend.ai.models import ProviderErrorCategory
from backend.ai.provider import ProviderResponse


class OllamaProvider:
    """Ollama provider implementing LLMProviderInterface.

    Uses the local Ollama OpenAI-compatible endpoint.
    No API key required. Falls back safely on any error.
    """

    def __init__(self) -> None:
        self._base_url = os.getenv("PAYTRACE_LLM_BASE_URL", "http://127.0.0.1:11434")
        self._model = os.getenv("PAYTRACE_LLM_MODEL", "qwen3:1.7b")

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self._model

    def complete(self, prompt: str) -> ProviderResponse:
        """Send prompt to Ollama API and return structured response.

        Uses the OpenAI-compatible /v1/chat/completions endpoint.
        Returns failure with safe error category on any error.
        Never raises exceptions or exposes internal details.
        """
        url = f"{self._base_url}/v1/chat/completions"
        payload = json.dumps({
        "model": self._model,
        "messages": [
        {"role": "system", "content": prompt},
         ],
        "temperature": 0.0,
        "max_tokens": 500,
        "think": False,
        }).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                content = body["choices"][0]["message"]["content"] or ""
                return ProviderResponse(content=content, success=True)
        except urllib.error.URLError:
            return ProviderResponse(
                content="",
                success=False,
                error_category=ProviderErrorCategory.UNAVAILABLE,
            )
        except TimeoutError:
            return ProviderResponse(
                content="",
                success=False,
                error_category=ProviderErrorCategory.TIMEOUT,
            )
        except Exception:
            return ProviderResponse(
                content="",
                success=False,
                error_category=ProviderErrorCategory.UNKNOWN,
            )
