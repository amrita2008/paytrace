"""Tests for Ollama provider and provider selection.

All tests mock HTTP/network calls -- no real LLM or Ollama required.
"""

from __future__ import annotations

import json
import os
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from backend.ai.models import ProviderErrorCategory
from backend.ai.provider import ProviderResponse


def _get_provider():
    from backend.api.ai_routes import _get_provider as gp

    return gp()


class TestOllamaProviderInterface:
    def test_provider_name(self):
        from backend.ai.providers.ollama_provider import OllamaProvider

        p = OllamaProvider()
        assert p.provider_name == "ollama"

    def test_model_name_default(self):
        from backend.ai.providers.ollama_provider import OllamaProvider

        p = OllamaProvider()
        assert p.model_name == "qwen3:1.7b"

    def test_model_name_from_env(self):
        from backend.ai.providers.ollama_provider import OllamaProvider

        with patch.dict(os.environ, {"PAYTRACE_LLM_MODEL": "llama3"}):
            p = OllamaProvider()
            assert p.model_name == "llama3"

    def test_base_url_from_env(self):
        from backend.ai.providers.ollama_provider import OllamaProvider

        with patch.dict(
            os.environ,
            {"PAYTRACE_LLM_BASE_URL": "http://localhost:9999"},
        ):
            p = OllamaProvider()
            assert p._base_url == "http://localhost:9999"

    def test_has_complete_method(self):
        from backend.ai.providers.ollama_provider import OllamaProvider

        assert hasattr(OllamaProvider, "complete")


class TestOllamaSuccess:
    def test_successful_complete(self):
        from backend.ai.providers.ollama_provider import OllamaProvider

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": "Payment has no settlement."
                        }
                    }
                ]
            }
        ).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch(
            "backend.ai.providers.ollama_provider.urllib.request.urlopen",
            return_value=mock_response,
        ):
            p = OllamaProvider()
            result = p.complete("test prompt")

        assert result.success is True
        assert result.content == "Payment has no settlement."
        assert result.error_category is None

    def test_empty_content_returns_empty_string(self):
        from backend.ai.providers.ollama_provider import OllamaProvider

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": ""
                        }
                    }
                ]
            }
        ).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch(
            "backend.ai.providers.ollama_provider.urllib.request.urlopen",
            return_value=mock_response,
        ):
            p = OllamaProvider()
            result = p.complete("test prompt")

        assert result.success is True
        assert result.content == ""

    def test_none_content_returns_empty_string(self):
        from backend.ai.providers.ollama_provider import OllamaProvider

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": None
                        }
                    }
                ]
            }
        ).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch(
            "backend.ai.providers.ollama_provider.urllib.request.urlopen",
            return_value=mock_response,
        ):
            p = OllamaProvider()
            result = p.complete("test prompt")

        assert result.success is True
        assert result.content == ""


