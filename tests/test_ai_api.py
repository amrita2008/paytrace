"""Tests for the AI investigation API endpoint.

10 focused tests covering: successful investigation, 404, 400,
provider fallback, schema validation, no CoT, no secrets,
no ground-truth access, result integrity, required fields, fact structure.

All tests use mocked provider — no real LLM calls.
"""

import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from backend.main import app
from backend.ai.models import ProviderErrorCategory
from backend.ai.provider import ProviderResponse


client = TestClient(app)


class FakeProvider:
    def __init__(self, response="", success=True, error_category=None):
        self._response = response
        self._success = success
        self._error_category = error_category

    @property
    def provider_name(self):
        return "fake"

    @property
    def model_name(self):
        return "fake-model"

    def complete(self, prompt):
        return ProviderResponse(
            content=self._response,
            success=self._success,
            error_category=self._error_category,
        )


def _valid_llm_response():
    return json.dumps({
        "summary": "Payment was captured but has no corresponding settlement.",
        "observed_facts": [
            {"claim": "Payment PAY-0019 has no settlement reference.", "claim_type": "fact", "evidence_ids": ["E1"]},
        ],
        "likely_explanation": "The settlement may not have been processed yet.",
        "unresolved_questions": ["Was the batch delayed?"],
        "recommended_next_action": "Check settlement batch logs for the expected date.",
        "confidence": 0.7,
        "requires_human_review": True,
    })


def _patch_provider(provider=None):
    if provider is None:
        provider = FakeProvider(response=_valid_llm_response(), success=True)
    return patch("backend.api.ai_routes._get_provider", return_value=provider)


class TestInvestigationEndpoint:

    def test_successful_investigation(self):
        """Valid investigation returns 200 with correct schema."""
        with _patch_provider():
            resp = client.get("/api/v1/reconciliation/results/GRP-0011/investigate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["investigation_id"] == "INV-GRP-0011"
        assert data["group_id"] == "GRP-0011"
        assert isinstance(data["summary"], str) and len(data["summary"]) > 0
        assert isinstance(data["observed_facts"], list) and len(data["observed_facts"]) > 0
        assert isinstance(data["confidence"], float)
        assert 0.0 <= data["confidence"] <= 1.0
        assert isinstance(data["requires_human_review"], bool)
        assert data["validation_status"] == "accepted"
        assert data["provider"] == "fake"

    def test_nonexistent_group_returns_404(self):
        resp = client.get("/api/v1/reconciliation/results/GRP-NONEXISTENT/investigate")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    def test_matched_group_no_exception_returns_400(self):
        """A matched group with no exception_type must return 400."""
        # Programmatically find a matched group with no exception_type
        all_results = client.get("/api/v1/reconciliation/results").json()["results"]
        matched_no_exc = [
            r for r in all_results
            if r["status"] == "matched" and r["exception_type"] is None
        ]
        assert len(matched_no_exc) > 0, "No matched groups without exception_type in dataset"
        group_id = matched_no_exc[0]["group_id"]

        with _patch_provider():
            resp = client.get(f"/api/v1/reconciliation/results/{group_id}/investigate")
        assert resp.status_code == 400
        assert "no exception" in resp.json()["detail"].lower()

    def test_provider_failure_returns_fallback(self):
        """Provider failure returns 200 with safe fallback record."""
        provider = FakeProvider(
            response="", success=False,
            error_category=ProviderErrorCategory.UNAVAILABLE,
        )
        with _patch_provider(provider):
            resp = client.get("/api/v1/reconciliation/results/GRP-0011/investigate")
        assert resp.status_code == 200
        data = resp.json()
        assert data["validation_status"] == "fallback"
        assert data["requires_human_review"] is True
        assert data["confidence"] == 0.0
        assert len(data["observed_facts"]) == 0

    def test_no_chain_of_thought_in_response(self):
        with _patch_provider():
            resp = client.get("/api/v1/reconciliation/results/GRP-0011/investigate")
        data = resp.json()
        prohibited = [
            "chain_of_thought", "chain-of-thought", "hidden_reasoning",
            "reasoning_trace", "model_thoughts", "internal_reasoning", "raw_response",
        ]
        for field in prohibited:
            assert field not in data, f"Prohibited field '{field}' found"

    def test_no_secrets_in_response(self):
        with _patch_provider():
            resp = client.get("/api/v1/reconciliation/results/GRP-0011/investigate")
        text = json.dumps(resp.json()).lower()
        assert "api_key" not in text
        assert "sk-" not in text
        assert "password" not in text

    def test_no_ground_truth_access(self):
        import backend.api.ai_routes as mod
        source = open(mod.__file__).read()
        assert "from evaluation" not in source
        assert "import evaluation" not in source
        assert "ground_truth" not in source

    def test_investigation_does_not_modify_result(self):
        """AI investigation must NOT modify the deterministic reconciliation result."""
        # Step 1: Capture result BEFORE investigation
        resp_before = client.get("/api/v1/reconciliation/results/GRP-0011")
        assert resp_before.status_code == 200
        result_before = resp_before.json()

        # Step 2: Call investigation
        with _patch_provider():
            resp_inv = client.get("/api/v1/reconciliation/results/GRP-0011/investigate")
        assert resp_inv.status_code == 200

        # Step 3: Capture result AFTER investigation
        resp_after = client.get("/api/v1/reconciliation/results/GRP-0011")
        assert resp_after.status_code == 200
        result_after = resp_after.json()

        # Step 4: Assert every deterministic field is identical
        for field in [
            "group_id", "status", "payment_ids", "settlement_ids",
            "bank_entry_ids", "match_score", "match_method",
            "exception_type", "resolution_status", "evidence_summary",
            "human_review_required", "evidence",
        ]:
            assert result_before[field] == result_after[field], \
                f"Field '{field}' changed after investigation"

    def test_all_required_fields_present(self):
        with _patch_provider():
            resp = client.get("/api/v1/reconciliation/results/GRP-0011/investigate")
        data = resp.json()
        for field in [
            "investigation_id", "group_id", "exception_type", "summary",
            "observed_facts", "likely_explanation", "unresolved_questions",
            "recommended_action", "confidence", "requires_human_review",
            "validation_status", "provider", "model",
        ]:
            assert field in data, f"Missing: {field}"

    def test_observed_facts_have_valid_structure(self):
        with _patch_provider():
            resp = client.get("/api/v1/reconciliation/results/GRP-0011/investigate")
        data = resp.json()
        for i, fact in enumerate(data["observed_facts"]):
            assert "claim" in fact and isinstance(fact["claim"], str) and len(fact["claim"]) > 0
            assert fact["claim_type"] in ("fact", "inference", "unknown")
            assert isinstance(fact["evidence_ids"], list) and len(fact["evidence_ids"]) > 0
