"""Tests for the PayTrace API endpoints.

Uses TestClient (already used in test_health.py).
All tests require the synthetic data files to be present.
No real LLM, database, or external API calls.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.reconciliation_runner import clear_cache
from backend.main import app


@pytest.fixture(autouse=True)
def _clear_cache():
    """Reset the reconciliation cache before each test."""
    clear_cache()
    yield
    clear_cache()


client = TestClient(app)


# ---------------------------------------------------------------
# 1: Existing health endpoint unchanged
# ---------------------------------------------------------------

def test_health_still_works():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "PayTrace"


# ---------------------------------------------------------------
# 2-3: Summary endpoint
# ---------------------------------------------------------------

def test_summary_returns_200():
    response = client.get("/api/v1/reconciliation/summary")
    assert response.status_code == 200


def test_summary_structure():
    response = client.get("/api/v1/reconciliation/summary")
    data = response.json()
    # Required fields
    assert "total_groups" in data
    assert "total_payments" in data
    assert "total_settlements" in data
    assert "total_bank_entries" in data
    assert "status_counts" in data
    assert "exception_type_counts" in data
    assert "human_review_required_count" in data
    assert "processing_timestamp" in data
    # Types
    assert isinstance(data["total_groups"], int)
    assert isinstance(data["total_payments"], int)
    assert isinstance(data["total_settlements"], int)
    assert isinstance(data["total_bank_entries"], int)
    assert isinstance(data["status_counts"], dict)
    assert isinstance(data["exception_type_counts"], dict)
    assert isinstance(data["human_review_required_count"], int)
    assert isinstance(data["processing_timestamp"], str)


# ---------------------------------------------------------------
# 4: Summary counts match results endpoint
# ---------------------------------------------------------------

def test_summary_counts_match_results():
    summary = client.get("/api/v1/reconciliation/summary").json()
    results = client.get("/api/v1/reconciliation/results").json()
    assert summary["total_groups"] == results["total"]
    assert summary["total_groups"] == len(results["results"])


# ---------------------------------------------------------------
# 5: Summary has no secrets
# ---------------------------------------------------------------

def test_summary_no_secrets():
    text = client.get("/api/v1/reconciliation/summary").text.lower()
    for term in ["api_key", "token", "password", "secret", "sk-", "/home", "/usr"]:
        assert term not in text, f"Found '{term}' in summary response"


# ---------------------------------------------------------------
# 6: Results endpoint
# ---------------------------------------------------------------

def test_results_returns_200():
    response = client.get("/api/v1/reconciliation/results")
    assert response.status_code == 200


# ---------------------------------------------------------------
# 7: Filter by status
# ---------------------------------------------------------------

def test_results_filter_by_status():
    response = client.get("/api/v1/reconciliation/results?status=matched")
    assert response.status_code == 200
    data = response.json()
    assert data["filters_applied"].get("status") == "matched"
    for r in data["results"]:
        assert r["status"] == "matched"


# ---------------------------------------------------------------
# 8: Filter by exception type
# ---------------------------------------------------------------

def test_results_filter_by_exception_type():
    response = client.get(
        "/api/v1/reconciliation/results?exception_type=MISSING_SETTLEMENT"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filters_applied"].get("exception_type") == "MISSING_SETTLEMENT"
    for r in data["results"]:
        assert r["exception_type"] == "MISSING_SETTLEMENT"


# ---------------------------------------------------------------
# 9: Invalid status returns 422
# ---------------------------------------------------------------

def test_results_invalid_status_returns_422():
    response = client.get("/api/v1/reconciliation/results?status=invalid_status")
    assert response.status_code == 422


# ---------------------------------------------------------------
# 10-11: Group detail
# ---------------------------------------------------------------

def test_group_detail_returns_200():
    # First get a valid group_id
    results = client.get("/api/v1/reconciliation/results").json()
    assert len(results["results"]) > 0
    group_id = results["results"][0]["group_id"]

    response = client.get(f"/api/v1/reconciliation/results/{group_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["group_id"] == group_id
    assert "evidence" in data
    assert isinstance(data["evidence"], list)
    assert len(data["evidence"]) > 0


def test_group_detail_includes_evidence():
    results = client.get("/api/v1/reconciliation/results").json()
    group_id = results["results"][0]["group_id"]
    detail = client.get(f"/api/v1/reconciliation/results/{group_id}").json()

    for ev in detail["evidence"]:
        assert "signal_id" in ev
        assert "source_record_id" in ev
        assert "signal_type" in ev
        assert "observed_value" in ev
        assert "points" in ev


# ---------------------------------------------------------------
# 12: 404 for non-existent group
# ---------------------------------------------------------------

def test_group_detail_404():
    response = client.get("/api/v1/reconciliation/results/GRP-NONEXISTENT")
    assert response.status_code == 404


# ---------------------------------------------------------------
# 13: No chain-of-thought in API response
# ---------------------------------------------------------------

def test_no_cot_in_api_response():
    results = client.get("/api/v1/reconciliation/results").json()
    results_text = str(results).lower()
    for term in ["chain of thought", "hidden_reasoning", "reasoning_trace", "model_thoughts"]:
        assert term not in results_text

    # Check detail view too
    if results["results"]:
        group_id = results["results"][0]["group_id"]
        detail = client.get(f"/api/v1/reconciliation/results/{group_id}").json()
        detail_text = str(detail).lower()
        for term in ["chain of thought", "hidden_reasoning", "reasoning_trace", "model_thoughts"]:
            assert term not in detail_text


# ---------------------------------------------------------------
# 14: No ground truth exposed
# ---------------------------------------------------------------

def test_no_ground_truth_exposed():
    text = client.get("/api/v1/reconciliation/summary").text.lower()
    assert "ground_truth" not in text
    assert "ground truth" not in text

    results = client.get("/api/v1/reconciliation/results").json()
    assert "ground_truth" not in str(results).lower()


# ---------------------------------------------------------------
# 15: Exception type counts in summary sum correctly
# ---------------------------------------------------------------

def test_summary_exception_type_counts():
    summary = client.get("/api/v1/reconciliation/summary").json()
    results = client.get("/api/v1/reconciliation/results").json()

    # Count exceptions from results
    exc_from_results: dict[str, int] = {}
    for r in results["results"]:
        et = r.get("exception_type")
        if et:
            exc_from_results[et] = exc_from_results.get(et, 0) + 1

    assert summary["exception_type_counts"] == exc_from_results
