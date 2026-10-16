"""Tests for CORS middleware behavior and origin restrictions."""

from fastapi.testclient import TestClient


def test_cors_preflight_allowed_origin(client: TestClient):
    """Verify OPTIONS preflight request from allowed origin receives CORS response headers."""
    headers = {
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Content-Type",
    }
    response = client.options("/api/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "GET" in response.headers.get("access-control-allow-methods", "")


def test_cors_preflight_disallowed_origin(client: TestClient):
    """Verify OPTIONS preflight request from disallowed origin does not receive CORS approval."""
    headers = {
        "Origin": "http://unauthorized-attacker.com",
        "Access-Control-Request-Method": "GET",
    }
    response = client.options("/api/health", headers=headers)
    # When an origin is rejected by CORSMiddleware, access-control-allow-origin is omitted
    assert response.headers.get("access-control-allow-origin") != "http://unauthorized-attacker.com"


def test_cors_get_allowed_origin(client: TestClient):
    """Verify regular GET request with Origin header receives access-control-allow-origin."""
    response = client.get("/api/health", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_cors_get_disallowed_origin(client: TestClient):
    """Verify regular GET request with disallowed Origin does not receive access-control-allow-origin."""
    response = client.get("/api/health", headers={"Origin": "http://unauthorized-attacker.com"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
