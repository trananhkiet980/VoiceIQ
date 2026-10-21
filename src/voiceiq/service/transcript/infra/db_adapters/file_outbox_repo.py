"""Dummy implementation of IOutboxRepoPort (For PoC without DB)."""

from __future__ import annotations

from typing import Any

from voiceiq.service.transcript.ports.outbox_repo_port import IOutboxRepoPort


class FileOutboxRepo(IOutboxRepoPort):
    """Dummy outbox repository that does nothing.
    Since we write events to a log file in FileTranscriptRepo,
    this class is just to satisfy the DI container interface.
    """

    async def fetch_unpublished_batch(
        self,
        batch_size: int = 100,
    ) -> list[dict[str, Any]]:
        return []

    async def mark_published(
        self,
        event_id: str,
    ) -> None:
        pass

    async def mark_failed(
        self,
        event_id: str,
    ) -> None:
        pass

    async def increment_attempts(
        self,
        event_id: str,
    ) -> int:
        return 1