class TestOllamaErrorFallback:
    def test_unavailable_returns_error(self):
        from backend.ai.providers.ollama_provider import OllamaProvider

        with patch(
            "backend.ai.providers.ollama_provider.urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            p = OllamaProvider()
            result = p.complete("test prompt")

        assert result.success is False
        assert result.error_category == ProviderErrorCategory.UNAVAILABLE

    def test_timeout_returns_error(self):
        from backend.ai.providers.ollama_provider import OllamaProvider

        with patch(
            "backend.ai.providers.ollama_provider.urllib.request.urlopen",
            side_effect=TimeoutError("timed out"),
        ):
            p = OllamaProvider()
            result = p.complete("test prompt")

        assert result.success is False
        assert result.error_category == ProviderErrorCategory.TIMEOUT

    def test_generic_exception_returns_unknown(self):
        from backend.ai.providers.ollama_provider import OllamaProvider

        with patch(
            "backend.ai.providers.ollama_provider.urllib.request.urlopen",
            side_effect=ValueError("bad response"),
        ):
            p = OllamaProvider()
            result = p.complete("test prompt")

        assert result.success is False
        assert result.error_category == ProviderErrorCategory.UNKNOWN


class TestOllamaMalformedResponse:
    def test_invalid_json_returns_unknown(self):
        from backend.ai.providers.ollama_provider import OllamaProvider

        mock_response = MagicMock()
        mock_response.read.return_value = b"not json"
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch(
            "backend.ai.providers.ollama_provider.urllib.request.urlopen",
            return_value=mock_response,
        ):
            p = OllamaProvider()
            result = p.complete("test prompt")

        assert result.success is False
        assert result.error_category == ProviderErrorCategory.UNKNOWN

    def test_missing_choices_returns_unknown(self):
        from backend.ai.providers.ollama_provider import OllamaProvider

        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps(
            {"no_choices_here": True}
        ).encode("utf-8")
        mock_response.__enter__ = lambda s: s
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch(
            "backend.ai.providers.ollama_provider.urllib.request.urlopen",
            return_value=mock_response,
        ):
            p = OllamaProvider()
            result = p.complete("test prompt")

        assert result.success is False
        assert result.error_category == ProviderErrorCategory.UNKNOWN


class TestProviderSelection:
    def test_ollama_selected_when_env_set(self):
        with patch.dict(
            os.environ,
            {"PAYTRACE_LLM_PROVIDER": "ollama"},
        ):
            provider = _get_provider()

        from backend.ai.providers.ollama_provider import OllamaProvider

        assert isinstance(provider, OllamaProvider)

    def test_ollama_case_insensitive(self):
        with patch.dict(
            os.environ,
            {"PAYTRACE_LLM_PROVIDER": "OLLAMA"},
        ):
            provider = _get_provider()

        from backend.ai.providers.ollama_provider import OllamaProvider

        assert isinstance(provider, OllamaProvider)

    def test_openai_selected_when_env_set_with_key(self):
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in (
                "PAYTRACE_LLM_PROVIDER",
                "PAYTRACE_LLM_API_KEY",
            )
        }

        env["PAYTRACE_LLM_PROVIDER"] = "openai"
        env["PAYTRACE_LLM_API_KEY"] = "sk-test"

        with patch.dict(os.environ, env, clear=True):
            provider = _get_provider()

        from backend.ai.providers.openai_provider import OpenAIProvider

        assert isinstance(provider, OpenAIProvider)

    def test_ollama_selected_when_no_provider_configured(self):
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in (
                "PAYTRACE_LLM_PROVIDER",
                "PAYTRACE_LLM_API_KEY",
            )
        }

        with patch.dict(os.environ, env, clear=True):
            provider = _get_provider()

        from backend.ai.providers.ollama_provider import OllamaProvider

        assert isinstance(provider, OllamaProvider)

    def test_openai_explicit_without_key_still_returns_openai_provider(self):
        env = {
            k: v
            for k, v in os.environ.items()
            if k not in (
                "PAYTRACE_LLM_PROVIDER",
                "PAYTRACE_LLM_API_KEY",
            )
        }

        env["PAYTRACE_LLM_PROVIDER"] = "openai"

        with patch.dict(os.environ, env, clear=True):
            provider = _get_provider()

        from backend.ai.providers.openai_provider import OpenAIProvider

        assert isinstance(provider, OpenAIProvider)

        # OpenAIProvider handles missing API key gracefully via fallback.
        result = provider.complete("test")
        assert result.success is False


