"""Health check and diagnostic endpoints."""

from fastapi import APIRouter, Depends, Request

from app.core.config import Settings, get_settings
from app.schemas.health import HealthData, HealthResponseEnvelope

router = APIRouter(tags=["Health & Diagnostics"])


@router.get(
    "/health",
    response_model=HealthResponseEnvelope,
    summary="Check service health",
    description="Returns the operational status, version, and active environment profile of the service.",
)
async def check_health(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> HealthResponseEnvelope:
    """Return current system health and configuration status."""
    active_settings: Settings = getattr(request.app.state, "settings", None) or settings
    return HealthResponseEnvelope(
        data=HealthData(
            status="HEALTHY",
            version=active_settings.VERSION,
            environment=active_settings.ENVIRONMENT,
            supported_scripts=["DEVANAGARI"],
            dependencies={
                "api_gateway": "ONLINE",
            },
        )
    )

