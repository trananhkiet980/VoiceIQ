"""Business Rule Engine - pure Python.

This module MUST NOT import any framework.
Applies business rules after AI analysis is complete.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field


class LowConfidenceRuleConfig(BaseModel):
    min_confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    ambiguous_margin_score: float = Field(default=0.0, ge=0.0)
    alert_on_missing_topic: bool = Field(default=True)


class EscalationRuleConfig(BaseModel):
    trigger_on_negative_urgency: bool = Field(default=True)


@dataclass(frozen=True)
class OutboxEvent:
    event_name: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class BusinessRuleResult:
    """Result of applying business rules to AI analysis output."""

    needs_labeling: bool
    needs_supervisor_alert: bool
    outbox_events: list[OutboxEvent]


def evaluate_post_call_rules(
    *,
    tenant_id: str,
    transcript_id: str,
    message_analyses: list[dict[str, Any]],
    call_analysis_topics: list[dict[str, Any]] | None = None,
    call_analysis_intents: list[dict[str, Any]] | None = None,
    low_confidence_config: LowConfidenceRuleConfig | None = None,
    escalation_config: EscalationRuleConfig | None = None,
) -> BusinessRuleResult:
    """Evaluate business rules per turn to generate granular outbox events."""
    if not low_confidence_config:
        low_confidence_config = LowConfidenceRuleConfig()
    if not escalation_config:
        escalation_config = EscalationRuleConfig()

    outbox_events: list[OutboxEvent] = []
    needs_labeling = False
    needs_supervisor_alert = False

    threshold = low_confidence_config.min_confidence_threshold
    margin = low_confidence_config.ambiguous_margin_score
    ambiguous_upper_bound = threshold + margin

    for turn in message_analyses:
        turn_idx = turn.get("turn_index", 0)
        speaker = turn.get("speaker", "unknown")
        confidence = float(turn.get("confidence_score", 0.0))
        intent_label = turn.get("intent_label")
        topic_label = turn.get("topic_label")
        sentiment = turn.get("sentiment")

        # Rule 1: Escalation (Negative sentiment)
        if escalation_config.trigger_on_negative_urgency and sentiment == "Negative":
            outbox_events.append(
                OutboxEvent(
                    event_name="VoiceIQ.transcript.escalated",
                    payload={"turn_index": turn_idx, "speaker": speaker, "reason": "Negative sentiment detected"},
                )
            )
            needs_supervisor_alert = True

        # Skip Filler turns from low confidence alerts since they are hardcoded
        if intent_label == "Filler":
            continue

        # Rule 2: Ambiguous Confidence (or strictly low confidence)
        if confidence < ambiguous_upper_bound:
            outbox_events.append(
                OutboxEvent(
                    event_name="VoiceIQ.transcript.low_confidence",
                    payload={
                        "turn_index": turn_idx,
                        "speaker": speaker,
                        "confidence_score": confidence,
                        "reason": f"Confidence score {confidence} is strictly below threshold {threshold}",
                    },
                )
            )
            needs_labeling = True

        # Rule 3: Missing/Uncertain Topic or Intent
        if low_confidence_config.alert_on_missing_topic:
            is_missing_topic = not topic_label or topic_label == "Khác"
            is_missing_intent = not intent_label or intent_label == "Khác"

            if is_missing_topic or is_missing_intent:
                reason_parts: list[str] = []
                if is_missing_topic:
                    reason_parts.append("Topic is missing or unknown")
                if is_missing_intent:
                    reason_parts.append("Intent is missing or unknown")

                outbox_events.append(
                    OutboxEvent(
                        event_name="VoiceIQ.transcript.missing_classification",
                        payload={
                            "turn_index": turn_idx,
                            "speaker": speaker,
                            "topic_label": topic_label,
                            "intent_label": intent_label,
                            "reason": " and ".join(reason_parts),
                        },
                    )
                )
                needs_labeling = True

    # Rule 4: Call-level Low Confidence
    if call_analysis_topics:
        for topic in call_analysis_topics:
            if topic.get("is_primary"):
                topic_conf = float(topic.get("confidence", 0.0))
                if topic_conf < ambiguous_upper_bound:
                    outbox_events.append(
                        OutboxEvent(
                            event_name="VoiceIQ.call.low_confidence_topic",
                            payload={
                                "topic_label": topic.get("label"),
                                "confidence_score": topic_conf,
                                "reason": f"Call-level topic confidence {topic_conf} is below threshold {threshold}",
                            },
                        )
                    )
                    needs_labeling = True

    if call_analysis_intents:
        for intent in call_analysis_intents:
            if intent.get("is_primary"):
                intent_conf = float(intent.get("confidence", 0.0))
                if intent_conf < ambiguous_upper_bound:
                    outbox_events.append(
                        OutboxEvent(
                            event_name="VoiceIQ.call.low_confidence_intent",
                            payload={
                                "intent_label": intent.get("label"),
                                "confidence_score": intent_conf,
                                "reason": f"Call-level intent confidence {intent_conf} is below threshold {threshold}",
                            },
                        )
                    )
                    needs_labeling = True

    return BusinessRuleResult(
        needs_labeling=needs_labeling,
        needs_supervisor_alert=needs_supervisor_alert,
        outbox_events=outbox_events,
    )


def build_safe_fallback_result() -> dict[str, Any]:
    """Return safe default values when AI processing fails."""
    return {
        "sentiment_overall": "Neutral",
        "sentiment_customer": "Neutral",
        "sentiment_agent": "Neutral",
        "confidence_score": 0.0,
        "topics": {
            "general": "Khác",
            "specific": "",
            "dynamic_keywords": [],
        },
        "summary": {
            "issue": "AI processing failed - manual review required",
            "resolution": "",
            "next_steps": "Manual review required",
        },
        "entities": [],
    }
