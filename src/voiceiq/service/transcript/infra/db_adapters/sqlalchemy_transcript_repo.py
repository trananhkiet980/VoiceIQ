"""SQLAlchemy implementation of ITranscriptRepoPort."""

from __future__ import annotations

import uuid
from typing import Any, cast

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from voiceiq.infrastructure.db.models import (
    CallAnalysisModel,
    CallIntentModel,
    CallScoreModel,
    CallTopicModel,
    CoachingQueueModel,
    ConversationSummaryModel,
    EventOutboxModel,
    FieldExtractionConfigModel,
    IntentTaxonomyModel,
    KeywordRegistryModel,
    MessageAnalysisModel,
    MessageEntityModel,
    ScorecardBandModel,
    ScorecardCategoryModel,
    ScorecardCriteriaModel,
    ScorecardModel,
    SummaryTemplateModel,
    TopicRegistryModel,
    TranscriptModel,
)


class SqlAlchemyTranscriptRepo:
    """Concrete repository adapter using SQLAlchemy 2.0 Async.

    Implements ITranscriptRepoPort protocol.
    ALL methods enforce tenant_id RLS guard.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def _set_tenant_context(self, session: AsyncSession, tenant_id: str) -> None:
        """Set RLS tenant context for the current transaction."""
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tenant_id, true)"),
            {"tenant_id": tenant_id},
        )

    async def create_transcript(
        self,
        tenant_id: str,
        call_id: str,
        transcript_json: list[dict[str, Any]],
        duration_seconds: float,
        word_count: int,
        turn_count: int,
    ) -> str:
        """Create or update a transcript record."""
        from sqlalchemy import text
        async with self._session_factory() as session:
            await self._set_tenant_context(session, tenant_id)

            # Insert dummy call into calls table to satisfy foreign key constraint
            # Wrap in a nested transaction (savepoint) so if it fails (e.g. table doesn't exist),
            # it doesn't abort the entire session transaction block.
            try:
                async with session.begin_nested():
                    await session.execute(
                        text("INSERT INTO calls (id, call_id, tenant_id, status, created_at) VALUES (:call_id, :call_id, :tenant_id, 'pending', NOW()) ON CONFLICT (id) DO NOTHING"),
                        {"call_id": call_id, "tenant_id": tenant_id}
                    )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Could not insert dummy call record: {e}")

            stmt = select(TranscriptModel.transcript_id).where(TranscriptModel.call_id == uuid.UUID(call_id))
            result = await session.execute(stmt)
            existing_id = result.scalar_one_or_none()

            if existing_id:
                update_stmt = (
                    update(TranscriptModel)
                    .where(TranscriptModel.call_id == uuid.UUID(call_id))
                    .values(
                        duration_seconds=duration_seconds,
                        word_count=word_count,
                        turn_count=turn_count,
                    )
                )
                await session.execute(update_stmt)
                # Cannot update JSON easily via update_stmt due to proxy, fetch and update
                transcript_stmt = select(TranscriptModel).where(TranscriptModel.call_id == uuid.UUID(call_id))
                transcript = (await session.execute(transcript_stmt)).scalar_one()
                dynamic_transcript: Any = transcript
                dynamic_transcript.transcript_json = transcript_json
                await session.commit()
                return str(existing_id)
            else:
                transcript = TranscriptModel(
                    tenant_id=uuid.UUID(tenant_id),
                    call_id=uuid.UUID(call_id),
                    duration_seconds=duration_seconds,
                    word_count=word_count,
                    turn_count=turn_count,
                )
                dynamic_transcript: Any = transcript
                dynamic_transcript.transcript_json = transcript_json
                session.add(transcript)
                await session.commit()
                return str(transcript.transcript_id)

    async def update_analysis_results(
        self,
        tenant_id: str,
        transcript_id: str,
        *,
        sentiment_overall: str | None = None,
        sentiment_customer: str | None = None,
        sentiment_agent: str | None = None,
        emotion_overall: str | None = None,
        emotion_customer: str | None = None,
        emotion_agent: str | None = None,
        call_analysis: dict[str, Any] | None = None,
        message_analyses: list[dict[str, Any]] | None = None,
        message_entities: list[dict[str, Any]] | None = None,
        outbox_events: list[dict[str, Any]] | None = None,
        call_score_data: dict[str, Any] | None = None,
        coaching_queue_data: list[dict[str, Any]] | None = None,
    ) -> None:
        """Update transcript and insert analysis into tables within SAME transaction."""
        async with self._session_factory() as session:
            await self._set_tenant_context(session, tenant_id)

            # 1. Update TranscriptModel
            stmt = (
                update(TranscriptModel)
                .where(TranscriptModel.tenant_id == uuid.UUID(tenant_id))
                .where(TranscriptModel.transcript_id == uuid.UUID(transcript_id))
                .values(
                    sentiment_overall=sentiment_overall,
                    sentiment_customer=sentiment_customer,
                    sentiment_agent=sentiment_agent,
                    emotion_overall=emotion_overall,
                    emotion_customer=emotion_customer,
                    emotion_agent=emotion_agent,
                )
                .returning(TranscriptModel.call_id)
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if not row:
                raise ValueError(f"Transcript {transcript_id} not found")
            call_id_uuid = row

            # Delete old data to prevent UniqueViolationError
            await session.execute(delete(CallAnalysisModel).where(CallAnalysisModel.call_id == call_id_uuid))
            await session.execute(delete(CallTopicModel).where(CallTopicModel.call_id == call_id_uuid))
            await session.execute(delete(CallIntentModel).where(CallIntentModel.call_id == call_id_uuid))
            await session.execute(
                delete(ConversationSummaryModel).where(ConversationSummaryModel.call_id == call_id_uuid)
            )

            if message_analyses:
                await session.execute(delete(MessageAnalysisModel).where(MessageAnalysisModel.call_id == call_id_uuid))
            if message_entities:
                await session.execute(delete(MessageEntityModel).where(MessageEntityModel.call_id == call_id_uuid))

            await session.execute(delete(CallScoreModel).where(CallScoreModel.call_id == call_id_uuid))
            await session.execute(delete(CoachingQueueModel).where(CoachingQueueModel.call_id == call_id_uuid))

            # Extract topic & intent strings (they are now lists of dicts from analyze_post_call.py)
            raw_topics = cast(list[dict[str, Any]], call_analysis.get("topics", []))
            raw_intents = cast(list[dict[str, Any]], call_analysis.get("intents", []))

            # Map topics
            if isinstance(raw_topics, list):  # pyright: ignore[reportUnnecessaryIsInstance]
                for t in raw_topics:
                    t_label = t.get("label")
                    if not t_label:
                        continue
                    t_confidence = t.get("confidence", -1.0)
                    t_is_primary = t.get("is_primary", False)
                    if len(t_label) > 200:
                        t_label = t_label[:197] + "..."

                    topic_stmt = (
                        select(TopicRegistryModel.topic_id).where(TopicRegistryModel.label_vi == t_label).limit(1)
                    )
                    topic_row = await session.execute(topic_stmt)
                    topic_id = topic_row.scalar_one_or_none()

                    ct_model = CallTopicModel(
                        tenant_id=uuid.UUID(tenant_id),
                        call_id=call_id_uuid,
                        topic_id=topic_id,
                        is_primary=t_is_primary,
                        confidence=t_confidence,
                        method="LLM",
                    )
                    session.add(ct_model)

            # Map intents
            if isinstance(raw_intents, list):  # pyright: ignore[reportUnnecessaryIsInstance]
                for i in raw_intents:
                    i_label = i.get("label")
                    if not i_label:
                        continue
                    i_confidence = i.get("confidence", -1.0)
                    i_is_primary = i.get("is_primary", False)
                    if len(i_label) > 100:
                        i_label = i_label[:97] + "..."

                    intent_stmt = (
                        select(
                            IntentTaxonomyModel.intent_id,
                            IntentTaxonomyModel.label,
                            IntentTaxonomyModel.display_name_vi,
                        )
                        .where(IntentTaxonomyModel.display_name_vi == i_label)
                        .limit(1)
                    )
                    intent_row = await session.execute(intent_stmt)
                    intent_record = intent_row.one_or_none()

                    intent_id = intent_record[0] if intent_record else None
                    db_label = intent_record[1] if intent_record and intent_record[1] else i_label
                    db_display = intent_record[2] if intent_record and intent_record[2] else i_label

                    ci_model = CallIntentModel(
                        tenant_id=uuid.UUID(tenant_id),
                        call_id=call_id_uuid,
                        intent_id=intent_id,
                        label=db_label,
                        display_name=db_display,
                        is_primary=i_is_primary,
                        is_oos=False,
                        confidence=i_confidence,
                        detected_at_stage=1,
                    )
                    session.add(ci_model)

            # Conversation Summary
            raw_summary = call_analysis.get("summary", {})
            issue = raw_summary.get("issue", "").strip()
            resolution = raw_summary.get("resolution", "").strip()
            computed_summary = f"{issue} {resolution}".strip()
            final_summary = computed_summary or call_analysis.get("summary_text") or "No summary"

            # Confidence score
            default_confidence = float(call_analysis.get("confidence_score", 1.0))

            # 2.5 Insert CallAnalysisModel (Rich NLP Data)
            ca_kwargs = {
                "tenant_id": uuid.UUID(tenant_id),
                "call_id": call_id_uuid,
                "topics": call_analysis.get("topics"),
                "intents": call_analysis.get("intents"),
                "summary_text": final_summary,
                "summary_bullets": call_analysis.get("summary_bullets"),
                "pipeline_version": call_analysis.get("pipeline_version", "LLM_ONLY"),
            }

            # Optional fields
            for field in [
                "escalation_level",
                "escalation_type",
                "escalation_signals",
                "escalation_peak_timestamp",
                "escalation_trajectory",
                "escalation_de_escalation_successful",
                "escalation_detected_at",
                "toxicity_agent_score",
                "toxicity_customer_score",
                "toxicity_triggered_auto_fail",
                "toxicity_tags",
                "intent_transitions",
                "script_compliance",
                "extracted_fields",
                "summary_model",
            ]:
                val = call_analysis.get(field)
                if val is not None:
                    ca_kwargs[field] = val

            # Safely merge sapp_analysis into extracted_fields JSONB to ensure it gets persisted
            sapp_analysis = call_analysis.get("sapp_analysis")
            if sapp_analysis:
                if "extracted_fields" not in ca_kwargs or ca_kwargs["extracted_fields"] is None:
                    ca_kwargs["extracted_fields"] = {}
                ca_kwargs["extracted_fields"]["sapp_analysis"] = sapp_analysis

            ca_model = CallAnalysisModel(**ca_kwargs)
            session.add(ca_model)

            # Helper to map sentiment to score
            def _map_sentiment_to_score(sentiment: str | None) -> float:
                if not sentiment:
                    return 0.5
                s = sentiment.lower()
                if "positive" in s:
                    return 1.0
                if "negative" in s:
                    return 0.0
                return 0.5

            # 3. Insert MessageAnalysisModel
            msg_models_map: dict[str, uuid.UUID] = {}
            valid_scores: list[float] = []
            for ma in message_analyses:
                ma_id = uuid.uuid4()

                # Ensure sentiment score exists
                sentiment_str = ma.get("sentiment")
                sentiment_score = ma.get("sentiment_score")
                if sentiment_score is None:
                    sentiment_score = _map_sentiment_to_score(sentiment_str)
                valid_scores.append(sentiment_score)

                # Ensure confidence exists
                conf_score = ma.get("confidence_score")
                if conf_score is None:
                    conf_score = default_confidence

                ma_model = MessageAnalysisModel(
                    id=ma_id,
                    tenant_id=uuid.UUID(tenant_id),
                    call_id=call_id_uuid,
                    turn_index=ma["turn_index"],
                    speaker=ma["speaker"],
                    start_time=ma.get("start_time"),
                    end_time=ma.get("end_time"),
                    text_content=ma.get("text_content", ma.get("text", "")),
                    text_corrected=ma.get("text_corrected"),
                    llm_correction_rejected=ma.get("llm_correction_rejected", False),
                    intent_label=ma.get("intent_label"),
                    intent_confidence=ma.get("intent_confidence", conf_score),
                    topic_label=ma.get("topic_label"),
                    topic_confidence=ma.get("topic_confidence", conf_score),
                    sentiment=sentiment_str,
                    sentiment_score=sentiment_score,
                    emotion=ma.get("emotion"),
                    urgency=ma.get("urgency"),
                    toxicity_score=ma.get("toxicity_score"),
                    volume_db=ma.get("volume_db"),
                    is_high_volume=ma.get("is_high_volume", False),
                    speech_rate_wpm=ma.get("speech_rate_wpm"),
                    is_overlap=ma.get("is_overlap", False),
                    overlap_duration_seconds=ma.get("overlap_duration_seconds"),
                    silence_before_seconds=ma.get("silence_before_seconds"),
                    confidence_score=conf_score,
                    turn_score=ma.get("turn_score"),
                    has_forbidden=ma.get("has_forbidden", False),
                    detection_model=ma.get("detection_model"),
                )
                session.add(ma_model)
                if "msg_id_ref" in ma:
                    msg_models_map[ma["msg_id_ref"]] = ma_model.id

            # Tính toán avg sentiment score
            total_turns = len(message_analyses)
            agent_turns = sum(1 for m in message_analyses if m.get("speaker") == "agent")
            customer_turns = sum(1 for m in message_analyses if m.get("speaker") == "customer")
            avg_sentiment_score = sum(valid_scores) / len(valid_scores) if valid_scores else None

            primary_topic_label = (
                next((t.get("label") for t in raw_topics if t.get("is_primary")), None)
                if isinstance(raw_topics, list)  # pyright: ignore[reportUnnecessaryIsInstance]
                else None
            )
            primary_intent_label = (
                next((i.get("label") for i in raw_intents if i.get("is_primary")), None)
                if isinstance(raw_intents, list)  # pyright: ignore[reportUnnecessaryIsInstance]
                else None
            )

            cs_model = ConversationSummaryModel(
                tenant_id=uuid.UUID(tenant_id),
                call_id=call_id_uuid,
                summary_text=final_summary,
                summary_bullet_points=call_analysis.get("summary_bullets"),
                primary_topic=primary_topic_label[:200] if primary_topic_label else None,
                primary_intent=primary_intent_label[:100] if primary_intent_label else None,
                resolution_status=call_analysis.get("resolution_status"),
                customer_satisfaction=call_analysis.get("customer_satisfaction"),
                total_turns=total_turns,
                agent_turns=agent_turns,
                customer_turns=customer_turns,
                avg_sentiment_score=avg_sentiment_score,
                forbidden_count=sum(1 for m in message_analyses if m.get("has_forbidden")),
                high_volume_count=sum(1 for m in message_analyses if m.get("is_high_volume")),
                extracted_fields=call_analysis.get("extracted_fields"),
                model_used=call_analysis.get("model_used", "Ollama LLM"),
                model_version=call_analysis.get("model_version"),
            )
            session.add(cs_model)

            # 4. Insert MessageEntityModel
            for ent in call_analysis.get("message_entities", []):
                msg_uuid = msg_models_map.get(ent.get("msg_id_ref"))
                if not msg_uuid:
                    continue  # Skip if no parent message found
                ent_model = MessageEntityModel(
                    tenant_id=uuid.UUID(tenant_id),
                    call_id=call_id_uuid,
                    message_id=msg_uuid,
                    entity_type=ent.get("entity_type", ent.get("label", "Unknown")),
                    entity_value=ent.get("entity_value", ent.get("text", "")),
                    entity_masked=ent.get("entity_masked"),
                    is_pii=ent.get("is_pii", False),
                    confidence=ent.get("confidence"),
                    start_offset=ent.get("start_offset"),
                    end_offset=ent.get("end_offset"),
                )
                session.add(ent_model)

            # 5. Insert EventOutboxModels if present
            if outbox_events:
                for outbox_event in outbox_events:
                    outbox_model = EventOutboxModel(
                        event_id=uuid.uuid4(),
                        tenant_id=uuid.UUID(tenant_id),
                        aggregate_type=outbox_event.get("aggregate_type", "transcript"),
                        aggregate_id=uuid.UUID(outbox_event.get("aggregate_id", str(transcript_id))),
                        event_type=outbox_event.get("event_name", "unknown.event"),
                        payload=outbox_event.get("payload", {}),
                    )
                    session.add(outbox_model)

            # 6. Insert CallScoreModel if present
            if call_score_data:
                is_auto_fail = call_score_data.get("is_auto_fail", False)
                call_score = CallScoreModel(
                    id=uuid.uuid4(),
                    tenant_id=uuid.UUID(tenant_id),
                    call_id=call_id_uuid,
                    agent_id=uuid.UUID(call_score_data["agent_id"]) if call_score_data.get("agent_id") else None,
                    scorecard_id=uuid.UUID(call_score_data["scorecard_id"]) if call_score_data.get("scorecard_id") else None,
                    scorecard_version=call_score_data.get("scorecard_version", 1),
                    total_score=call_score_data.get("score"),
                    max_score=call_score_data.get("max_score", 100.0),
                    percentage=call_score_data.get("percentage"),
                    pass_fail="fail" if is_auto_fail else "pass",
                    flagged_for_review=is_auto_fail,
                    flag_reason="Auto Fail" if is_auto_fail else None,
                    criteria_results={
                        "details": call_score_data.get("details", []),
                        "bands": call_score_data.get("bands", [])
                    },
                    critical_violations=call_score_data.get("critical_violations", []),
                    review_action=call_score_data.get("review_action"),
                    scoring_method=call_score_data.get("scoring_method", "auto"),
                    score_auto=call_score_data.get("score"),
                    score_manual=call_score_data.get("score_manual"),
                    max_score_auto=call_score_data.get("max_score_auto", 100.0),
                    max_score_manual=call_score_data.get("max_score_manual"),
                    threshold_normal=call_score_data.get("threshold_normal", 60.0),
                    threshold_good=call_score_data.get("threshold_good", 85.0),
                    qc_category=call_score_data.get("qc_category", "normal"),
                    comment=call_score_data.get("comment"),
                    scored_at=call_score_data.get("scored_at"),
                )
                session.add(call_score)

            # 7. Insert CoachingQueueModel if present
            if coaching_queue_data:
                for cq in coaching_queue_data:
                    coaching = CoachingQueueModel(
                        id=uuid.uuid4(),
                        tenant_id=uuid.UUID(tenant_id),
                        call_id=call_id_uuid,
                        agent_id=uuid.uuid4(), # Mock agent_id as Transcript doesn't store it yet
                        notes=f"Rule: {cq.get('title', 'QA Need Coaching')}\nAction: {cq.get('action')}\nCoaching: {cq.get('coaching')}",
                        status="pending"
                    )
                    session.add(coaching)

            await session.commit()

    async def get_by_call_id(
        self,
        tenant_id: str,
        call_id: str,
    ) -> dict[str, Any] | None:
        """Retrieve transcript by call_id with tenant guard."""
        async with self._session_factory() as session:
            await self._set_tenant_context(session, tenant_id)

            stmt = select(TranscriptModel).where(
                TranscriptModel.tenant_id == uuid.UUID(tenant_id),
                TranscriptModel.call_id == uuid.UUID(call_id),
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            if row is None:
                return None
            return self._row_to_dict(row)

    async def get_explorer_calls(
        self,
        tenant_id: str,
        status_filter: str = "all",
    ) -> list[dict[str, Any]]:
        """Get list of calls with joined analysis and score data."""
        async with self._session_factory() as session:
            await self._set_tenant_context(session, tenant_id)

            stmt = (
                select(TranscriptModel, CallAnalysisModel, CallScoreModel)
                .outerjoin(CallAnalysisModel, TranscriptModel.call_id == CallAnalysisModel.call_id)
                .outerjoin(CallScoreModel, TranscriptModel.call_id == CallScoreModel.call_id)
                .where(TranscriptModel.tenant_id == uuid.UUID(tenant_id))
            )

            # Ignore status_filter for now as it's not strictly implemented in demo,
            # or could just return everything for demo UI.
            stmt = stmt.order_by(TranscriptModel.created_at.desc()).limit(150)

            result = await session.execute(stmt)
            rows = result.all()

            data = []
            for trans, anal, score in rows:
                data.append({
                    "transcript": self._row_to_dict(trans),
                    "call_analysis": self._analysis_row_to_dict(anal) if anal else None,
                    "call_score": {"total_score": float(score.total_score)} if score and score.total_score is not None else None,
                })
            return data

    async def get_full_call_detail(
        self,
        tenant_id: str,
        call_id: str,
    ) -> dict[str, Any] | None:
        """Get full call details including message analyses."""
        async with self._session_factory() as session:
            await self._set_tenant_context(session, tenant_id)
            call_uuid = uuid.UUID(call_id)

            # Get Transcript
            stmt = select(TranscriptModel).where(
                TranscriptModel.tenant_id == uuid.UUID(tenant_id),
                TranscriptModel.call_id == call_uuid,
            )
            trans = (await session.execute(stmt)).scalar_one_or_none()
            if not trans:
                return None

            # Get Analysis
            anal_stmt = select(CallAnalysisModel).where(CallAnalysisModel.call_id == call_uuid)
            anal = (await session.execute(anal_stmt)).scalar_one_or_none()

            # Get Score
            score_stmt = select(CallScoreModel).where(CallScoreModel.call_id == call_uuid)
            score = (await session.execute(score_stmt)).scalar_one_or_none()

            # Get Message Analyses
            msg_stmt = select(MessageAnalysisModel).where(MessageAnalysisModel.call_id == call_uuid).order_by(MessageAnalysisModel.turn_index)
            msg_res = (await session.execute(msg_stmt)).scalars().all()
            messages = []
            for m in msg_res:
                messages.append({
                    "turn_id": m.turn_index,
                    "speaker": m.speaker,
                    "text": m.text_content,
                    "intent_label": m.intent_label,
                    "intent_confidence": float(m.intent_confidence) if m.intent_confidence else 0.0,
                    "topic_label": m.topic_label,
                    "topic_confidence": float(m.topic_confidence) if m.topic_confidence else 0.0,
                    "sentiment": m.sentiment,
                    "sentiment_score": float(m.sentiment_score) if m.sentiment_score else 0.0,
                    "toxicity_score": float(m.toxicity_score) if m.toxicity_score else 0.0,
                })

            trans_dict = self._row_to_dict(trans)
            trans_dict["call_analysis"] = self._analysis_row_to_dict(anal) if anal else None
            trans_dict["qa_score"] = float(score.total_score) if score and score.total_score is not None else None
            trans_dict["message_analyses"] = messages
            return trans_dict

    def _analysis_row_to_dict(self, row: CallAnalysisModel) -> dict[str, Any]:
        """Convert CallAnalysisModel to dict."""
        return {
            "pipeline_version": row.pipeline_version,
            "summary_model": row.summary_model,
            "summary_text": row.summary_text,
            "summary_bullets": row.summary_bullets,
            "extracted_fields": row.extracted_fields,
            "topics": row.topics,
            "intents": row.intents,
            "toxicity_tags": row.toxicity_tags,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    async def get_by_id(
        self,
        tenant_id: str,
        transcript_id: str,
    ) -> dict[str, Any] | None:
        """Retrieve transcript by transcript_id with tenant guard."""
        async with self._session_factory() as session:
            await self._set_tenant_context(session, tenant_id)

            stmt = select(TranscriptModel).where(
                TranscriptModel.tenant_id == uuid.UUID(tenant_id),
                TranscriptModel.transcript_id == uuid.UUID(transcript_id),
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            if row is None:
                return None
            return self._row_to_dict(row)

    @staticmethod
    def _row_to_dict(row: TranscriptModel) -> dict[str, Any]:
        """Convert ORM model to dict (explicit mapping, no magic)."""
        dynamic_row: Any = row
        return {
            "transcript_id": str(row.transcript_id),
            "tenant_id": str(row.tenant_id),
            "call_id": str(row.call_id),
            "word_count": row.word_count,
            "turn_count": row.turn_count,
            "duration_seconds": float(row.duration_seconds) if row.duration_seconds else None,
            "sentiment_overall": row.sentiment_overall,
            "sentiment_customer": row.sentiment_customer,
            "sentiment_agent": row.sentiment_agent,
            "emotion_overall": row.emotion_overall,
            "emotion_customer": row.emotion_customer,
            "emotion_agent": row.emotion_agent,
            "endcall_status": row.endcall_status,
            "full_text_combined": row.full_text_combined,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "transcript_json": cast(list[dict[str, Any]] | None, dynamic_row.transcript_json),
            "diagnostics": cast(dict[str, Any] | None, dynamic_row.diagnostics),
        }

    async def get_active_topics(self, tenant_id: str) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            await self._set_tenant_context(session, tenant_id)
            stmt = select(TopicRegistryModel).where(
                TopicRegistryModel.tenant_id == uuid.UUID(tenant_id), TopicRegistryModel.status == "active"
            )
            result = await session.execute(stmt)

            all_rows = result.scalars().all()

            # Find all IDs that act as a parent to some other active topic
            parent_ids = {str(r.parent_topic_id) for r in all_rows if r.parent_topic_id}

            topics: list[dict[str, Any]] = []
            for row in all_rows:
                row_id = str(row.topic_id)
                # Only include leaf nodes (topics that are NOT parents)
                if row_id in parent_ids:
                    continue

                display_name = str(row.label_vi or row.label)
                if row.description_nli:
                    full_label = f"{display_name}: {row.description_nli}"
                else:
                    full_label = display_name
                topics.append(
                    {
                        "id": row_id,
                        "name": display_name,
                        "label": full_label,
                        "parent_id": str(row.parent_topic_id) if row.parent_topic_id else None,
                        "metadata": row.metadata_json or {},
                    }
                )
            return topics

    async def get_active_intents(self, tenant_id: str) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            await self._set_tenant_context(session, tenant_id)
            stmt = select(IntentTaxonomyModel).where(
                IntentTaxonomyModel.tenant_id == uuid.UUID(tenant_id), IntentTaxonomyModel.status == "active"
            )
            result = await session.execute(stmt)
            intents: list[dict[str, Any]] = []
            for row in result.scalars().all():
                display_name = str(row.display_name_vi or row.label)
                if row.description_nli:
                    full_label = f"{display_name}: {row.description_nli}"
                else:
                    full_label = display_name
                intents.append(
                    {
                        "id": str(row.intent_id),
                        "name": display_name,
                        "label": full_label,
                        "detection_rules": row.detection_rules or {},
                    }
                )
            return intents

    async def get_field_extraction_configs(self, tenant_id: str) -> list[dict[str, Any]]:
        async with self._session_factory() as session:
            await self._set_tenant_context(session, tenant_id)
            stmt = select(FieldExtractionConfigModel).where(
                FieldExtractionConfigModel.tenant_id == uuid.UUID(tenant_id),
                FieldExtractionConfigModel.status == "active",
            )
            result = await session.execute(stmt)
            configs: list[dict[str, Any]] = []
            for row in result.scalars().all():
                configs.append(
                    {
                        "field_name": row.field_name,
                        "field_type": row.field_type,
                        "is_pii": row.is_pii,
                        "pii_mask_pattern": row.pii_mask_pattern,
                        "extraction_method": row.extraction_method,
                    }
                )
            return configs

    async def get_active_keywords(self, tenant_id: str) -> list[str]:
        async with self._session_factory() as session:
            await self._set_tenant_context(session, tenant_id)
            stmt = select(KeywordRegistryModel.keyword).where(
                KeywordRegistryModel.tenant_id == uuid.UUID(tenant_id), KeywordRegistryModel.status == "active"
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def insert_realtime_message(
        self,
        tenant_id: str,
        call_id: str,
        message_data: dict[str, Any],
        outbox_events: list[dict[str, Any]] | None = None,
    ) -> str:
        """Insert a single real-time message analysis into the DB. Returns message ID."""
        async with self._session_factory() as session:
            await self._set_tenant_context(session, tenant_id)
            ma_id = uuid.uuid4()
            ma_model = MessageAnalysisModel(
                id=ma_id,
                tenant_id=uuid.UUID(tenant_id),
                call_id=uuid.UUID(call_id),
                turn_index=message_data.get("turn_index", 0),
                speaker=message_data.get("speaker", "unknown"),
                start_time=message_data.get("start_time"),
                end_time=message_data.get("end_time"),
                text_content=message_data.get("text", ""),
                text_corrected=message_data.get("text_corrected"),
                llm_correction_rejected=message_data.get("llm_correction_rejected", False),
                intent_label=message_data.get("intent_label"),
                intent_confidence=message_data.get("intent_confidence"),
                topic_label=message_data.get("topic_label"),
                topic_confidence=message_data.get("topic_confidence"),
                sentiment=message_data.get("sentiment"),
                sentiment_score=message_data.get("sentiment_score"),
                emotion=message_data.get("emotion"),
                urgency=message_data.get("urgency"),
                toxicity_score=message_data.get("toxicity_score"),
                volume_db=message_data.get("volume_db"),
                is_high_volume=message_data.get("is_high_volume", False),
                speech_rate_wpm=message_data.get("speech_rate_wpm"),
                is_overlap=message_data.get("is_overlap", False),
                overlap_duration_seconds=message_data.get("overlap_duration_seconds"),
                silence_before_seconds=message_data.get("silence_before_seconds"),
                confidence_score=message_data.get("confidence_score"),
                turn_score=message_data.get("turn_score"),
                has_forbidden=message_data.get("has_forbidden", False),
                detection_model=message_data.get("detection_model"),
            )
            session.add(ma_model)

            if outbox_events:
                for event in outbox_events:
                    ev = EventOutboxModel(
                        event_id=uuid.uuid4(),
                        tenant_id=uuid.UUID(tenant_id),
                        event_type=event.get("event_name"),
                        aggregate_type=event.get("aggregate_type", "transcript"),
                        aggregate_id=uuid.UUID(event.get("aggregate_id", call_id)),
                        payload=event.get("payload", {}),
                    )
                    session.add(ev)

            await session.commit()
            return str(ma_id)

    async def get_message_analyses_by_call_id(
        self,
        tenant_id: str,
        call_id: str,
    ) -> list[dict[str, Any]]:
        """Retrieve all message analyses for a given call_id, ordered by turn_index."""
        async with self._session_factory() as session:
            await self._set_tenant_context(session, tenant_id)
            stmt = (
                select(MessageAnalysisModel)
                .where(
                    MessageAnalysisModel.tenant_id == uuid.UUID(tenant_id),
                    MessageAnalysisModel.call_id == uuid.UUID(call_id),
                )
                .order_by(MessageAnalysisModel.turn_index.asc())
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()

            analyses: list[dict[str, Any]] = []
            for row in rows:
                analyses.append(
                    {
                        "id": str(row.id),
                        "call_id": str(row.call_id),
                        "turn_index": row.turn_index,
                        "speaker": row.speaker,
                        "text_content": row.text_content,
                        "intent_label": row.intent_label,
                        "intent_confidence": float(row.intent_confidence)
                        if row.intent_confidence is not None
                        else None,
                        "topic_label": row.topic_label,
                        "topic_confidence": float(row.topic_confidence) if row.topic_confidence is not None else None,
                        "sentiment": row.sentiment,
                        "sentiment_score": float(row.sentiment_score) if row.sentiment_score is not None else None,
                        "confidence_score": float(row.confidence_score) if row.confidence_score is not None else None,
                    }
                )
            return analyses

    async def get_active_scorecard(self, tenant_id: str) -> dict[str, Any] | None:
        """Get the active scorecard, including its categories, criteria, and bands."""
        async with self._session_factory() as session:
            await self._set_tenant_context(session, tenant_id)

            # Fetch the main scorecard
            stmt = select(ScorecardModel).where(
                ScorecardModel.tenant_id == uuid.UUID(tenant_id),
                ScorecardModel.status == "active"
            ).limit(1)
            result = await session.execute(stmt)
            scorecard = result.scalar_one_or_none()

            if not scorecard:
                return None

            scorecard_id = scorecard.scorecard_id

            # Fetch categories
            cat_stmt = select(ScorecardCategoryModel).where(
                ScorecardCategoryModel.scorecard_id == scorecard_id,
                ScorecardCategoryModel.status == "active"
            )
            cat_result = await session.execute(cat_stmt)
            categories = cat_result.scalars().all()

            # Fetch criteria
            crit_stmt = select(ScorecardCriteriaModel).where(
                ScorecardCriteriaModel.scorecard_id == scorecard_id
            )
            crit_result = await session.execute(crit_stmt)
            criteria = crit_result.scalars().all()

            # Fetch bands
            band_stmt = select(ScorecardBandModel).where(
                ScorecardBandModel.scorecard_id == scorecard_id
            )
            band_result = await session.execute(band_stmt)
            bands = band_result.scalars().all()

            return {
                "scorecard_id": str(scorecard_id),
                "name": scorecard.name,
                "scoring_model": scorecard.scoring_model,
                "base_score": float(scorecard.base_score),
                "max_score": float(scorecard.max_score),
                "pass_threshold": float(scorecard.pass_threshold),
                "categories": [
                    {
                        "category_id": str(c.id),
                        "name": c.name,
                        "weight": float(c.weight),
                        "category_type": c.category_type
                    } for c in categories
                ],
                "criteria": [
                    {
                        "criteria_id": str(c.criteria_id),
                        "category_id": str(c.category_id),
                        "code": c.code,
                        "name": c.name,
                        "description": c.description,
                        "detection_method": c.detection_method,
                        "detection_config": c.detection_config or {},
                        "scoring_type": c.scoring_type,
                        "score_value": float(c.score_value),
                        "is_critical": c.is_critical,
                        "auto_fail": c.auto_fail
                    } for c in criteria
                ],
                "bands": [
                    {
                        "band_id": str(b.id),
                        "code": b.code,
                        "min_score": float(b.min_score),
                        "max_score": float(b.max_score),
                        "action_code": b.action_code,
                        "action_detail": b.action_detail or {},
                        "is_auto_fail_band": b.is_auto_fail_band
                    } for b in bands
                ]
            }

    async def get_summary_templates(self, tenant_id: str) -> list[dict[str, Any]]:
        """Get summary templates for dynamic summary generation."""
        async with self._session_factory() as session:
            await self._set_tenant_context(session, tenant_id)
            stmt = select(SummaryTemplateModel).where(
                SummaryTemplateModel.tenant_id == uuid.UUID(tenant_id)
            )
            result = await session.execute(stmt)
            templates = result.scalars().all()

            return [
                {
                    "template_id": str(t.id),
                    "name": t.name,
                    "prompt_template": t.prompt_template,
                    "field_ids": t.field_ids or [],
                    "description": t.description
                } for t in templates
            ]
