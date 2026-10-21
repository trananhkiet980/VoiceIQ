"""AI Response Schema contracts.

Every AI adapter must return data conforming to these schemas,
regardless of the underlying model (Ollama, OpenAI, TensorFlow).
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class TopicClassificationContract(BaseModel):
    """3-level topic classification."""

    general: str = Field(description="Level 1: General topic from fixed list")
    specific: str = Field(description="Level 2: Specific sub-topic")
    dynamic_keywords: list[str] = Field(default_factory=list, description="Level 3: Dynamic keywords")


class CallSummaryContract(BaseModel):
    """Structured call summary."""

    issue: str = Field(description="Main issue discussed")
    resolution: str = Field(description="Resolution applied")
    next_steps: str = Field(description="Follow-up actions")


class EntityContract(BaseModel):
    """Named entity extracted by AI."""

    text: str
    label: str


class AiAnalysisResultContract(BaseModel):
    """Standard output schema for post-call AI analysis.

    Every AI adapter MUST return data conforming to this schema.
    """

    sentiment_overall: str = Field(description="Overall sentiment: Positive|Neutral|Negative")
    sentiment_customer: str = Field(default="Neutral")
    sentiment_agent: str = Field(default="Neutral")
    confidence_score: float = Field(ge=0.0, le=1.0, description="Model confidence score")
    topics: TopicClassificationContract
    summary: CallSummaryContract
    entities: list[EntityContract] = Field(default_factory=lambda: [])


class AiMetadataContract(BaseModel):
    """AI inference metadata for observability."""

    model_name: str = ""
    model_version: str = ""
    prompt_version: str = ""
    latency_ms: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    finish_reason: str = ""


class TurnAiAnalysis(BaseModel):
    """AI analysis result for a single dialog turn."""

    sentiment: str = "Neutral"
    intent: str = ""
