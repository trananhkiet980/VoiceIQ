from typing import Any

from voiceiq.service.transcript.domain.composite_heuristics import (
    aggregate_labels_from_turns,
)


def test_aggregate_labels_from_turns_basic() -> None:
    message_analyses: list[dict[str, Any]] = [
        {"confidence_score": 0.9, "topic_label": "TopicA", "intent_label": "Hỏi thông tin khóa học", "start_time": 0.0, "end_time": 10.0},
        {"confidence_score": 0.8, "topic_label": "TopicA", "intent_label": "Chốt sale", "start_time": 10.0, "end_time": 15.0},
        {"confidence_score": 0.9, "topic_label": "TopicB", "intent_label": "Unknown", "start_time": 15.0, "end_time": 20.0},
    ]

    top_topics, top_intents = aggregate_labels_from_turns(message_analyses, min_confidence=0.5)

    assert len(top_topics) == 2
    assert top_topics[0]["label"] == "TopicA"
    assert top_topics[0]["is_primary"] is True
    assert top_topics[1]["label"] == "TopicB"
    assert top_topics[1]["is_primary"] is False

    # Chốt sale has highest priority
    assert len(top_intents) == 1
    assert top_intents[0]["label"] == "Chốt đăng ký"
    assert top_intents[0]["is_primary"] is True


def test_aggregate_labels_ignores_low_confidence() -> None:
    message_analyses: list[dict[str, Any]] = [
        {"confidence_score": 0.9, "topic_label": "TopicA", "intent_label": "Khiếu nại"},
        {"confidence_score": 0.3, "topic_label": "TopicB", "intent_label": "Chốt sale"},
    ]

    top_topics, top_intents = aggregate_labels_from_turns(message_analyses, min_confidence=0.5)

    # TopicB and Chốt sale should be ignored because of low confidence
    assert len(top_topics) == 1
    assert top_topics[0]["label"] == "TopicA"

    assert len(top_intents) == 1
    assert top_intents[0]["label"] == "Khiếu nại"


def test_aggregate_labels_ignores_filler_and_unknown() -> None:
    message_analyses: list[dict[str, Any]] = [
        {"confidence_score": 0.9, "topic_label": "Khác", "intent_label": "Filler"},
        {"confidence_score": 0.9, "topic_label": "Unknown", "intent_label": "None"},
        {"confidence_score": 0.9, "topic_label": "TopicA", "intent_label": "Hẹn gọi lại"},
    ]

    top_topics, top_intents = aggregate_labels_from_turns(message_analyses, min_confidence=0.5)

    assert len(top_topics) == 1
    assert top_topics[0]["label"] == "TopicA"

    assert len(top_intents) == 1
    assert top_intents[0]["label"] == "Follow-up / Nuôi lead"


def test_aggregate_labels_weights_last_turns_higher() -> None:
    message_analyses: list[dict[str, Any]] = [
        {"confidence_score": 0.9, "topic_label": "TopicA", "intent_label": "Hỏi thông tin khóa học", "start_time": 0.0, "end_time": 20.0},
        {"confidence_score": 0.9, "topic_label": "TopicA", "intent_label": "Hỏi thông tin khóa học", "start_time": 20.0, "end_time": 40.0},
        {"confidence_score": 0.9, "topic_label": "TopicB", "intent_label": "Hỏi học phí", "start_time": 40.0, "end_time": 45.0},
    ]

    top_topics, top_intents = aggregate_labels_from_turns(message_analyses, min_confidence=0.5)

    assert len(top_topics) == 2
    assert top_topics[0]["label"] == "TopicA"
    assert top_topics[1]["label"] == "TopicB"

    # Both Intents match 'Hỏi ', so outcome is 'Tư vấn thông tin'
    assert len(top_intents) == 1
    assert top_intents[0]["label"] == "Tư vấn thông tin"
