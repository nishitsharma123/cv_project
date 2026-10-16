"""Health check response models."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.common import SuccessResponse


class HealthData(BaseModel):
    """Payload representing system health and diagnostics."""

    status: str = Field(
        default="HEALTHY",
        description="Overall service operational status",
    )
    version: str = Field(
        ...,
        description="Application semver version",
    )
    environment: str = Field(
        ...,
        description="Active runtime environment name",
    )
    supported_scripts: List[str] = Field(
        default=["DEVANAGARI"],
        description="List of Indic scripts supported by the OCR pipeline",
    )
    dependencies: Optional[Dict[str, str]] = Field(
        default=None,
        description="Status of connected internal subsystems and dependencies",
    )


class HealthResponseEnvelope(SuccessResponse[HealthData]):
    """Standardized response envelope for health checks."""
    pass
