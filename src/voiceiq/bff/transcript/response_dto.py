"""Response DTOs (Pydantic v2) for transcript endpoints."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from voiceiq.shared.typing import JsonDict, JsonList


class RealtimeTurnResponse(BaseModel):
    """WebSocket response for real-time sentiment analysis."""

    sentiment: str
    topic_label: str | None = None
    topic_confidence: float | None = None
    intent_label: str | None = None
    intent_confidence: float | None = None
    sentiment_score: float | None = None
    confidence_score: float | None = None
    coaching_signal: str | None = None
    latency_ms: float
    turn_id: int | str | None = None
    speaker: str | None = None
    text_content: str | None = None
    qa_compliance: bool | None = None
    entities: list[dict[str, Any]] | None = None
    outbox_events: list[dict[str, Any]] | None = None


class BaseResponse(BaseModel):
    """Generic API response wrapper."""

    success: bool
    message: str


class TranscriptDetailResponse(BaseModel):
    """Full transcript analysis detail."""

    transcript_id: str
    tenant_id: str
    call_id: str
    word_count: int | None = None
    turn_count: int | None = None
    duration_seconds: float | None = None
    sentiment_overall: str | None = None
    sentiment_customer: str | None = None
    sentiment_agent: str | None = None
    emotion_overall: str | None = None
    endcall_status: str | None = None
    transcript_json: JsonList | None = None
    call_summary: JsonDict | None = None
    diagnostics: JsonDict | None = None
    ai_metadata: JsonDict | None = None
    created_at: str | None = None
