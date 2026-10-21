"""Request DTOs (Pydantic v2) for transcript endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field

from voiceiq.shared.typing import JsonList


class RealtimeTurnRequest(BaseModel):
    """WebSocket payload for a single dialog turn."""

    call_id: str
    speaker: str = Field(..., pattern="^(agent|customer)$")
    text: str
    start_time: float
    end_time: float
    turn_id: int | str | None = None


class EndCallRequest(BaseModel):
    """POST body for submitting a completed call for analysis."""

    call_id: str
    duration_seconds: float
    transcript_json: JsonList
    dry_run: bool = False

    def to_word_count(self) -> int:
        return sum(len(str(t.get("text", "")).split()) for t in self.transcript_json)

    def to_turn_count(self) -> int:
        return len(self.transcript_json)
