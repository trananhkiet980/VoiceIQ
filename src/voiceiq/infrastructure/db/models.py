"""SQLAlchemy ORM models.

These models are ONLY used in the infrastructure layer.
Domain layer must NOT import this module.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class TranscriptModel(Base):
    """ORM model for the transcripts table."""

    __tablename__ = "transcripts"

    transcript_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Telephony metadata (mock)
    model_primary: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_fallback_used: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    wer_estimate: Mapped[float | None] = mapped_column(Float, nullable=True)

    word_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    turn_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    duration_minutes_charge: Mapped[int | None] = mapped_column(Integer, nullable=True)

    agent_talk_percentage: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    customer_talk_percentage: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    silence_percentage: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    overlap_percentage: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    # Sentiment & status (from older implementation, kept for compatibility if needed)
    sentiment_overall: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sentiment_customer: Mapped[str | None] = mapped_column(String(20), nullable=True)
    sentiment_agent: Mapped[str | None] = mapped_column(String(20), nullable=True)
    emotion_customer: Mapped[str | None] = mapped_column(String(30), nullable=True)
    emotion_agent: Mapped[str | None] = mapped_column(String(30), nullable=True)
    emotion_overall: Mapped[str | None] = mapped_column(String(30), nullable=True)
    endcall_status: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Content
    transcript_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    full_text_combined: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Diagnostics (kept for arbitrary flexible storage)
    diagnostics: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    # Acoustic & Demographics
    diarization_quality: Mapped[str | None] = mapped_column(String(20), nullable=True)
    avg_volume_db: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    max_volume_db: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    agent_speech_rate_wpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    customer_speech_rate_wpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    overlap_total_seconds: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    interrupt_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    silence_total_seconds: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    silence_max_duration_seconds: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    silence_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gender_agent: Mapped[str | None] = mapped_column(String(20), nullable=True)
    age_range_customer: Mapped[str | None] = mapped_column(String(20), nullable=True)
    region_customer: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        UniqueConstraint("call_id", name="uq_transcripts_call_id"),
        Index("ux_transcripts_tenant_id", "tenant_id", "transcript_id", unique=True),
        Index("idx_transcripts_created_at", "tenant_id", created_at.desc()),
    )


class CallAnalysisModel(Base):
    """Per-call NLP analysis."""

    __tablename__ = "call_analysis"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)

    topics: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    intents: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)

    escalation_level: Mapped[str] = mapped_column(String(20), nullable=False, server_default=text("'none'"))
    escalation_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    escalation_signals: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    escalation_peak_timestamp: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    escalation_trajectory: Mapped[str | None] = mapped_column(String(20), nullable=True)
    escalation_de_escalation_successful: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    escalation_detected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    toxicity_agent_score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    toxicity_customer_score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    toxicity_triggered_auto_fail: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True, server_default=text("false")
    )
    toxicity_tags: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    intent_transitions: Mapped[list[dict[str, Any]] | None] = mapped_column(JSONB, nullable=True)
    script_compliance: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_bullets: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    extracted_fields: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    summary_model: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pipeline_version: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text("NOW()"))

    __table_args__ = (Index("idx_call_analysis_tenant_call", "tenant_id", "call_id"),)


class MessageAnalysisModel(Base):
    """Per-turn NLP analysis."""

    __tablename__ = "message_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(String(20), nullable=False)
    start_time: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)
    end_time: Mapped[float | None] = mapped_column(Numeric(8, 2), nullable=True)

    text_content: Mapped[str] = mapped_column(Text, nullable=False)
    text_corrected: Mapped[str | None] = mapped_column(Text)
    llm_correction_rejected: Mapped[bool] = mapped_column(Boolean, default=False)

    intent_label: Mapped[str | None] = mapped_column(String(100))
    intent_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    topic_label: Mapped[str | None] = mapped_column(String(200))
    topic_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3))
    sentiment: Mapped[str | None] = mapped_column(String(20))
    sentiment_score: Mapped[float | None] = mapped_column(Numeric(4, 3))
    urgency: Mapped[str | None] = mapped_column(String(20), nullable=True)
    emotion: Mapped[str | None] = mapped_column(String(30), nullable=True)
    toxicity_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    volume_db: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    is_high_volume: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    speech_rate_wpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_overlap: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    overlap_duration_seconds: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    silence_before_seconds: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)

    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    turn_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    has_forbidden: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    detection_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    __table_args__ = (
        Index("idx_message_analyses_call", "tenant_id", "call_id"),
        Index("idx_message_analyses_created_at", "created_at"),
    )


class MessageEntityModel(Base):
    """NER PII extracted per turn."""

    __tablename__ = "message_entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_value: Mapped[str] = mapped_column(Text, nullable=False)
    entity_masked: Mapped[str | None] = mapped_column(Text, nullable=True)

    is_pii: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    start_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_offset: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    __table_args__ = (Index("idx_message_entities_message", "message_id"),)


class MessageKeywordHitModel(Base):
    """Keyword matches."""

    __tablename__ = "message_keyword_hits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    keyword_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    keyword_type: Mapped[str] = mapped_column(String(50), nullable=False)
    matched_text: Mapped[str] = mapped_column(Text, nullable=False)
    context_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )

    __table_args__ = (Index("idx_keyword_hits_message", "message_id"),)


class TopicRegistryModel(Base):
    """Taxonomy topic registry."""

    __tablename__ = "topic_registry"

    topic_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    label_vi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description_nli: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent_topic_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    hierarchy_path: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    hierarchy_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    examples: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class IntentTaxonomyModel(Base):
    """Taxonomy intent registry."""

    __tablename__ = "intent_taxonomy"

    intent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name_vi: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description_nli: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry_template: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detection_rules: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    examples: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )


class FieldExtractionConfigModel(Base):
    """NER field extraction configs."""

    __tablename__ = "field_extraction_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    display_name_vi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    field_type: Mapped[str] = mapped_column(String(50), nullable=False)
    is_pii: Mapped[bool] = mapped_column(Boolean, default=False)
    pii_mask_pattern: Mapped[str | None] = mapped_column(String(50), nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(50), nullable=False)
    extraction_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_visible: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class KeywordRegistryModel(Base):
    """Keyword registry."""

    __tablename__ = "keyword_registry"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    keyword: Mapped[str] = mapped_column(String(200), nullable=False)
    keyword_type: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")


class EventOutboxModel(Base):
    """Transactional Outbox for events (Debezium/CDC)."""

    __tablename__ = "event_outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(50), nullable=False)
    aggregate_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    event_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    correlation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CallTopicModel(Base):
    """Topics detected in a call."""

    __tablename__ = "call_topics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    topic_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    classification_uncertain: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class CallIntentModel(Base):
    """Intents detected in a call."""

    __tablename__ = "call_intents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    intent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    is_oos: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    detected_at_stage: Mapped[int | None] = mapped_column(Integer, nullable=True)
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)


class ConversationSummaryModel(Base):
    """GenAI conversation summaries and extracted fields."""

    __tablename__ = "conversation_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    summary_bullet_points: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    primary_topic: Mapped[str | None] = mapped_column(String(200), nullable=True)
    primary_intent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resolution_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    customer_satisfaction: Mapped[str | None] = mapped_column(String(20), nullable=True)
    total_turns: Mapped[int | None] = mapped_column(Integer, nullable=True)
    agent_turns: Mapped[int | None] = mapped_column(Integer, nullable=True)
    customer_turns: Mapped[int | None] = mapped_column(Integer, nullable=True)
    avg_sentiment_score: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    forbidden_count: Mapped[int] = mapped_column(Integer, default=0)
    high_volume_count: Mapped[int] = mapped_column(Integer, default=0)
    extracted_fields: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    summary_feedback: Mapped[int] = mapped_column(SmallInteger, default=0)
    model_used: Mapped[str | None] = mapped_column(String(50), nullable=True)
    model_version: Mapped[str | None] = mapped_column(String(20), nullable=True)


class ScorecardModel(Base):
    """Module 2: Scorecards template."""
    __tablename__ = "scorecards"

    scorecard_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry_template: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pass_threshold: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    scoring_model: Mapped[str | None] = mapped_column(String(20), nullable=True)
    base_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    max_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    min_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    max_bonus_total: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    calibration_correlation_threshold: Mapped[float | None] = mapped_column(Numeric(4, 3), default=0.80)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)


class ScorecardCategoryModel(Base):
    __tablename__ = "scorecard_categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scorecard_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    name_vi: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    category_type: Mapped[str | None] = mapped_column(String(20), default="deduction")
    max_deduction: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    max_bonus: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    weight: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    score_rule: Mapped[str | None] = mapped_column(String(20), default="deduction")
    sort_order: Mapped[int | None] = mapped_column(Integer, default=0)
    status: Mapped[str | None] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)


class ScorecardCriteriaModel(Base):
    __tablename__ = "scorecard_criteria"

    criteria_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scorecard_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    is_critical: Mapped[bool | None] = mapped_column(Boolean, default=False)
    detection_method: Mapped[str | None] = mapped_column(String(100), nullable=True)
    detection_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    search_window: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    scoring_type: Mapped[str | None] = mapped_column(String(20), default="deduction")
    score_value: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    score_unit: Mapped[str | None] = mapped_column(String(20), default="fixed")
    max_occurrences: Mapped[int | None] = mapped_column(Integer, nullable=True)
    auto_fail: Mapped[bool | None] = mapped_column(Boolean, default=False)
    criteria_type: Mapped[str | None] = mapped_column(String(20), default="auto")
    criteria_level: Mapped[int | None] = mapped_column(Integer, default=1)
    code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)


class ScorecardAssignmentModel(Base):
    __tablename__ = "scorecard_assignments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scorecard_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    assignment_type: Mapped[str] = mapped_column(String(20), nullable=False)
    assignment_value: Mapped[str | None] = mapped_column(String(255), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)


class CallScoreModel(Base):
    """Module 2: Call Scores."""
    __tablename__ = "call_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True)
    agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    scorecard_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    scorecard_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    max_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    percentage: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    pass_fail: Mapped[str | None] = mapped_column(String(20), nullable=True)
    flagged_for_review: Mapped[bool | None] = mapped_column(Boolean, default=False)
    flag_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    criteria_results: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    critical_violations: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    review_action: Mapped[str | None] = mapped_column(String(100), nullable=True)
    scoring_method: Mapped[str | None] = mapped_column(String(20), default="auto")
    score_auto: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    score_manual: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    max_score_auto: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    max_score_manual: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    threshold_normal: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    threshold_good: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    qc_category: Mapped[str | None] = mapped_column(String(20), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    scored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)


class ScorecardBandModel(Base):
    __tablename__ = "scorecard_bands"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    scorecard_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    label_vi: Mapped[str | None] = mapped_column(String(100), nullable=True)
    min_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    max_score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    is_auto_fail_band: Mapped[bool | None] = mapped_column(Boolean, default=False)
    action_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    action_detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    color_hex: Mapped[str | None] = mapped_column(String(7), nullable=True)
    sort_order: Mapped[int | None] = mapped_column(Integer, nullable=True)


class CoachingQueueModel(Base):
    __tablename__ = "coaching_queue"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    call_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    band_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    action_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    priority: Mapped[int | None] = mapped_column(SmallInteger, default=0)
    status: Mapped[str | None] = mapped_column(String(20), default="pending")
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)


class SummaryTemplateModel(Base):
    __tablename__ = "summary_templates"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    field_ids: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    bullet_count_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bullet_count_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_default: Mapped[bool | None] = mapped_column(Boolean, default=False)
    status: Mapped[str | None] = mapped_column(String(20), default="active")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
