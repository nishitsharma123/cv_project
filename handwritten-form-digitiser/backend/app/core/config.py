"""Centralized application configuration using Pydantic Settings."""

from functools import lru_cache
from typing import List, Literal, Optional, Union
import json

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Project metadata
    PROJECT_NAME: str = Field(
        default="Handwritten Indic-Script Form Digitiser",
        description="Name of the service or application",
    )
    VERSION: str = Field(
        default="0.1.0",
        description="Application semver version",
    )
    API_V1_STR: str = Field(
        default="/api/v1",
        description="Base routing prefix for API version 1",
    )

    # Runtime environment
    ENVIRONMENT: Literal["development", "staging", "production", "testing"] = Field(
        default="development",
        description="Operational environment name",
    )
    DEBUG: bool = Field(
        default=True,
        description="Debug mode toggle (must be False in production)",
    )

    # Interactive API Documentation
    DOCS_URL: Optional[str] = Field(
        default="/docs",
        description="Path for Swagger UI docs (disabled in production by default)",
    )
    OPENAPI_URL: Optional[str] = Field(
        default="/openapi.json",
        description="Path for OpenAPI JSON specification (disabled in production by default)",
    )
    REDOC_URL: Optional[str] = Field(
        default="/redoc",
        description="Path for ReDoc UI documentation (disabled in production by default)",
    )

    # Security & CORS
    ALLOWED_ORIGINS: Union[List[str], str] = Field(
        default=[
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ],
        description="List of allowed CORS origins",
    )

    # Logging
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Global logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
    )
    LOG_FORMAT: Literal["json", "text"] = Field(
        default="text",
        description="Log output formatting style",
    )

    # Upload & Image Constraints
    MAX_UPLOAD_SIZE_MB: int = Field(
        default=15,
        description="Maximum allowed image upload size in megabytes",
    )
    MIN_IMAGE_DIMENSION: int = Field(
        default=100,
        description="Minimum allowed image width and height in pixels",
    )
    MAX_IMAGE_DIMENSION: int = Field(
        default=8000,
        description="Maximum allowed image width and height in pixels (decompression bomb protection)",
    )
    MAX_PREVIEW_DIMENSION: int = Field(
        default=800,
        description="Maximum dimension for downscaled preview representations",
    )
    SUPPORTED_IMAGE_FORMATS: List[str] = Field(
        default=["JPEG", "JPG", "PNG"],
        description="List of supported image file extension formats",
    )

    @field_validator("ALLOWED_ORIGINS", mode="after")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse allowed origins from JSON string, comma-separated string, or list."""
        if isinstance(v, str):
            v_trimmed = v.strip()
            if v_trimmed.startswith("[") and v_trimmed.endswith("]"):
                try:
                    parsed = json.loads(v_trimmed)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [origin.strip() for origin in v_trimmed.split(",") if origin.strip()]
        elif isinstance(v, list):
            return [str(origin).strip() for origin in v if str(origin).strip()]
        return []

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level string."""
        normalized = v.upper().strip()
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if normalized not in allowed:
            raise ValueError(f"Invalid LOG_LEVEL '{v}'. Allowed levels: {', '.join(allowed)}")
        return normalized

    @model_validator(mode="after")
    def validate_production_safeties(self) -> "Settings":
        """Enforce strict production safety policies."""
        if self.ENVIRONMENT == "production":
            if self.DEBUG:
                raise ValueError("DEBUG must be False in production environment.")
            if "*" in self.ALLOWED_ORIGINS:
                raise ValueError("Wildcard '*' in ALLOWED_ORIGINS is prohibited in production.")
            # Automatically disable interactive documentation endpoints in production
            # unless explicitly configured otherwise
            if self.DOCS_URL == "/docs":
                self.DOCS_URL = None
            if self.OPENAPI_URL == "/openapi.json":
                self.OPENAPI_URL = None
            if self.REDOC_URL == "/redoc":
                self.REDOC_URL = None
        return self


@lru_cache()
def get_settings() -> Settings:
    """Retrieve cached application settings instance."""
    return Settings()
