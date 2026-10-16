"""Tests for centralized exception handling and uniform error responses."""

from fastapi.testclient import TestClient


def test_not_found_route_returns_404_error_envelope(client: TestClient):
    """Verify unknown route returns structured 404 JSON response."""
    response = client.get("/api/nonexistent-endpoint")
    assert response.status_code == 404

    body = response.json()
    assert body["success"] is False
    assert "timestamp" in body
    assert body["error"]["code"] == "NOT_FOUND"
    assert "Resource not found" in body["error"]["message"] or "Not Found" in body["error"]["message"]


def test_method_not_allowed_returns_405(client: TestClient):
    """Verify invoking unsupported HTTP method returns structured 405 response."""
    response = client.post("/api/health")
    assert response.status_code == 405

    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "METHOD_NOT_ALLOWED"


def test_domain_bad_request_exception(client: TestClient):
    """Verify BadRequestException triggers 400 with details."""
    response = client.get("/test/bad-request")
    assert response.status_code == 400

    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "BAD_REQUEST"
    assert body["error"]["message"] == "Simulated bad request."
    assert len(body["error"]["details"]) == 1
    assert body["error"]["details"][0]["field"] == "query"


def test_domain_not_found_exception(client: TestClient):
    """Verify NotFoundException triggers 404."""
    response = client.get("/test/not-found")
    assert response.status_code == 404

    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"] == "Simulated item not found."


def test_domain_validation_exception(client: TestClient):
    """Verify ValidationException triggers 422 with details."""
    response = client.get("/test/validation-error")
    assert response.status_code == 422

    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["message"] == "Field semantic validation failed."
    assert body["error"]["details"][0]["field"] == "amount"


def test_schema_validation_error_returns_422(client: TestClient):
    """Verify invalid request body returns structured 422 with field locator."""
    # Send empty dictionary when name and amount are required
    response = client.post("/test/validate-body", json={})
    assert response.status_code == 422

    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert len(body["error"]["details"]) > 0

    field_names = [d["field"] for d in body["error"]["details"]]
    assert "name" in field_names
    assert "amount" in field_names


def test_unhandled_exception_returns_500_without_stack_trace_leakage(client: TestClient):
    """Verify unhandled exception returns clean 500 without leaking file paths or tracebacks."""
    response = client.get("/test/unhandled-error")
    assert response.status_code == 500

    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"

    # Confirm message is generic and safe
    assert "An unexpected server error occurred" in body["error"]["message"]

    # Verify no traceback keywords, file extensions, or system paths appear in the response body
    raw_text = response.text
    assert "Traceback" not in raw_text
    assert "ZeroDivisionError" not in raw_text
    assert "conftest.py" not in raw_text
    assert "cv_project" not in raw_text
