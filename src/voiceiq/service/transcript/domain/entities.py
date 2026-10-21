"""Domain entities - pure Python dataclasses.

This module MUST NOT import any framework (fastapi, sqlalchemy, pydantic, httpx).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from .value_objects import CallOutcome, SentimentLabel, SentimentTrend


@dataclass
class DialogTurn:
    """A single turn in a call transcript."""

    turn_index: int
    speaker: str  # 'agent' or 'customer'
    text: str
    start_time: float
    end_time: float

    # Analytical fields
    topic_level_1: str | None = None
    topic_level_2: str | None = None
    intent: str | None = None
    sentiment: SentimentLabel | None = None

    # NER Extraction
    extracted_entities: list[dict[str, Any]] | None = None

    # QA Metrics (for Agent)
    qa_compliance: bool | None = None
    qa_objection_handled: bool | None = None
    qa_warning_overpromise: bool | None = None

    ai_analysis: dict[str, object] | None = None


@dataclass
class Transcript:
    """Core transcript entity."""

    transcript_id: str
    tenant_id: str
    call_id: str
    word_count: int = 0
    turn_count: int = 0
    duration_seconds: Decimal = Decimal("0.00")

    # VoiceIQ Aggregated Metrics
    main_topic: str | None = None
    final_intent: CallOutcome | None = None
    sentiment_trend: SentimentTrend | None = None
    qa_compliance_score: float | None = None
    objection_handling_rate: float | None = None
    next_best_actions: list[dict[str, Any]] | None = None

    sentiment_overall: str = "Neutral"
    sentiment_customer: str = "Neutral"
    sentiment_agent: str = "Neutral"
    emotion_overall: str = "normal"
    endcall_status: str = "normal"
    transcript_json: list[dict[str, Any]] = field(default_factory=lambda: [])
    full_text_combined: str = ""
    call_summary: dict[str, str] | None = None
    churn_predictions: dict[str, object] | None = None
    diagnostics: dict[str, object] | None = None
    ai_metadata: dict[str, object] | None = None
    created_at: datetime | None = None
