"""Tests for centralized configuration and environment validation."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_default_settings_instantiation():
    """Verify default development configuration loads successfully."""
    settings = Settings()
    assert settings.PROJECT_NAME == "Handwritten Indic-Script Form Digitiser"
    assert settings.ENVIRONMENT == "development"
    assert settings.DEBUG is True
    assert settings.DOCS_URL == "/docs"
    assert len(settings.ALLOWED_ORIGINS) >= 2


def test_allowed_origins_parsing_from_comma_separated_string():
    """Verify ALLOWED_ORIGINS string parses into list of origins."""
    settings = Settings(
        ALLOWED_ORIGINS="http://localhost:3000, https://digitiser.example.com "
    )
    assert settings.ALLOWED_ORIGINS == [
        "http://localhost:3000",
        "https://digitiser.example.com",
    ]


def test_allowed_origins_parsing_from_json_array_string():
    """Verify ALLOWED_ORIGINS JSON string parses into list."""
    settings = Settings(
        ALLOWED_ORIGINS='["http://localhost:3000", "http://localhost:5173"]'
    )
    assert settings.ALLOWED_ORIGINS == [
        "http://localhost:3000",
        "http://localhost:5173",
    ]


def test_invalid_log_level_raises_error():
    """Verify unsupported log level strings are rejected."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(LOG_LEVEL="SUPER_VERBOSE")
    assert "Invalid LOG_LEVEL" in str(exc_info.value)


def test_production_environment_rejects_debug_mode():
    """Verify production profile forbids DEBUG=True."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(ENVIRONMENT="production", DEBUG=True)
    assert "DEBUG must be False in production" in str(exc_info.value)


def test_production_environment_rejects_wildcard_cors():
    """Verify production profile forbids wildcard origin '*'."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(ENVIRONMENT="production", DEBUG=False, ALLOWED_ORIGINS=["*"])
    assert "Wildcard '*' in ALLOWED_ORIGINS is prohibited" in str(exc_info.value)


def test_production_environment_auto_disables_docs():
    """Verify production profile disables interactive documentation paths by default."""
    settings = Settings(
        ENVIRONMENT="production",
        DEBUG=False,
        ALLOWED_ORIGINS=["https://app.example.com"],
    )
    assert settings.DOCS_URL is None
    assert settings.OPENAPI_URL is None
    assert settings.REDOC_URL is None
