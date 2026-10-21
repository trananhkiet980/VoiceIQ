"""Backfill Script: Chạy AI phân tích cho các dòng dữ liệu đã có sẵn trong bảng transcripts.

Usage:
    uv run python apps/backfill_main.py
"""

import asyncio
import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voiceiq.app.container import Container
from voiceiq.app.settings import get_settings
from voiceiq.infrastructure.db.models import TranscriptModel

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def process_transcript(
    session: AsyncSession,
    container: Container,
    tenant_id: str,
    transcript_id: str,
    full_text_combined: str,
):
    """Chạy 3 AI Microservices và cập nhật kết quả."""
    logger.info("Processing transcript_id: %s", transcript_id)

    handler = container.get_analyze_post_call_handler()
    settings = get_settings()

    # Lấy dữ liệu
    stmt = select(TranscriptModel).where(
        TranscriptModel.tenant_id == uuid.UUID(tenant_id), TranscriptModel.transcript_id == uuid.UUID(transcript_id)
    )
    res = await session.execute(stmt)
    record = res.scalar_one_or_none()
    if not record:
        return

    dynamic_record: Any = record
    transcript_json: list[dict[str, Any]] = dynamic_record.transcript_json or []

    # 1. Format & Run AI
    formatted_text = handler._format_transcript(transcript_json)  # pyright: ignore[reportPrivateUsage]

    repo = container._transcript_repo  # pyright: ignore[reportPrivateUsage]
    assert repo is not None

    active_topics_data = await repo.get_active_topics(tenant_id)
    active_intents_data = await repo.get_active_intents(tenant_id)

    topic_labels: list[str] = [
        t.get("name", t.get("label", str(t))) if isinstance(t, dict) else str(t)  # pyright: ignore[reportUnnecessaryIsInstance]
        for t in active_topics_data
    ]
    intent_labels: list[str] = [
        i.get("name", i.get("label", str(i))) if isinstance(i, dict) else str(i)  # pyright: ignore[reportUnnecessaryIsInstance]
        for i in active_intents_data
    ]
    seed_keywords = await repo.get_active_keywords(tenant_id)

    field_configs = await repo.get_field_extraction_configs(tenant_id)
    ner_labels: list[str] = []
    ner_config_map: dict[str, dict[str, Any]] = {}
    for cfg in field_configs:
        fname = str(cfg.get("field_name", ""))
        if cfg.get("extraction_method") == "ner":
            ner_labels.append(fname)
            ner_config_map[fname] = cfg

    try:
        if settings.AI_PIPELINE_MODE == "LLM_ONLY":
            analysis = await handler._run_case2_strategy(  # pyright: ignore[reportPrivateUsage]
                full_text=formatted_text,
                output_language=settings.AI_OUTPUT_LANGUAGE,
                topic_labels=topic_labels,
                intent_labels=intent_labels,
                ner_labels=ner_labels,
                seed_keywords=seed_keywords,
            )
        else:
            analysis = await handler._run_composite_strategy(  # pyright: ignore[reportPrivateUsage]
                full_text=formatted_text,
                transcript_json=transcript_json,
                output_language=settings.AI_OUTPUT_LANGUAGE,
                topic_labels=topic_labels,
                intent_labels=intent_labels,
                ner_labels=ner_labels,
                ner_config_map=ner_config_map,
                active_intents_data=active_intents_data,
                tenant_id=tenant_id,
                call_id=str(dynamic_record.call_id) if hasattr(dynamic_record, "call_id") else "dummy",
            )
    except Exception:
        from voiceiq.service.transcript.domain.rules import build_safe_fallback_result

        logger.exception("AI microservices pipeline failed for backfill")
        analysis = build_safe_fallback_result()

    # Note: Trong Backfill, chúng ta thường bỏ qua Business Rules (evaluate_post_call_rules)
    # để tránh việc sinh ra quá nhiều Outbox Event (tin nhắn gửi bù) cho những cuộc gọi cũ.

    # Extract data for 5 tables
    summary: dict[str, Any] = analysis.get("summary", {})  # type: ignore
    call_analysis_data: dict[str, Any] = {
        "topics": analysis.get("call_analysis_topics", []),
        "intents": analysis.get("call_analysis_intents", []),
        "escalation_level": "high" if str(analysis.get("emotion_overall", "")) == "anger" else "none",
        "escalation_signals": [],
        "toxicity_agent_score": 0.0,
        "toxicity_customer_score": 0.0,
        "toxicity_tags": {},
        "script_compliance": {},
        "summary_text": str(summary.get("issue", "")) + ". " + str(summary.get("resolution", "")),
        "summary_bullets": [
            str(summary.get("issue", "")),
            str(summary.get("resolution", "")),
            str(summary.get("next_steps", "")),
        ],
        "extracted_fields": {},
    }
    message_analyses_data: list[dict[str, Any]] = analysis.get("message_analyses", [])  # type: ignore
    message_entities_data: list[dict[str, Any]] = analysis.get("message_entities", [])  # type: ignore

    await repo.update_analysis_results(
        tenant_id=tenant_id,
        transcript_id=transcript_id,
        sentiment_overall=str(analysis.get("sentiment_overall", "Neutral")),
        sentiment_customer=str(analysis.get("sentiment_customer", "Neutral")),
        sentiment_agent=str(analysis.get("sentiment_agent", "Neutral")),
        call_analysis=call_analysis_data,  # pyright: ignore[reportUnknownArgumentType]
        message_analyses=message_analyses_data,
        message_entities=message_entities_data,
    )
    logger.info("Successfully backfilled transcript_id: %s", transcript_id)


async def main():
    container = Container()
    await container.init()

    try:
        if not container._session_factory:  # pyright: ignore[reportPrivateUsage]
            raise RuntimeError("Database not initialized")

        async with container._session_factory() as session:  # pyright: ignore[reportPrivateUsage]
            # Lấy tất cả các transcript chưa được phân tích AI (sentiment_overall is NULL)
            stmt = select(TranscriptModel).where(TranscriptModel.sentiment_overall.is_(None))
            result = await session.execute(stmt)
            records = result.scalars().all()

            if not records:
                logger.info("Không có dòng dữ liệu nào cần phân tích (Tất cả đã được AI chấm điểm).")
                return

            logger.info("Tìm thấy %d dòng cần phân tích. Bắt đầu chạy...", len(records))

            for record in records:
                # Bỏ qua nếu full_text_combined trống
                if not record.transcript_json:
                    continue

                await process_transcript(
                    session=session,
                    container=container,
                    tenant_id=str(record.tenant_id),
                    transcript_id=str(record.transcript_id),
                    full_text_combined=record.full_text_combined,  # type: ignore
                )

    finally:
        await container.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
