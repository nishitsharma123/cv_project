"""Pytest fixtures and test application setup."""

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app.core.config import Settings
from app.core.errors import (
    BadRequestException,
    NotFoundException,
    ValidationException,
)
from app.main import create_app


class SampleRequestBody(BaseModel):
    name: str
    amount: float


# Router with diagnostic test endpoints to test exception handling
test_router = APIRouter(prefix="/test", tags=["Testing Diagnostics"])


@test_router.get("/bad-request")
async def trigger_bad_request():
    raise BadRequestException(
        message="Simulated bad request.",
        details=[{"field": "query", "message": "Missing required filter"}],
    )


@test_router.get("/not-found")
async def trigger_not_found():
    raise NotFoundException(message="Simulated item not found.")


@test_router.get("/validation-error")
async def trigger_validation_error():
    raise ValidationException(
        message="Field semantic validation failed.",
        details=[{"field": "amount", "message": "Amount must be greater than zero"}],
    )


@test_router.get("/unhandled-error")
async def trigger_unhandled_error():
    # Deliberate zero division to trigger unhandled exception handler
    _ = 1 / 0


@test_router.post("/validate-body")
async def trigger_body_validation(payload: SampleRequestBody):
    return {"name": payload.name, "amount": payload.amount}


@pytest.fixture
def test_settings() -> Settings:
    """Provide isolated Settings instance for testing."""
    return Settings(
        PROJECT_NAME="Test Handwritten Digitiser",
        VERSION="0.1.0-test",
        ENVIRONMENT="testing",
        DEBUG=True,
        DOCS_URL="/docs",
        OPENAPI_URL="/openapi.json",
        REDOC_URL="/redoc",
        ALLOWED_ORIGINS=["http://localhost:5173", "http://127.0.0.1:5173"],
        LOG_LEVEL="DEBUG",
        LOG_FORMAT="text",
    )


from app.core.config import Settings, get_settings


@pytest.fixture
def app(test_settings: Settings):
    """Provide test FastAPI application with diagnostic routes mounted."""
    application = create_app(test_settings)
    application.dependency_overrides[get_settings] = lambda: test_settings
    application.include_router(test_router)
    return application


@pytest.fixture
def client(app) -> TestClient:
    """Provide synchronous Starlette/HTTPX TestClient."""
    return TestClient(app, raise_server_exceptions=False)
