"""Transcript Repository Port - abstract interface for data access."""

from __future__ import annotations

from typing import Any, Protocol


class ITranscriptRepoPort(Protocol):
    """Abstract repository contract for transcript data.

    ALL methods MUST include tenant_id parameter for RLS guard.
    """

    async def create_transcript(
        self,
        tenant_id: str,
        call_id: str,
        transcript_json: list[dict[str, Any]],
        duration_seconds: float,
        word_count: int,
        turn_count: int,
    ) -> str:
        """Create a new transcript record. Returns transcript_id."""
        ...

    async def update_analysis_results(
        self,
        tenant_id: str,
        transcript_id: str,
        *,
        sentiment_overall: str | None = None,
        sentiment_customer: str | None = None,
        sentiment_agent: str | None = None,
        emotion_overall: str | None = None,
        emotion_customer: str | None = None,
        emotion_agent: str | None = None,
        call_analysis: dict[str, Any] | None = None,
        message_analyses: list[dict[str, Any]],
        message_entities: list[dict[str, Any]] | None = None,
        outbox_events: list[dict[str, Any]] | None = None,
        call_score_data: dict[str, Any] | None = None,
        coaching_queue_data: list[dict[str, Any]] | None = None,
    ) -> None:
        """Update transcript and insert analysis into 5 tables within SAME transaction."""
        ...

    async def get_by_call_id(
        self,
        tenant_id: str,
        call_id: str,
    ) -> dict[str, Any] | None:
        """Retrieve transcript by call_id with tenant guard."""
        ...

    async def get_by_id(
        self,
        tenant_id: str,
        transcript_id: str,
    ) -> dict[str, Any] | None:
        """Retrieve transcript by transcript_id with tenant guard."""
        ...

    async def get_active_topics(self, tenant_id: str) -> list[dict[str, Any]]:
        """Get list of active topics for a tenant. Returns dict with id, label, parent_id, metadata."""
        ...

    async def get_active_intents(self, tenant_id: str) -> list[dict[str, Any]]:
        """Get list of active intents for a tenant. Returns dict with id, label, metadata."""
        ...

    async def get_field_extraction_configs(self, tenant_id: str) -> list[dict[str, Any]]:
        """Get all field extraction configurations for a tenant."""
        ...

    async def get_active_keywords(self, tenant_id: str) -> list[str]:
        """Get list of active keywords for a tenant."""
        ...

    async def insert_realtime_message(
        self,
        tenant_id: str,
        call_id: str,
        message_data: dict[str, Any],
        outbox_events: list[dict[str, Any]] | None = None,
    ) -> str:
        """Insert a single real-time message analysis into the DB. Returns message ID."""
        ...

    async def get_message_analyses_by_call_id(
        self,
        tenant_id: str,
        call_id: str,
    ) -> list[dict[str, Any]]:
        """Retrieve all message analyses for a given call_id, ordered by turn_index."""
        ...

    async def get_active_scorecard(self, tenant_id: str) -> dict[str, Any] | None:
        """Get the active scorecard, including its categories, criteria, and bands."""
        ...

    async def get_summary_templates(self, tenant_id: str) -> list[dict[str, Any]]:
        """Get summary templates for dynamic summary generation."""
        ...

    async def get_explorer_calls(
        self,
        tenant_id: str,
        status_filter: str = "all",
    ) -> list[dict[str, Any]]:
        """Get list of calls for explorer UI."""
        ...

    async def get_full_call_detail(
        self,
        tenant_id: str,
        call_id: str,
    ) -> dict[str, Any] | None:
        """Get full call details including transcript, call analysis, message analysis, and score."""
        ...
