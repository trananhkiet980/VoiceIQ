"""Application lifecycle management (startup/shutdown)."""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .container import Container

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Manage application lifecycle."""
    logger.info("Starting VoiceIQ...")

    # Initialize container (creates DB engine, adapters)
    container = Container()
    await container.init()
    app.state.container = container

    logger.info("Service started successfully.")
    yield

    # Cleanup
    logger.info("Shutting down...")
    await container.shutdown()
    logger.info("Service shutdown complete.")
