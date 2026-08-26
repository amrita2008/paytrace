"""Tests for the /health endpoint.

These tests require:
- No database
- No LLM / API keys
- No Razorpay credentials
- No external network access
- No real user data
"""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_returns_200():
    """Health endpoint returns HTTP 200."""
    response = client.get("/health")
    assert response.status_code == 200


def test_health_returns_json():
    """Health endpoint returns JSON content type."""
    response = client.get("/health")
    content_type = response.headers["content-type"]
    assert content_type.startswith("application/json")


def test_health_status_ok():
    """Health endpoint reports status 'ok'."""
    response = client.get("/health")
    data = response.json()
    assert data["status"] == "ok"


def test_health_includes_service_name():
    """Health endpoint includes the service name."""
    response = client.get("/health")
    data = response.json()
    assert data["service"] == "PayTrace"
    assert isinstance(data["service"], str)


def test_health_includes_version():
    """Health endpoint includes a version string."""
    response = client.get("/health")
    data = response.json()
    assert "version" in data
    assert isinstance(data["version"], str)
    assert len(data["version"]) > 0


def test_health_response_has_no_secrets():
    """Health response must not contain secrets, env vars, or paths."""
    response = client.get("/health")
    text = response.text.lower()
    # Must not expose env var values or sensitive patterns
    assert "api_key" not in text
    assert "token" not in text
    assert "password" not in text
    assert "secret" not in text
    assert "localhost" not in text
    assert "/home" not in text
    assert "/usr" not in text


def test_health_response_fields_are_exact():
    """Health response contains exactly the expected fields (no extras)."""
    response = client.get("/health")
    data = response.json()
    expected_keys = {"status", "service", "version"}
    assert set(data.keys()) == expected_keys
