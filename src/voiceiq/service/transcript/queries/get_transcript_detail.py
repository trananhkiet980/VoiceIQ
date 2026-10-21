"""Query Handler: Get Transcript Detail.

1 Query = 1 Handler File (CQRS-lite).
Optimized for fast read - no domain aggregate hydration needed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..ports.transcript_repo_port import ITranscriptRepoPort


@dataclass(frozen=True)
class GetTranscriptDetailQuery:
    """Query for retrieving transcript detail."""

    tenant_id: str
    call_id: str


class GetTranscriptDetailHandler:
    """Handler for transcript detail query.

    Read path: directly returns Read DTO without domain hydration.
    """

    def __init__(self, transcript_repo_port: ITranscriptRepoPort) -> None:
        self._repo = transcript_repo_port

    async def handle(self, query: GetTranscriptDetailQuery) -> dict[str, Any] | None:
        """Execute query and return transcript data."""
        return await self._repo.get_full_call_detail(
            tenant_id=query.tenant_id,
            call_id=query.call_id,
        )
