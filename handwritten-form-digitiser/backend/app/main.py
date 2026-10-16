"""FastAPI application factory and server entrypoint."""

from contextlib import asynccontextmanager
import logging
from typing import AsyncGenerator, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.api.preprocessing import router as preprocessing_router
from app.api.recognition import router as recognition_router
from app.api.segmentation import router as segmentation_router
from app.api.validation import router as validation_router
from app.core.config import Settings, get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import RequestLoggingMiddleware, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan management for startup and shutdown hooks."""
    logger = logging.getLogger("app.main")
    settings: Settings = app.state.settings
    logger.info(
        f"Starting {settings.PROJECT_NAME} v{settings.VERSION} "
        f"[env={settings.ENVIRONMENT}, debug={settings.DEBUG}]"
    )
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}")


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    """Application factory constructing configured FastAPI application."""
    if settings is None:
        settings = get_settings()

    # Initialize structured logging
    setup_logging(level=settings.LOG_LEVEL, log_format=settings.LOG_FORMAT)

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        docs_url=settings.DOCS_URL,
        openapi_url=settings.OPENAPI_URL,
        redoc_url=settings.REDOC_URL,
        lifespan=lifespan,
    )

    # Attach settings to app state for dependency access
    app.state.settings = settings

    # Configure CORS restricted to configured origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Request metrics and sanitized access logging middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Register centralized exception handlers
    register_exception_handlers(app)

    # Mount API routers
    # 1. Mount routers under /api (e.g. GET /api/health, POST /api/preprocess, POST /api/segment, POST /api/recognize, POST /api/validate)
    app.include_router(health_router, prefix="/api")
    app.include_router(preprocessing_router, prefix="/api")
    app.include_router(segmentation_router, prefix="/api")
    app.include_router(recognition_router, prefix="/api")
    app.include_router(validation_router, prefix="/api")

    # 2. Mount routers under versioned prefix (e.g. /api/v1) for API contract compliance
    if settings.API_V1_STR != "/api":
        app.include_router(health_router, prefix=settings.API_V1_STR)
        app.include_router(preprocessing_router, prefix=settings.API_V1_STR)
        app.include_router(segmentation_router, prefix=settings.API_V1_STR)
        app.include_router(recognition_router, prefix=settings.API_V1_STR)
        app.include_router(validation_router, prefix=settings.API_V1_STR)


    return app


# Default ASGI application instance for uvicorn
app = create_app()
