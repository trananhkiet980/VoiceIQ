import uuid
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from voiceiq.app.container import Container

router = APIRouter(prefix="/api/v1/demo", tags=["Transcripts"])


class MarkUnprocessedRequest(BaseModel):
    call_ids: list[str]


@router.get("/queue-transcripts")
async def get_queue_transcripts(
    request: Request, tenant_id: str = "916180a7-0b43-5c08-b3c8-c738826880bb", status: str = "pending"
) -> Any:
    container: Container = request.app.state.container
    session_factory = container._session_factory  # pyright: ignore[reportPrivateUsage]
    assert session_factory is not None
    from sqlalchemy import exists, select

    from voiceiq.infrastructure.db.models import MessageAnalysisModel, TranscriptModel

    try:
        async with session_factory() as session:
            has_messages = exists().where(MessageAnalysisModel.call_id == TranscriptModel.call_id)

            if status == "pending":
                stmt = select(TranscriptModel).where(
                    TranscriptModel.tenant_id == uuid.UUID(tenant_id),
                    TranscriptModel.sentiment_overall.is_(None),
                    ~has_messages,
                )
            else:
                stmt = select(TranscriptModel).where(
                    TranscriptModel.tenant_id == uuid.UUID(tenant_id),
                    TranscriptModel.sentiment_overall.is_not(None) | has_messages,
                )
            stmt = stmt.order_by(TranscriptModel.created_at.desc()).limit(15)
            results = await session.execute(stmt)
            transcripts = results.scalars().all()

            return [
                {
                    "call_id": str(t.call_id),
                    "duration_seconds": float(t.duration_seconds) if t.duration_seconds else 0.0,
                    "created_at": t.created_at.isoformat(),
                    "transcript_json": t.transcript_json,
                    "endcall_status": t.endcall_status,
                }
                for t in transcripts
            ]
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "error": "DATABASE_NOT_CONNECTED",
                "message": f"Chưa kết nối được cơ sở dữ liệu PostgreSQL (Port 5432): {str(e)}",
                "hint": "Vui lòng khởi động Docker container PostgreSQL hoặc service PostgreSQL trên máy.",
            },
        )


@router.post("/transcripts/mark-unprocessed")
async def mark_unprocessed(
    req: MarkUnprocessedRequest, request: Request, tenant_id: str = "916180a7-0b43-5c08-b3c8-c738826880bb"
) -> Any:
    container: Container = request.app.state.container
    session_factory = container._session_factory  # pyright: ignore[reportPrivateUsage]
    assert session_factory is not None
    from sqlalchemy import delete, update

    from voiceiq.infrastructure.db.models import (
        CallAnalysisModel,
        CallIntentModel,
        CallScoreModel,
        CallTopicModel,
        ConversationSummaryModel,
        EventOutboxModel,
        MessageAnalysisModel,
        MessageEntityModel,
        TranscriptModel,
    )

    try:
        async with session_factory() as session:
            call_uuids = [uuid.UUID(cid) for cid in req.call_ids]
            await session.execute(
                update(TranscriptModel)
                .where(TranscriptModel.tenant_id == uuid.UUID(tenant_id))
                .where(TranscriptModel.call_id.in_(call_uuids))
                .values(sentiment_overall=None, sentiment_customer=None, sentiment_agent=None)
            )
            await session.execute(delete(MessageEntityModel).where(MessageEntityModel.call_id.in_(call_uuids)))
            await session.execute(delete(MessageAnalysisModel).where(MessageAnalysisModel.call_id.in_(call_uuids)))
            await session.execute(delete(CallTopicModel).where(CallTopicModel.call_id.in_(call_uuids)))
            await session.execute(delete(CallIntentModel).where(CallIntentModel.call_id.in_(call_uuids)))
            await session.execute(delete(ConversationSummaryModel).where(ConversationSummaryModel.call_id.in_(call_uuids)))
            await session.execute(delete(EventOutboxModel).where(EventOutboxModel.aggregate_id.in_(call_uuids)))
            await session.execute(delete(CallScoreModel).where(CallScoreModel.call_id.in_(call_uuids)))
            await session.execute(
                delete(CallAnalysisModel)
                .where(CallAnalysisModel.tenant_id == uuid.UUID(tenant_id))
                .where(CallAnalysisModel.call_id.in_(call_uuids))
            )
            await session.commit()
        return {"message": f"Successfully unmarked {len(req.call_ids)} calls"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"error": "DATABASE_NOT_CONNECTED", "message": f"Lỗi thao tác Database: {str(e)}"},
        )


@router.get("/transcripts/{call_id}")
async def get_transcript_data(
    call_id: str, request: Request, tenant_id: str = "916180a7-0b43-5c08-b3c8-c738826880bb"
) -> Any:
    from voiceiq.service.transcript.queries.get_active_topics_intents import (
        GetActiveTopicsIntentsQuery,
    )
    from voiceiq.service.transcript.queries.get_transcript_detail import GetTranscriptDetailQuery

    container = request.app.state.container

    try:
        # 1. Fetch topics and intents
        topics_handler = container.get_active_topics_intents_handler()
        topics, intents = await topics_handler.handle(
            GetActiveTopicsIntentsQuery(tenant_id=tenant_id, label_format="FULL")
        )

        # 2. Fetch transcript detail
        detail_handler = container.get_transcript_detail_handler()
        transcript_detail = await detail_handler.handle(
            GetTranscriptDetailQuery(tenant_id=tenant_id, call_id=call_id)
        )

        if not transcript_detail:
            return JSONResponse(status_code=404, content={"message": "Call ID not found in DB"})

        # 3. Format for UI
        call_analysis = transcript_detail.get("call_analysis")
        if call_analysis:
            extracted = call_analysis.get("extracted_fields") or {}
            call_analysis["raw_llm_analysis"] = (
                extracted.get("raw_llm_analysis") if isinstance(extracted, dict) else None
            )
            call_analysis["analysis_duration_ms"] = (
                extracted.get("analysis_duration_ms") if isinstance(extracted, dict) else None
            )
            call_analysis["customer_sentiment"] = transcript_detail.get("sentiment_customer", "Neutral")

        return {
            "transcript_id": transcript_detail.get("transcript_id"),
            "call_id": transcript_detail.get("call_id"),
            "sentiment_overall": transcript_detail.get("sentiment_overall"),
            "transcript_json": transcript_detail.get("transcript_json"),
            "call_analysis": call_analysis,
            "message_analyses": transcript_detail.get("message_analyses", []),
            "message_entities": transcript_detail.get("message_entities", []),
            "active_topics": topics,
            "active_intents": intents,
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "error": "DATABASE_NOT_CONNECTED",
                "message": f"Chưa kết nối được cơ sở dữ liệu PostgreSQL (Port 5432): {str(e)}",
            },
        )

@router.get("/explorer/calls")
async def get_explorer_calls_endpoint(
    request: Request,
    tenant_id: str = "916180a7-0b43-5c08-b3c8-c738826880bb",
    status: str = "all",
    intent: str = "",
    min_score: float = 0.0,
    max_score: float = 999.0,
) -> Any:
    from voiceiq.service.transcript.queries.get_explorer_calls import GetExplorerCallsQuery

    container = request.app.state.container
    try:
        handler = container.get_explorer_calls_handler()
        query = GetExplorerCallsQuery(
            tenant_id=tenant_id,
            status_filter=status,
            intent_filter=intent,
            min_score=min_score,
            max_score=max_score,
        )
        calls = await handler.handle(query)
        return {"calls": calls, "total": len(calls)}
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "EXPLORER_QUERY_FAILED", "message": str(e)},
        )