class TestOllamaEndToEnd:
    def test_ollama_provider_works_with_investigation_service(self):
        from datetime import datetime, timezone

        from backend.ai.investigation_service import InvestigationService
        from backend.ai.providers.ollama_provider import OllamaProvider
        from backend.models.canonical import PaymentStatus
        from backend.reconciliation.models import (
            ExceptionType,
            MatchEvidence,
            MatchStatus,
            NormalizedPayment,
            ReconciliationResult,
            ResolutionStatus,
            SignalType,
        )

        valid_response = json.dumps(
            {
                "summary": "Payment has no corresponding settlement.",
                "observed_facts": [
                    {
                        "claim": "PAY-TEST has no settlement.",
                        "claim_type": "fact",
                        "evidence_ids": ["E1"],
                    }
                ],
                "likely_explanation": "Settlement may be delayed.",
                "unresolved_questions": [],
                "recommended_next_action": "Check settlement batch logs.",
                "confidence": 0.7,
                "requires_human_review": True,
            }
        )

        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "content": valid_response
                        }
                    }
                ]
            }
        ).encode("utf-8")
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)

        with patch(
            "backend.ai.providers.ollama_provider.urllib.request.urlopen",
            return_value=mock_resp,
        ):
            provider = OllamaProvider()
            service = InvestigationService(provider)

            result = ReconciliationResult(
                group_id="GRP-OLLAMA",
                status=MatchStatus.MISMATCHED,
                payment_ids=["PAY-TEST"],
                settlement_ids=[],
                bank_entry_ids=[],
                match_score=None,
                match_method=None,
                exception_type=ExceptionType.MISSING_SETTLEMENT,
                resolution_status=ResolutionStatus.OPEN,
                evidence=[
                    MatchEvidence(
                        "E1",
                        "PAY-TEST",
                        SignalType.MISSING_RECORD,
                        "no_settlement",
                        0,
                    )
                ],
                evidence_summary="Payment has no settlement.",
                human_review_required=True,
            )

            payments = [
                NormalizedPayment(
                    payment_id="PAY-TEST",
                    order_id="ORD-TEST",
                    amount_paise=1000,
                    fee_paise=0,
                    net_amount_paise=1000,
                    currency="INR",
                    status=PaymentStatus.CAPTURED,
                    timestamp=datetime(
                        2026,
                        8,
                        20,
                        10,
                        0,
                        0,
                        tzinfo=timezone.utc,
                    ),
                    gateway_reference="GW-TEST",
                )
            ]

            response = service.investigate(
                result,
                payments,
                [],
                [],
            )

        assert response.record.validation_status == "accepted"
        assert response.record.provider_name == "ollama"
        assert response.record.model_name == "qwen3:1.7b"
        assert response.result is not None
        assert response.record.group_id == "GRP-OLLAMA"

    def test_ollama_failure_gives_fallback(self):
        from datetime import datetime, timezone

        from backend.ai.investigation_service import InvestigationService
        from backend.ai.providers.ollama_provider import OllamaProvider
        from backend.models.canonical import PaymentStatus
        from backend.reconciliation.models import (
            ExceptionType,
            MatchEvidence,
            MatchStatus,
            NormalizedPayment,
            ReconciliationResult,
            ResolutionStatus,
            SignalType,
        )

        with patch(
            "backend.ai.providers.ollama_provider.urllib.request.urlopen",
            side_effect=urllib.error.URLError("Connection refused"),
        ):
            provider = OllamaProvider()
            service = InvestigationService(provider)

            result = ReconciliationResult(
                group_id="GRP-OLLAMA-FAIL",
                status=MatchStatus.MISMATCHED,
                payment_ids=["PAY-TEST"],
                settlement_ids=[],
                bank_entry_ids=[],
                match_score=None,
                match_method=None,
                exception_type=ExceptionType.MISSING_SETTLEMENT,
                resolution_status=ResolutionStatus.OPEN,
                evidence=[
                    MatchEvidence(
                        "E1",
                        "PAY-TEST",
                        SignalType.MISSING_RECORD,
                        "no_settlement",
                        0,
                    )
                ],
                evidence_summary="Payment has no settlement.",
                human_review_required=True,
            )

            payments = [
                NormalizedPayment(
                    payment_id="PAY-TEST",
                    order_id="ORD-TEST",
                    amount_paise=1000,
                    fee_paise=0,
                    net_amount_paise=1000,
                    currency="INR",
                    status=PaymentStatus.CAPTURED,
                    timestamp=datetime(
                        2026,
                        8,
                        20,
                        10,
                        0,
                        0,
                        tzinfo=timezone.utc,
                    ),
                    gateway_reference="GW-TEST",
                )
            ]

            response = service.investigate(
                result,
                payments,
                [],
                [],
            )

        assert response.record.validation_status == "fallback"
        assert response.record.requires_human_review is True
        assert response.result is None
        assert response.record.provider_name == "ollama"
        assert "unavailable" in response.record.summary.lower()