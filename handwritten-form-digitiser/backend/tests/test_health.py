"""Tests for health check endpoints."""

from fastapi.testclient import TestClient


def test_health_check_returns_200_and_valid_envelope(client: TestClient):
    """Verify GET /api/health returns HTTP 200 with standard response envelope."""
    response = client.get("/api/health")
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    assert "timestamp" in body

    data = body["data"]
    assert data["status"] == "HEALTHY"
    assert data["version"] == "0.1.0-test"
    assert data["environment"] == "testing"
    assert "DEVANAGARI" in data["supported_scripts"]
    assert data["dependencies"]["api_gateway"] == "ONLINE"


def test_health_check_versioned_endpoint(client: TestClient):
    """Verify GET /api/v1/health functions identically for API versioning compliance."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "HEALTHY"
    assert body["data"]["version"] == "0.1.0-test"
