"""Command Handler: Save Realtime Turn.

1 Command = 1 Handler File (CQRS-lite).
Handles real-time sentiment analysis for WebSocket Agent Assist.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from ..ports.ai_ports import IAiSentimentPort, IAiZeroShotPort
from ..ports.transcript_repo_port import ITranscriptRepoPort


@dataclass(frozen=True)
class SaveRealtimeTurnCommand:
    """Command for processing a realtime dialog turn."""

    tenant_id: str
    call_id: str
    speaker: str
    text: str
    start_time: float
    end_time: float
    dry_run: bool = False
    threshold: float = 0.5
    turn_index: int = 0


class SaveRealtimeTurnHandler:
    """Handler for real-time turn processing.

    Processes Sentiment, Topic, and Intent for a single turn.
    """

    def __init__(
        self,
        repo_port: ITranscriptRepoPort,
        ai_sentiment_port: IAiSentimentPort | None = None,
        ai_zeroshot_port: IAiZeroShotPort | None = None,
        ai_ner_port=None,
        ai_full_port=None,
    ) -> None:
        self._repo = repo_port
        self._sentiment = ai_sentiment_port
        self._zeroshot = ai_zeroshot_port
        self._ner = ai_ner_port
        self._full = ai_full_port

    async def handle(self, command: SaveRealtimeTurnCommand) -> dict[str, Any]:
        """Process a realtime turn and return sentiment, topic, and intent."""
        # 1. Fetch active topics and intents (should be cached by repo)
        active_topics_data, active_intents_data = await asyncio.gather(
            self._repo.get_active_topics(command.tenant_id), self._repo.get_active_intents(command.tenant_id)
        )

        # Rule 1: Filler Words Bypass
        text_clean = "".join(c for c in command.text.lower() if c.isalnum() or c.isspace()).strip()
        words = text_clean.split()
        filler_words = {
            "dạ",
            "vâng",
            "dạ vâng",
            "à",
            "ừ",
            "ừm",
            "dạ vâng ạ",
            "dạ đúng rồi",
            "oke chị",
            "cảm ơn",
            "dạ em cảm ơn",
            "xin nghe",
            "xin chào",
            "chào chị",
            "chào anh",
        }
        if len(words) < 7 and text_clean in filler_words:
            msg_data = {
                "topic_label": None,
                "topic_confidence": 0.0,
                "intent_label": "Filler",
                "intent_confidence": 1.0,
                "sentiment": "Neutral",
                "text": command.text,
                "speaker": command.speaker,
                "start_time": command.start_time,
                "end_time": command.end_time,
                "turn_index": 0,
            }
            if command.call_id and command.tenant_id and not command.dry_run:
                try:
                    await self._repo.insert_realtime_message(command.tenant_id, command.call_id, msg_data)
                except Exception:
                    pass
            return msg_data

        filtered_topics_data: list[Any] = []
        for t in active_topics_data:
            if isinstance(t, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
                req = t.get("metadata", {}).get("applicable_speaker")
                if not req:
                    # If parent has no speaker, inherit from children if all children have the same speaker
                    tid = t.get("id")
                    if tid:
                        child_reqs = [
                            t2.get("metadata", {}).get("applicable_speaker")
                            for t2 in active_topics_data
                            if isinstance(t2, dict) and t2.get("parent_id") == tid  # pyright: ignore[reportUnnecessaryIsInstance]
                        ]
                        if child_reqs and all(cr and cr.lower() == child_reqs[0].lower() for cr in child_reqs):
                            req = child_reqs[0]

                if req and req.lower() != "both" and req.lower() != command.speaker.lower():
                    continue
            filtered_topics_data.append(t)

        filtered_intents_data: list[Any] = []
        for i in active_intents_data:
            if isinstance(i, dict) and "detection_rules" in i:  # pyright: ignore[reportUnnecessaryIsInstance]
                req = i["detection_rules"].get("applicable_speaker")
                if req and req.lower() != "both" and req.lower() != command.speaker.lower():
                    continue
            filtered_intents_data.append(i)

        # 2. Run analysis concurrently (Sentiment and L1 Topic)
        async def run_sentiment_safe() -> tuple[str, float]:
            if self._sentiment is not None:
                res = await self._sentiment.analyze_sentiment_fast(command.text)
                return res if isinstance(res, tuple) else (res, 0.8)
            # Lightweight keyword-based sentiment fallback
            txt_low = command.text.lower()
            neg_words = ['lỗi', 'hỏng', 'chậm', 'tệ', 'kém', 'bực', 'phàn nàn', 'hủy', 'không được', 'đắt', 'sai']
            pos_words = ['cảm ơn', 'tuyệt', 'tốt', 'nhanh', 'hài lòng', 'ok', 'dạ vâng', 'rõ rồi', 'hay']
            if any(w in txt_low for w in neg_words):
                return ('negative', 0.85)
            if any(w in txt_low for w in pos_words):
                return ('positive', 0.85)
            return ('neutral', 0.7)

        sentiment_task = run_sentiment_safe()

        async def run_topic_hierarchical() -> dict[str, Any] | None:
            if self._zeroshot is None:
                return None
            l1_topics = [t for t in filtered_topics_data if isinstance(t, dict) and t.get("hierarchy_level") == 1]
            if not l1_topics:
                l1_topics = filtered_topics_data

            l1_labels = [str(t.get("label", "")) for t in l1_topics]
            if not l1_labels:
                return None

            l1_res = await self._zeroshot.classify_text(command.text, labels=l1_labels, multi_label=True)
            if not l1_res:
                return None

            best_l1 = max(l1_res, key=lambda x: x.get("score", 0.0))
            best_l1_lbl = best_l1.get("label")
            best_l1_topic = next((t for t in l1_topics if t.get("label") == best_l1_lbl), None)

            if best_l1_topic:
                l1_id = best_l1_topic.get("id")
                l2_topics = [t for t in filtered_topics_data if isinstance(t, dict) and t.get("parent_id") == l1_id]
                if l2_topics:
                    l2_labels = [str(t.get("label", "")) for t in l2_topics]
                    l2_res = await self._zeroshot.classify_text(command.text, labels=l2_labels, multi_label=True)
                    if l2_res:
                        return max(l2_res, key=lambda x: x.get("score", 0.0))

            return best_l1

        sent_result, best_topic_res = await asyncio.gather(sentiment_task, run_topic_hierarchical())  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
        sent_label, sent_score = sent_result if isinstance(sent_result, tuple) else (sent_result, 0.0)  # pyright: ignore[reportUnnecessaryIsInstance]

        topic_label: str | None = best_topic_res.get("label") if best_topic_res else None
        topic_confidence: float = float(best_topic_res.get("score", 0.0)) if best_topic_res else 0.0

        # 3. Intent Classification (Independent of Topic to avoid butterfly effect)
        intent_text = command.text

        optimized_intents = []
        for i in filtered_intents_data:
            if isinstance(i, dict) and i.get("label"):
                optimized_intents.append(i.get("label", ""))

        if len(optimized_intents) == 1:
            optimized_intents.append("Khác")

        intent_label: str | None = None
        intent_confidence: float = -1.0

        if optimized_intents and self._zeroshot is not None:
            i_res = await self._zeroshot.classify_text(intent_text, labels=optimized_intents, multi_label=True)
            if i_res:
                best_i = max(i_res, key=lambda x: x.get("score", 0.0))
                intent_label = best_i.get("label")
                intent_confidence = float(best_i.get("score", 0.0))

        # Calculate Confidence Score (Average of Intent & Topic, or just the one available)
        topic_conf_val = topic_confidence or 0.0
        intent_conf_val = intent_confidence or 0.0
        avg_conf = (
            (topic_conf_val + intent_conf_val) / 2.0
            if (topic_conf_val > 0 and intent_conf_val > 0)
            else (topic_conf_val or intent_conf_val)
        )

        # Extract QA Checklist dynamically from active intents
        qa_checklist_intents = [
            str(i.get("label", "")) for i in active_intents_data
            if isinstance(i, dict) and i.get("label") and i.get("detection_rules", {}).get("is_qa_checklist")
        ]

        # Evaluate QA Compliance (Turn-by-turn)
        from voiceiq.service.transcript.domain.sapp_rules import evaluate_qa_compliance
        qa_compliance = evaluate_qa_compliance(command.speaker, intent_label or "", qa_checklist_intents)

        # 3.5 NER Extraction
        extracted_entities = []
        if self._ner:
            field_configs = await self._repo.get_field_extraction_configs(str(command.tenant_id))
            ner_labels = [str(cfg.get("label", "")) for cfg in field_configs if cfg.get("extraction_method") == "ner" and cfg.get("label")]
            if ner_labels:
                try:
                    n_res = await self._ner.extract_entities(command.text, labels=ner_labels)
                    for nr in n_res:
                        if nr.get("score", 0.0) >= command.threshold:
                            extracted_entities.append(nr)
                except Exception:
                    pass

        # 4. Write to Database
        msg_data: dict[str, Any] = {
            "topic_label": topic_label,
            "topic_confidence": topic_confidence,
            "intent_label": intent_label,
            "entities": extracted_entities if extracted_entities else None,
            "intent_confidence": intent_confidence,
            "qa_compliance": qa_compliance,
            "confidence_score": avg_conf,
            "sentiment": sent_label,
            "sentiment_score": sent_score,
            "text": command.text,
            "speaker": command.speaker,
            "start_time": command.start_time,
            "end_time": command.end_time,
            # For simplicity in real-time, turn_index is not passed in the command currently,
            # but would be derived in a real stream.
            "turn_index": command.turn_index,
        }

        # 5. Evaluate Real-time Business Rules (Outbox Events)
        from voiceiq.service.transcript.domain.rules import (
            LowConfidenceRuleConfig,
            evaluate_post_call_rules,
        )

        low_conf_cfg = LowConfidenceRuleConfig(min_confidence_threshold=command.threshold)
        rule_result = evaluate_post_call_rules(
            tenant_id=command.tenant_id,
            transcript_id="realtime",  # Not strictly needed for these rules
            message_analyses=[msg_data],
            low_confidence_config=low_conf_cfg,
        )

        # Add outbox events to msg_data so it returns to UI/caller
        outbox_event_dicts: list[dict[str, Any]] = []
        for ev in rule_result.outbox_events:
            outbox_event_dicts.append(
                {
                    "event_name": ev.event_name,
                    "aggregate_type": "transcript",
                    "aggregate_id": command.call_id,
                    "payload": ev.payload,
                }
            )
        msg_data["outbox_events"] = outbox_event_dicts

        try:
            if command.call_id and command.tenant_id and not command.dry_run:
                await self._repo.insert_realtime_message(
                    command.tenant_id, command.call_id, msg_data, outbox_events=outbox_event_dicts
                )
        except Exception as e:
            # If DB write fails, don't crash real-time stream
            import logging

            logging.getLogger(__name__).warning("Failed to save real-time turn to DB: %s", e)

        return msg_data

    async def handle_realtime(self, text: str, tenant_id: str, call_id: str = "", **kwargs: Any) -> dict[str, Any]:
        """Simplified method for WebSocket handler - returns all realtime NLP."""
        command = SaveRealtimeTurnCommand(
            tenant_id=tenant_id,
            call_id=call_id,
            speaker=str(kwargs.get("speaker", "customer")),
            text=text,
            start_time=float(kwargs.get("start_time", 0.0)),
            end_time=float(kwargs.get("end_time", 0.0)),
            dry_run=bool(kwargs.get("dry_run", False)),
            threshold=float(kwargs.get("threshold", 0.5)),
            turn_index=int(kwargs.get("turn_index", 0)),
        )
        return await self.handle(command)
