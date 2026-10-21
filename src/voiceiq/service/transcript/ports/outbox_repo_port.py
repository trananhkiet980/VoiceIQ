"""Outbox Repository Port - abstract interface for outbox operations."""

from __future__ import annotations

from typing import Any, Protocol


class IOutboxRepoPort(Protocol):
    """Abstract repository contract for the transactional outbox."""

    async def fetch_unpublished_batch(
        self,
        batch_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Fetch unpublished outbox events using FOR UPDATE SKIP LOCKED."""
        ...

    async def mark_published(
        self,
        event_id: str,
    ) -> None:
        """Mark an outbox event as published."""
        ...

    async def mark_failed(
        self,
        event_id: str,
    ) -> None:
        """Mark an outbox event as failed after max attempts."""
        ...

    async def increment_attempts(
        self,
        event_id: str,
    ) -> int:
        """Increment attempt counter and return new value."""
        ...
