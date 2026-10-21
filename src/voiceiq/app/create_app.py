"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI

from voiceiq.bff.transcript.router import router as transcript_router

from .error_handlers import register_error_handlers
from .lifecycle import lifespan
from .middleware import MockGatewayMiddleware
from .settings import get_settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="VoiceIQ",
        version="1.0.0",
        description="One-Shot LLM Pipeline for Call Analytics & Real-time Agent Assist",
        lifespan=lifespan,
    )

    # Middleware (only in local/dev)
    if settings.ENVIRONMENT in ("local", "development"):
        app.add_middleware(MockGatewayMiddleware)

    # Error handlers
    register_error_handlers(app)

    # Routers
    app.include_router(transcript_router)

    # Health endpoints
    @app.get("/health/live")
    async def health_live() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok"}

    @app.get("/health/ready")
    async def health_ready() -> dict[str, str]:  # pyright: ignore[reportUnusedFunction]
        return {"status": "ok"}

    return app
