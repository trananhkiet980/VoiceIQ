from typing import Any

from voiceiq.service.transcript.domain.rules import (
    EscalationRuleConfig,
    LowConfidenceRuleConfig,
    build_safe_fallback_result,
    evaluate_post_call_rules,
)


def test_build_safe_fallback_result() -> None:
    result = build_safe_fallback_result()
    assert result["sentiment_overall"] == "Neutral"
    assert result["confidence_score"] == 0.0
    assert result["topics"]["general"] == "Khác"
    assert "manual review required" in result["summary"]["issue"]


def test_evaluate_escalation_rule_negative_sentiment() -> None:
    message_analyses: list[dict[str, Any]] = [
        {
            "turn_index": 0,
            "speaker": "customer",
            "sentiment": "Negative",
            "confidence_score": 0.9,
            "topic_label": "ValidTopic",
            "intent_label": "ValidIntent",
        }
    ]
    result = evaluate_post_call_rules(
        tenant_id="test",
        transcript_id="test",
        message_analyses=message_analyses,
        escalation_config=EscalationRuleConfig(trigger_on_negative_urgency=True),
        low_confidence_config=LowConfidenceRuleConfig(min_confidence_threshold=0.5),
    )
    assert result.needs_supervisor_alert is True
    assert len(result.outbox_events) == 1
    assert result.outbox_events[0].event_name == "VoiceIQ.transcript.escalated"


def test_evaluate_low_confidence_rule() -> None:
    message_analyses: list[dict[str, Any]] = [
        {
            "turn_index": 1,
            "speaker": "agent",
            "confidence_score": 0.3,  # Below threshold 0.5
            "intent_label": "SomeIntent",
            "topic_label": "SomeTopic",
            "sentiment": "Neutral",
        }
    ]
    result = evaluate_post_call_rules(
        tenant_id="test",
        transcript_id="test",
        message_analyses=message_analyses,
        low_confidence_config=LowConfidenceRuleConfig(min_confidence_threshold=0.5, ambiguous_margin_score=0.0),
    )
    assert result.needs_labeling is True

    events = [ev.event_name for ev in result.outbox_events]
    assert "VoiceIQ.transcript.low_confidence" in events
    assert "VoiceIQ.transcript.missing_classification" not in events


def test_evaluate_missing_classification() -> None:
    message_analyses: list[dict[str, Any]] = [
        {
            "turn_index": 2,
            "speaker": "customer",
            "confidence_score": 0.9,
            "intent_label": "Khác",  # Missing/Unknown
            "topic_label": "",       # Missing
            "sentiment": "Neutral",
        }
    ]
    result = evaluate_post_call_rules(
        tenant_id="test",
        transcript_id="test",
        message_analyses=message_analyses,
    )
    assert result.needs_labeling is True
    assert len(result.outbox_events) == 1
    assert result.outbox_events[0].event_name == "VoiceIQ.transcript.missing_classification"
    assert "Topic is missing or unknown and Intent is missing or unknown" in result.outbox_events[0].payload["reason"]


def test_evaluate_call_level_low_confidence() -> None:
    topics: list[dict[str, Any]] = [{"label": "Issue", "confidence": 0.4, "is_primary": True}]
    intents: list[dict[str, Any]] = [{"label": "Complain", "confidence": 0.3, "is_primary": True}]

    result = evaluate_post_call_rules(
        tenant_id="test",
        transcript_id="test",
        message_analyses=[],
        call_analysis_topics=topics,
        call_analysis_intents=intents,
        low_confidence_config=LowConfidenceRuleConfig(min_confidence_threshold=0.5),
    )

    assert result.needs_labeling is True
    events = [ev.event_name for ev in result.outbox_events]
    assert "VoiceIQ.call.low_confidence_topic" in events
    assert "VoiceIQ.call.low_confidence_intent" in events
