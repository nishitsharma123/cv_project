"""Tests for API documentation endpoints (/docs, /openapi.json)."""

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


def test_docs_page_available_in_development(client: TestClient):
    """Verify /docs Swagger UI is accessible in non-production environments."""
    response = client.get("/docs")
    assert response.status_code == 200
    assert "swagger-ui" in response.text.lower() or "html" in response.headers.get("content-type", "")


def test_openapi_json_available_in_development(client: TestClient):
    """Verify /openapi.json specification is valid and contains registered routes."""
    response = client.get("/openapi.json")
    assert response.status_code == 200

    spec = response.json()
    assert spec["info"]["title"] == "Test Handwritten Digitiser"
    assert "/api/health" in spec["paths"]


def test_docs_suppressed_in_production():
    """Verify /docs returns 404 when environment is production."""
    prod_settings = Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        ALLOWED_ORIGINS=["https://app.example.com"],
    )
    prod_app = create_app(prod_settings)
    prod_client = TestClient(prod_app, raise_server_exceptions=False)

    response = prod_client.get("/docs")
    assert response.status_code == 404

    openapi_response = prod_client.get("/openapi.json")
    assert openapi_response.status_code == 404
