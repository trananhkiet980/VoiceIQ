"""Command Handler: Analyze Post-Call.

1 Command = 1 Handler File (CQRS-lite).
Orchestrates: LLM inference -> parse -> validate -> business rules -> DB + Outbox.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Any

from voiceiq.app.settings import get_settings

from ..ports.ai_ports import IAiFullAnalysisPort, IAiNerPort, IAiSentimentPort, IAiSummaryPort, IAiZeroShotPort
from ..ports.transcript_repo_port import ITranscriptRepoPort

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnalyzePostCallCommand:
    """Command object for post-call analysis."""

    tenant_id: str
    call_id: str
    transcript_json: list[dict[str, Any]]
    duration_seconds: float = 0.0
    word_count: int = 0
    turn_count: int = 0
    dry_run: bool = False
    confidence_threshold: float | None = None
    model: str | None = None
    prompt_template: str | None = None


class AnalyzePostCallHandler:
    """Handler for post-call analysis pipeline.

    Pipeline: Microservices AI -> Business Rules -> DB Write + Outbox (atomic).
    """

    def __init__(
        self,
        ai_full_port: IAiFullAnalysisPort,
        transcript_repo_port: ITranscriptRepoPort,
        ai_summary_port: IAiSummaryPort | None = None,
        ai_sentiment_port: IAiSentimentPort | None = None,
        ai_zeroshot_port: IAiZeroShotPort | None = None,
        ai_ner_port: IAiNerPort | None = None,
    ) -> None:
        self._full_port = ai_full_port
        self._repo = transcript_repo_port
        self._summary_port = ai_summary_port
        self._sentiment_port = ai_sentiment_port
        self._zeroshot_port = ai_zeroshot_port
        self._ner_port = ai_ner_port

    def _format_transcript(self, transcript_json: list[dict[str, Any]]) -> str:
        """Format transcript_json into a readable timeline format for AI."""
        lines: list[str] = []
        for turn in transcript_json:
            start = float(turn.get("start_time", 0.0))
            end = float(turn.get("end_time", 0.0))
            speaker = str(turn.get("speaker", "Unknown"))
            text = str(turn.get("text", ""))

            if speaker.lower() == "customer":
                speaker_vi = "Khách hàng"
            elif speaker.lower() == "agent":
                speaker_vi = "Tư vấn viên"
            else:
                speaker_vi = "Unknown"

            start_m, start_s = divmod(int(start), 60)
            end_m, end_s = divmod(int(end), 60)

            lines.append(f"[{start_m:02d}:{start_s:02d} - {end_m:02d}:{end_s:02d}] {speaker_vi}: {text}")

        return "\n".join(lines)

    async def _run_case1_strategy(
        self,
        full_text: str,
        output_language: str,
        topic_labels: list[str],
        intent_labels: list[str],
        ner_labels: list[str],
        seed_keywords: list[str],
    ) -> dict[str, Any]:
        """Case 1: Summary from LLM + Labels from LLM in 2 separate calls."""
        summary_task = self._summary_port.generate_summary(full_text, output_language)
        label_task = self._full_port.analyze_full_transcript(
            full_text, topic_labels, intent_labels, ner_labels, seed_keywords, output_language
        )

        summary_res, label_res = await asyncio.gather(summary_task, label_task, return_exceptions=True)

        from voiceiq.service.transcript.domain.rules import build_safe_fallback_result

        analysis = label_res if isinstance(label_res, dict) else build_safe_fallback_result()
        if isinstance(summary_res, dict):
            analysis["summary"] = summary_res

        analysis["message_analyses"] = []  # Prevent overwriting real-time
        return analysis

    async def _run_case2_strategy(
        self,
        full_text: str,
        output_language: str,
        topic_labels: list[str],
        intent_labels: list[str],
        ner_labels: list[str],
        seed_keywords: list[str],
        model: str | None = None,
        prompt_template: str | None = None,
        qa_criteria: list[dict[str, Any]] = None,
        call_datetime: str = "",
    ) -> dict[str, Any]:
        """Case 2: Summary + Labels in Pass 1, then QA+NBA in Pass 2."""
        try:
            analysis = await self._full_port.analyze_full_transcript(
                full_text, topic_labels, intent_labels, ner_labels, seed_keywords, output_language, model, prompt_template, qa_criteria, call_datetime
            )
        except Exception:
            from voiceiq.service.transcript.domain.rules import build_safe_fallback_result

            analysis = build_safe_fallback_result()

        import copy
        analysis["_raw_response"] = copy.deepcopy(analysis)

        analysis["message_analyses"] = []

        # Map LLM Output format to expected UI format
        raw_topics = analysis.get("topics", {})
        topic_customer = raw_topics.get("topic_customer")
        topic_agent = raw_topics.get("topic_agent")
        intent_customer = raw_topics.get("intent_customer")
        intent_agent = raw_topics.get("intent_agent")
        intent_transitions = raw_topics.get("intent_transitions", [])

        call_topics = []
        def _parse_label(raw_val: Any) -> tuple[str, float]:
            if isinstance(raw_val, dict):
                return str(raw_val.get("label", "Unknown")), float(raw_val.get("confidence_score", 0.99))
            return str(raw_val), 0.99

        if topic_customer and topic_customer not in ("Unknown", "Không rõ"):
            lbl, conf = _parse_label(topic_customer)
            if lbl not in ("Unknown", "Không rõ"):
                lbl = [x.strip() for x in lbl.split(",")][0]
                call_topics.append({"speaker": "customer", "label": lbl, "confidence": conf, "is_primary": True})
        
        if topic_agent and topic_agent not in ("Unknown", "Không rõ"):
            lbl, conf = _parse_label(topic_agent)
            if lbl not in ("Unknown", "Không rõ") and not any(t["label"] == lbl for t in call_topics):
                lbl = [x.strip() for x in lbl.split(",")][0]
                call_topics.append({"speaker": "agent", "label": lbl, "confidence": conf, "is_primary": False})

        analysis["call_analysis_topics"] = call_topics
        analysis["intent_transitions"] = intent_transitions

        call_intents = []
        if intent_customer and intent_customer not in ("Unknown", "Không rõ"):
            lbl, conf = _parse_label(intent_customer)
            if lbl not in ("Unknown", "Không rõ"):
                lbl = [x.strip() for x in lbl.split(",")][0]
                call_intents.append({"speaker": "customer", "label": lbl, "confidence": conf, "is_primary": True})
                
        if intent_agent and intent_agent not in ("Unknown", "Không rõ"):
            lbl, conf = _parse_label(intent_agent)
            if lbl not in ("Unknown", "Không rõ"):
                lbl = [x.strip() for x in lbl.split(",")][0]
                call_intents.append({"speaker": "agent", "label": lbl, "confidence": conf, "is_primary": False})
        
        analysis["call_analysis_intents"] = call_intents
        
        # Không gọi Pass 2 nữa, lấy trực tiếp kết quả từ Pass 1 (1-Shot thuần túy) để đồng nhất với scratch
        if qa_criteria:
            analysis["qa_evaluation_llm"] = analysis.get("qa_evaluation", [])
            analysis["nba_llm"] = analysis.get("nba_recommendations", [])

        return analysis

    async def _run_slm_only_strategy(
        self,
        full_text: str,
        transcript_json: list[dict[str, Any]],
        output_language: str,
        topic_labels: list[str],
        intent_labels: list[str],
        ner_labels: list[str],
        ner_config_map: dict[str, dict[str, Any]],
        active_intents_data: list[Any] | None = None,
        tenant_id: str = "dummy",
        call_id: str = "dummy",
    ) -> dict[str, Any]:
        """Strategy 3: Pure SLM. Turn-by-turn SLM + Rule Aggregation + Full-text SLM (No LLM)."""

        message_analyses, message_entities, negative_count, outbox_events = await self._run_turn_by_turn(
            transcript_json,
            topic_labels,
            intent_labels,
            ner_labels,
            ner_config_map,
            active_intents_data,
            tenant_id,
            call_id,
        )

        # Lược bỏ các trường âm thanh không cần thiết để debug SLM dễ nhìn hơn
        for ma in message_analyses:
            ma.pop("volume_db", None)
            ma.pop("speech_rate_wpm", None)
            ma.pop("is_overlap", None)
            ma.pop("overlap_duration_seconds", None)
            ma.pop("silence_before_seconds", None)
            ma.pop("confidence_score", None)

        overall_sentiment = "negative" if negative_count >= 2 else "neutral"

        zeroshot_full_res = await self._zeroshot_port.classify_text(
            full_text, labels=topic_labels + intent_labels, multi_label=True
        )

        analysis: dict[str, Any] = {
            "sentiment_overall": overall_sentiment,
            "topics": {"general": "Unknown", "specific": "Unknown", "dynamic_keywords": []},
            "summary": {
                "issue": "[SLM_ONLY Mode] Không gọi LLM tóm tắt để tiết kiệm tài nguyên",
                "resolution": "",
                "next_steps": "",
            },
            "confidence_score": 0.0,
            "message_analyses": message_analyses,
            "message_entities": message_entities,
            "outbox_events": outbox_events,
        }

        if isinstance(zeroshot_full_res, list):  # pyright: ignore[reportUnnecessaryIsInstance]

            def get_top_label_full(res_list: list[dict[str, Any]], target: list[str]) -> str | None:
                candidates = [r for r in res_list if r["label"] in target]
                if not candidates:
                    return None
                return max(candidates, key=lambda x: x["score"])["label"]

            best_topic = get_top_label_full(zeroshot_full_res, topic_labels)
            if best_topic:
                parts = best_topic.split(":", 1)
                analysis["topics"]["general"] = parts[0].strip()
                if len(parts) > 1:
                    analysis["topics"]["specific"] = parts[1].strip()
            else:
                analysis["topics"]["general"] = "cần review"

            top_topics: list[dict[str, Any]] = []
            topic_cands = [r for r in zeroshot_full_res if r["label"] in topic_labels]
            topic_cands.sort(key=lambda x: x["score"], reverse=True)
            for r in topic_cands[:3]:
                top_topics.append({"label": r["label"], "confidence": r["score"], "is_primary": False})
            if top_topics:
                top_topics[0]["is_primary"] = True
            analysis["call_analysis_topics"] = top_topics

            top_intents: list[dict[str, Any]] = []
            intent_cands = [r for r in zeroshot_full_res if r["label"] in intent_labels]
            intent_cands.sort(key=lambda x: x["score"], reverse=True)
            for r in intent_cands[:3]:
                top_intents.append({"label": r["label"], "confidence": r["score"], "is_primary": False})
            if top_intents:
                top_intents[0]["is_primary"] = True
            analysis["call_analysis_intents"] = top_intents

        return analysis

    async def _run_turn_by_turn(
        self,
        transcript_json: list[dict[str, Any]],
        topic_labels: list[str],
        intent_labels: list[str],
        ner_labels: list[str],
        ner_config_map: dict[str, dict[str, Any]],
        active_intents_data: list[Any] | None = None,
        tenant_id: str = "dummy",
        call_id: str = "dummy",
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int, list[dict[str, Any]]]:
        """Simulate real-time turn-by-turn analysis by batching text to SLM."""
        from .save_realtime_turn import SaveRealtimeTurnCommand, SaveRealtimeTurnHandler

        message_analyses: list[dict[str, Any]] = []
        message_entities: list[dict[str, Any]] = []
        outbox_events: list[dict[str, Any]] = []
        negative_count = 0

        # We need tenant_id and call_id, which we don't have strictly in this signature.
        # But we can extract it or just pass dummy ones if not available because dry_run=True will bypass DB.
        # Wait, the command has them. In this refactor, we just use dummy for dry run.
        rt_handler = SaveRealtimeTurnHandler(self._sentiment_port, self._zeroshot_port, self._repo)

        # For demo purposes, we process sequentially.
        for turn_idx, turn in enumerate(transcript_json):
            text = str(turn.get("text", ""))
            speaker = str(turn.get("speaker", "unknown"))
            turn_number = turn.get("turn", turn_idx + 1)  # Support 1-based "turn" from JSON if available

            rt_cmd = SaveRealtimeTurnCommand(
                tenant_id=tenant_id,
                call_id=call_id,
                speaker=speaker,
                text=text,
                start_time=turn.get("start_time", 0.0),
                end_time=turn.get("end_time", 0.0),
                dry_run=True,  # Prevent double saving
                threshold=0.5,  # Use 0.5 to match frontend exactly
                turn_index=turn_number,  # Use 1-based index to match frontend exactly
            )

            rt_res = await rt_handler.handle(rt_cmd)

            sentiment = rt_res.get("sentiment", "neutral")
            if sentiment.lower() == "negative":
                negative_count += 1

            topic_label = rt_res.get("topic_label")
            topic_confidence = rt_res.get("topic_confidence")
            intent_label = rt_res.get("intent_label")
            intent_confidence = rt_res.get("intent_confidence")

            # 4. NER
            msg_id_ref = f"turn_{turn_idx}"
            try:
                if ner_labels:
                    n_res = await self._ner_port.extract_entities(text, labels=ner_labels)
                    if n_res:
                        for ent in n_res:
                            if not any(e.get("text") == ent.get("text") for e in message_entities):
                                message_entities.append(
                                    {
                                        "text": ent.get("text"),
                                        "label": ent.get("label", ent.get("entity_type", "Unknown")),
                                        "msg_id_ref": msg_id_ref,
                                    }
                                )
            except Exception:
                pass

            topic_conf_val = topic_confidence or 0.0
            intent_conf_val = intent_confidence or 0.0
            avg_conf = (
                (topic_conf_val + intent_conf_val) / 2.0
                if (topic_conf_val > 0 and intent_conf_val > 0)
                else (topic_conf_val or intent_conf_val)
            )

            # Compile turn
            msg_data = {
                "msg_id_ref": msg_id_ref,
                "topic_label": topic_label,
                "topic_confidence": topic_confidence,
                "intent_label": intent_label,
                "intent_confidence": intent_confidence,
                "confidence_score": avg_conf,
                "sentiment": sentiment,
                "sentiment_score": rt_res.get("sentiment_score"),
                "text": text,
                "speaker": speaker,
                "start_time": turn.get("start_time", 0.0),
                "end_time": turn.get("end_time", 0.0),
                "turn_index": turn_idx,
            }
            message_analyses.append(msg_data)

            if "outbox_events" in rt_res:
                outbox_events.extend(rt_res["outbox_events"])

        return message_analyses, message_entities, negative_count, outbox_events

    async def _run_composite_strategy(
        self,
        full_text: str,
        transcript_json: list[dict[str, Any]],
        output_language: str,
        topic_labels: list[str],
        intent_labels: list[str],
        ner_labels: list[str],
        ner_config_map: dict[str, dict[str, Any]],
        active_intents_data: list[Any] | None = None,
        tenant_id: str = "dummy",
        call_id: str = "dummy",
    ) -> dict[str, Any]:
        """Strategy 2: Rule Aggregation from existing Real-time + LLM Summary."""
        # 1. Fetch existing message analyses from DB (Required Constraint)
        message_analyses = await self._repo.get_message_analyses_by_call_id(tenant_id, call_id)
        if not message_analyses or len(message_analyses) == 0:
            raise ValueError(
                "Real-time turn-by-turn analysis is required for COMPOSITE mode. Please process via realtime first."
            )

        # 2. Heuristics / Rule Aggregation
        negative_count = sum(1 for m in message_analyses if str(m.get("sentiment")).lower() == "negative")
        overall_sentiment = "Negative" if negative_count >= 2 else "Neutral"

        # 3. Parallel LLM (Summary)
        summary_res = await self._summary_port.generate_summary(full_text, output_language)

        # 4. Turn-by-Turn Heuristic Aggregation (Replace SLM Full-text)
        from voiceiq.service.transcript.domain.composite_heuristics import (
            aggregate_labels_from_turns,
        )

        top_topics, top_intents = aggregate_labels_from_turns(message_analyses, min_confidence=0.5)

        analysis: dict[str, Any] = {
            "sentiment_overall": overall_sentiment,
            "topics": {"general": "Unknown", "specific": "Unknown", "dynamic_keywords": []},
            "summary": {"issue": "Unknown", "resolution": "Unknown", "next_steps": "Unknown"},
            "confidence_score": 0.0,
            # We return empty lists so we don't duplicate/re-insert what was already inserted in real-time
            "message_analyses": [],
            "_calc_message_analyses": message_analyses,
            "outbox_events": [],
        }

        if not isinstance(summary_res, Exception):
            analysis["summary"] = summary_res

        # Map top topics for call_analysis
        if top_topics:
            best_topic = top_topics[0]["label"]
            parts = best_topic.split(":", 1)
            analysis["topics"]["general"] = parts[0].strip()
            if len(parts) > 1:
                analysis["topics"]["specific"] = parts[1].strip()
        else:
            analysis["topics"]["general"] = "Cần review"

        analysis["call_analysis_topics"] = top_topics
        analysis["call_analysis_intents"] = top_intents

        return analysis

    async def handle(self, command: AnalyzePostCallCommand) -> dict[str, Any] | None:
        """Execute post-call analysis."""
        import json
        import time
        from pathlib import Path
        
        start_time = time.time()

        # 1. Format text
        formatted_text = self._format_transcript(command.transcript_json)

        # 2. Create transcript record
        if command.dry_run:
            transcript_id = str(uuid.uuid4())
        else:
            transcript_id = await self._repo.create_transcript(
                tenant_id=command.tenant_id,
                call_id=command.call_id,
                transcript_json=command.transcript_json,
                duration_seconds=command.duration_seconds,
                word_count=command.word_count,
                turn_count=command.turn_count,
            )

        # 3. Run Strategy
        settings = get_settings()
        out_lang = settings.AI_OUTPUT_LANGUAGE

        active_topics_data = await self._repo.get_active_topics(command.tenant_id)
        active_intents_data = await self._repo.get_active_intents(command.tenant_id)

        topic_labels = [
            t.get("name", t.get("label", str(t))) if isinstance(t, dict) else str(t)  # pyright: ignore[reportUnnecessaryIsInstance]
            for t in active_topics_data
        ]
        intent_labels = [
            i.get("name", i.get("label", str(i))) if isinstance(i, dict) else str(i)  # pyright: ignore[reportUnnecessaryIsInstance]
            for i in active_intents_data
        ]
        seed_keywords = await self._repo.get_active_keywords(command.tenant_id)

        field_configs = await self._repo.get_field_extraction_configs(command.tenant_id)
        ner_labels: list[str] = []
        ner_config_map: dict[str, dict[str, Any]] = {}
        for cfg in field_configs:
            fname = cfg.get("field_name", "")
            if cfg.get("extraction_method") == "ner":
                ner_labels.append(fname)
                ner_config_map[fname] = cfg

        try:
            pipeline_mode = settings.AI_PIPELINE_MODE
            if pipeline_mode == "COMPOSITE":
                analysis = await self._run_composite_strategy(
                    formatted_text,
                    command.transcript_json,
                    out_lang,
                    topic_labels,
                    intent_labels,
                    ner_labels,
                    ner_config_map,
                    active_intents_data,
                    command.tenant_id,
                    command.call_id,
                )
            elif pipeline_mode == "SLM_ONLY":
                analysis = await self._run_slm_only_strategy(
                    formatted_text,
                    command.transcript_json,
                    out_lang,
                    topic_labels,
                    intent_labels,
                    ner_labels,
                    ner_config_map,
                    active_intents_data,
                    command.tenant_id,
                    command.call_id,
                )
            else:
                # Fetch scorecard for QA extraction
                active_scorecard = await self._repo.get_active_scorecard(command.tenant_id)
                qa_criteria = [{"code": c.get("code"), "name": c.get("name"), "description": c.get("description", ""), "score_value": float(c.get("score_value", 1.0))} for c in active_scorecard.get("criteria", [])] if active_scorecard else []

                from datetime import datetime
                call_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                analysis = await self._run_case2_strategy(
                    formatted_text, out_lang, topic_labels, intent_labels, ner_labels, seed_keywords, command.model, command.prompt_template, qa_criteria, call_datetime
                )
        except ValueError as e:
            # Re-raise explicit business rule / constraint errors so API can return 400 Bad Request
            raise e
        except Exception:
            logger.exception("AI microservices pipeline failed", extra={"call_id": command.call_id})
            from voiceiq.service.transcript.domain.rules import build_safe_fallback_result

            analysis = build_safe_fallback_result()

        # 4. Extract real-time generated outbox events
        message_analyses_data: list[dict[str, Any]] = analysis.get("_calc_message_analyses", analysis.get("message_analyses", []))
        raw_outbox_events: list[dict[str, Any]] = analysis.get("outbox_events", [])

        # Override confidence for log extraction if needed
        confidence = float(analysis.get("confidence_score", 0.0))

        # 5. Build outbox events
        outbox_events: list[dict[str, Any]] = []
        from voiceiq.shared.outbox_helper import build_outbox_event

        if raw_outbox_events:
            for event in raw_outbox_events:
                ev_name = event.get("event_name")
                if not ev_name:
                    continue
                ev = build_outbox_event(
                    tenant_id=command.tenant_id,
                    event_name=str(ev_name),
                    aggregate_type="transcript",
                    aggregate_id=transcript_id,
                    payload=event.get("payload", {}),
                )
                outbox_events.append(ev)

        # Evaluate Call-level rules
        from voiceiq.service.transcript.domain.rules import evaluate_post_call_rules

        rule_result = evaluate_post_call_rules(
            tenant_id=command.tenant_id,
            transcript_id=transcript_id,
            message_analyses=[],  # Turn-level evaluated during realtime
            call_analysis_topics=analysis.get("call_analysis_topics", []),
            call_analysis_intents=analysis.get("call_analysis_intents", []),
        )
        for ev_obj in rule_result.outbox_events:
            ev = build_outbox_event(
                tenant_id=command.tenant_id,
                event_name=ev_obj.event_name,
                aggregate_type="transcript",
                aggregate_id=transcript_id,
                payload=ev_obj.payload,
            )
            outbox_events.append(ev)

        # 6. Extract data for 5 tables
        summary = analysis.get("summary", {})

        # Extract QA Checklist dynamically from active intents
        qa_checklist_intents = [
            i.get("label") for i in (active_intents_data or [])
            if isinstance(i, dict) and i.get("detection_rules", {}).get("is_qa_checklist")
        ]

        # SAPP Rule 6.3: Sentiment Calculation (Customer only)
        message_analyses_data: list[dict[str, Any]] = analysis.get("message_analyses", [])
        customer_turns = [m for m in message_analyses_data if str(m.get("speaker")).lower() == "customer"]
        sentiment_score = 0.0
        sentiment_trend = "Giữ nguyên"
        if customer_turns:
            total_weight = 0
            weighted_sum = 0
            for i, turn in enumerate(customer_turns):
                weight = i + 1
                total_weight += weight
                s_label = str(turn.get("sentiment", "neutral")).lower()
                val = 1 if s_label == "positive" else (-1 if s_label == "negative" else 0)
                weighted_sum += val * weight

            avg = weighted_sum / total_weight if total_weight > 0 else 0
            if avg > 0.2:
                overall_sentiment = "Positive"
            elif avg < -0.2:
                overall_sentiment = "Negative"
            else:
                overall_sentiment = "Neutral"

            # Trend
            first_val = 1 if str(customer_turns[0].get("sentiment", "neutral")).lower() == "positive" else (-1 if str(customer_turns[0].get("sentiment", "neutral")).lower() == "negative" else 0)
            last_val = 1 if str(customer_turns[-1].get("sentiment", "neutral")).lower() == "positive" else (-1 if str(customer_turns[-1].get("sentiment", "neutral")).lower() == "negative" else 0)
            if last_val > first_val:
                sentiment_trend = "Cải thiện"
            elif last_val < first_val:
                sentiment_trend = "Xấu đi"
        else:
            overall_sentiment = analysis.get("sentiment_overall", "Neutral")

        analysis["sentiment_overall"] = overall_sentiment
        if "sentiment_customer" not in analysis:
            analysis["sentiment_customer"] = overall_sentiment
        if "sentiment_agent" not in analysis:
            analysis["sentiment_agent"] = "Neutral"

        # Evaluate Call-level QA (Dynamic)
        from voiceiq.service.transcript.domain.sapp_rules import (
            DynamicScoringEngine,
            evaluate_next_best_actions,
        )

        active_scorecard = await self._repo.get_active_scorecard(command.tenant_id)
        summary_templates = await self._repo.get_summary_templates(command.tenant_id)

        # Common variables
        final_intent = "Không rõ"
        if analysis.get("call_analysis_intents"):
            final_intent = analysis["call_analysis_intents"][0].get("label", "Không rõ")

        customer_intents = [m.get("intent_label") or "" for m in customer_turns]
        has_over_promise = any("Cam kết quá lời" in str(m.get("intent_label") or "") for m in message_analyses_data if str(m.get("speaker")).lower() == "agent")

        if "qa_evaluation_llm" in analysis:
            # LLM_ONLY mode with Prompt Chaining QA
            qa_eval = analysis["qa_evaluation_llm"]
            
            score = 0.0
            is_auto_fail = False
            criteria_list = active_scorecard.get("criteria", []) if active_scorecard else []
            
            for q in qa_eval:
                c_code = q.get("code")
                matching_c = next((c for c in criteria_list if c.get("code") == c_code), None) if c_code else None
                
                scoring_type = matching_c.get("scoring_type", "regular") if matching_c else "regular"
                auto_fail = matching_c.get("auto_fail", False) if matching_c else False
                val = float(q.get("score_value", 1.0))
                
                q["scoring_type"] = scoring_type
                q["auto_fail"] = auto_fail
                
                raw_passed = q.get("passed")
                is_passed = raw_passed is True or (isinstance(raw_passed, str) and raw_passed.strip().lower() == "true")
                q["passed"] = is_passed
                
                if is_passed:
                    if scoring_type == "deduction" or scoring_type == "penalty":
                        score -= val
                    else:
                        score += val
                        
                    if auto_fail:
                        is_auto_fail = True

            if is_auto_fail:
                score = 0.0

            qa_score = round(score, 2)
            total_count = len(qa_eval) if qa_eval else 1

            scoring_result = {
                "score": qa_score,
                "checked_codes": [q.get("code") for q in qa_eval if (q.get("passed") is True or str(q.get("passed")).strip().lower() == "true") and q.get("code")],
                "total_checklist": total_count,
                "details": qa_eval,
                "is_auto_fail": is_auto_fail,
                "bands": [],
                "coaching_actions": []
            }
            
            for raw_act in analysis.get("nba_llm", []):
                if isinstance(raw_act, dict):
                    struct = raw_act.get("structured_data", {})
                    category = struct.get("priority", "Bình thường").strip()
                    display_text = raw_act.get("display_text", "").strip()
                    deadline = struct.get("deadline", "")
                else:
                    category = "Xử lý trong thời gian nhất định"
                    display_text = str(raw_act).strip()
                    deadline = ""
                    struct = {}

                lower_cat = category.lower()
                is_praise = "không cần" in lower_cat
                
                scoring_result["coaching_actions"].append({
                    "type": "coaching" if is_praise else "task",
                    "priority": category,
                    "title": display_text if display_text else "Hành động tiếp theo",
                    "action": raw_act.get("ai_advice", ""),
                    "deadline": deadline,
                    "structured_data": struct
                })

            qa_compliance = {
                "score": qa_score,
                "checked": scoring_result["checked_codes"],
                "total": total_count,
                "details": qa_eval
            }

            next_best_actions = scoring_result["coaching_actions"]
        else:
            engine = DynamicScoringEngine(active_scorecard or {})
            scoring_result = engine.evaluate(message_analyses_data)

            qa_score = scoring_result["score"]
            qa_compliance = {
                "score": qa_score,
                "checked": scoring_result["checked_codes"],
                "total": scoring_result["total_checklist"],
                "details": scoring_result["details"]
            }

            next_best_actions = evaluate_next_best_actions(
                final_intent=final_intent,
                sentiment_trend=sentiment_trend,
                customer_intents=customer_intents,
                coaching_actions=scoring_result["coaching_actions"],
                has_over_promise=has_over_promise
            )

        # SAPP Rule 6.4: Tỷ lệ agent nói và Xử lý từ chối
        total_duration = sum(max(float(m.get("end_time", 0.0)) - float(m.get("start_time", 0.0)), 1.0) for m in message_analyses_data)
        agent_duration = sum(max(float(m.get("end_time", 0.0)) - float(m.get("start_time", 0.0)), 1.0) for m in message_analyses_data if str(m.get("speaker")).lower() == "agent")
        agent_talk_ratio = (agent_duration / total_duration * 100) if total_duration > 0 else 50.0

        total_objections = 0
        handled_objections = 0

        objection_keywords = ["từ chối", "băn khoăn", "trì hoãn", "kêu giá cao", "phàn nàn", "chê", "lo ngại", "xin hỏi", "hẹn qua", "chưa đủ", "so sánh"]
        handling_keywords = ["xử lý", "trấn an", "chuyển hướng", "cô lập", "đồng cảm", "xin lỗi", "đề xuất", "chứng minh", "giải thích", "tư vấn"]

        detected_objections = set()

        for i, turn in enumerate(message_analyses_data):
            speaker = str(turn.get("speaker")).lower()
            intent = str(turn.get("intent_label") or "").lower()
            topic = str(turn.get("topic_label") or "").lower()

            is_objection = any(kw in intent for kw in objection_keywords) or any(kw in topic for kw in objection_keywords)

            if speaker == "customer" and is_objection:
                total_objections += 1
                if turn.get("intent_label"):
                    detected_objections.add(turn.get("intent_label"))
                for next_turn in message_analyses_data[i+1:i+3]:
                    next_intent = str(next_turn.get("intent_label") or "").lower()
                    if str(next_turn.get("speaker")).lower() == "agent" and any(kw in next_intent for kw in handling_keywords):
                        handled_objections += 1
                        break

        objections = list(detected_objections)
        objection_handling_rate = (handled_objections / total_objections * 100) if total_objections > 0 else 100.0

        # Construct Dynamic Summary Markdown
        from voiceiq.service.transcript.domain.composite_heuristics import generate_dynamic_summary

        final_summary_markdown = generate_dynamic_summary(
            templates=summary_templates,
            summary=summary,
            qa_score=qa_score,
            objection_handling_rate=objection_handling_rate,
            total_objections=total_objections,
            final_intent=final_intent,
            next_best_actions=next_best_actions,
            agent_talk_ratio=agent_talk_ratio,
            call_analysis_topics=analysis.get("call_analysis_topics", []),
            overall_sentiment=overall_sentiment,
            sentiment_trend=sentiment_trend,
            has_over_promise=has_over_promise,
            missed_qa=[code for code in scoring_result["checked_codes"]], # In a real implementation we would diff with the checklist
            call_analysis_intents=analysis.get("call_analysis_intents", []),
            intent_transitions=analysis.get("intent_transitions", [])
        )


        escalation_analysis = analysis.get("escalation_analysis", {})
        toxicity_analysis = analysis.get("toxicity_analysis", {})

        # Sanitize escalation fields for DB Constraints
        esc_type = escalation_analysis.get("escalation_type")
        if esc_type not in ["verbal", "emotional", "honorific_shift", "behavioral", "compound"]:
            esc_type = None
            
        esc_traj = escalation_analysis.get("escalation_trajectory")
        if esc_traj not in ["stable", "escalating", "de_escalating", "volatile"]:
            esc_traj = None

        raw_llm = analysis.get("summary") if settings.AI_PIPELINE_MODE == "COMPOSITE" else analysis.get("_raw_response", analysis)
        if isinstance(raw_llm, dict):
            raw_llm.pop("_calc_message_analyses", None)

        call_analysis_data: dict[str, Any] = {
            "topics": analysis.get("call_analysis_topics", []),
            "intents": analysis.get("call_analysis_intents", []),
            "escalation_level": escalation_analysis.get("escalation_level", "none") or "none",
            "escalation_type": esc_type,
            "escalation_trajectory": esc_traj,
            "escalation_de_escalation_successful": escalation_analysis.get("de_escalation_successful"),
            "sapp_analysis": {
                "sentiment_trend": sentiment_trend,
                "objections": objections,
                "next_best_actions": next_best_actions,
                "agent_talk_ratio": round(agent_talk_ratio, 1),
                "objection_handling_rate": round(objection_handling_rate, 1)
            },
            "escalation_signals": escalation_analysis.get("escalation_signals"),
            "toxicity_agent_score": toxicity_analysis.get("agent_score"),
            "toxicity_customer_score": toxicity_analysis.get("customer_score"),
            "toxicity_tags": toxicity_analysis.get("toxicity_tags"),
            "toxicity_triggered_auto_fail": toxicity_analysis.get("toxicity_triggered_auto_fail"),
            "script_compliance": qa_compliance,
            "summary_text": final_summary_markdown,
            "summary_bullets": analysis.get("summary", {}).get("summary_bullets", []),
            "extracted_fields": {
                "entities": analysis.get("entities", []),
                "raw_llm_analysis": raw_llm,
                "analysis_duration_ms": int((time.time() - start_time) * 1000)
            },
            "summary_model": command.model or "default",
            "pipeline_version": settings.AI_PIPELINE_MODE,
        }  # pyright: ignore[reportUnknownVariableType]

        message_analyses_data: list[dict[str, Any]] = analysis.get("_calc_message_analyses", analysis.get("message_analyses", []))
        message_entities_data: list[dict[str, Any]] = analysis.get("message_entities", [])

        call_score_data = None
        if active_scorecard or "qa_evaluation_llm" in analysis:
            call_score_data = {
                "scorecard_id": active_scorecard.get("scorecard_id") if active_scorecard else None,
                "score": qa_score,
                "is_auto_fail": scoring_result.get("is_auto_fail", False),
                "bands": scoring_result.get("bands", []),
                "details": scoring_result.get("details", [])
            }

        coaching_queue_data = [
            act for act in next_best_actions if act.get("type") == "coaching"
        ]

        output_data = {
            "transcript_id": transcript_id,
            "call_id": command.call_id,
            "sentiment_overall": analysis.get("sentiment_overall"),
            "call_analysis": call_analysis_data,
            "message_analyses": message_analyses_data,
            "message_entities": message_entities_data,
            "outbox_events": outbox_events,
            "call_score": call_score_data,
            "coaching_queue": coaching_queue_data,
            "raw_llm_analysis": raw_llm,
        }

        # 7. Atomic DB update (Skip if dry_run)
        if command.dry_run:
            log_dir = Path(".data")
            log_dir.mkdir(exist_ok=True)
            out_file = log_dir / "dry_run_output.json"

            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)

            logger.info("Dry run completed. Output saved to %s", out_file)
            return output_data

        await self._repo.update_analysis_results(
            tenant_id=command.tenant_id,
            transcript_id=transcript_id,
            sentiment_overall=str(analysis.get("sentiment_overall", "Neutral")),
            sentiment_customer=str(analysis.get("sentiment_customer", "Neutral")),
            sentiment_agent=str(analysis.get("sentiment_agent", "Neutral")),
            emotion_overall=analysis.get("emotion_overall"),
            emotion_customer=analysis.get("emotion_customer"),
            emotion_agent=analysis.get("emotion_agent"),
            call_analysis=call_analysis_data,  # pyright: ignore[reportUnknownArgumentType]
            message_analyses=[] if pipeline_mode == "COMPOSITE" else message_analyses_data,
            message_entities=message_entities_data,
            outbox_events=outbox_events,
            call_score_data=call_score_data,
            coaching_queue_data=coaching_queue_data,
        )

        logger.info(
            "Post-call analysis completed (5-table schema)",
            extra={
                "call_id": command.call_id,
                "confidence": confidence,
                "needs_labeling": analysis.get("needs_labeling", False),
            },
        )
        return output_data
