import uuid

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
):
    container: Container = request.app.state.container
    session_factory = container._session_factory  # pyright: ignore[reportPrivateUsage]
    assert session_factory is not None
    from sqlalchemy import exists, select

    from voiceiq.infrastructure.db.models import MessageAnalysisModel, TranscriptModel

    async with session_factory() as session:
        has_messages = exists().where(MessageAnalysisModel.call_id == TranscriptModel.call_id)

        if status == "pending":
            stmt = select(TranscriptModel).where(
                TranscriptModel.tenant_id == uuid.UUID(tenant_id),
                TranscriptModel.sentiment_overall.is_(None),
                ~has_messages
            )
        else:
            stmt = select(TranscriptModel).where(
                TranscriptModel.tenant_id == uuid.UUID(tenant_id),
                TranscriptModel.sentiment_overall.is_not(None) | has_messages
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


@router.post("/transcripts/mark-unprocessed")
async def mark_unprocessed(
    req: MarkUnprocessedRequest, request: Request, tenant_id: str = "916180a7-0b43-5c08-b3c8-c738826880bb"
):
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


@router.get("/transcripts/{call_id}")
async def get_transcript_data(call_id: str, request: Request, tenant_id: str = "916180a7-0b43-5c08-b3c8-c738826880bb"):
    from voiceiq.service.transcript.queries.get_active_topics_intents import (
        GetActiveTopicsIntentsQuery,
    )
    from voiceiq.service.transcript.queries.get_transcript_detail import GetTranscriptDetailQuery

    container = request.app.state.container

    # 1. Fetch topics and intents
    topics_handler = container.get_active_topics_intents_handler()
    topics, intents = await topics_handler.handle(GetActiveTopicsIntentsQuery(tenant_id=tenant_id, label_format="FULL"))

    # 2. Fetch transcript detail
    detail_handler = container.get_transcript_detail_handler()
    transcript_detail = await detail_handler.handle(GetTranscriptDetailQuery(tenant_id=tenant_id, call_id=call_id))

    if not transcript_detail:
        return JSONResponse(status_code=404, content={"message": "Call ID not found in DB"})

    # 3. Format for UI
    call_analysis = transcript_detail.get("call_analysis")
    if call_analysis:
        extracted = call_analysis.get("extracted_fields") or {}
        call_analysis["raw_llm_analysis"] = extracted.get("raw_llm_analysis") if isinstance(extracted, dict) else None
        call_analysis["analysis_duration_ms"] = extracted.get("analysis_duration_ms") if isinstance(extracted, dict) else None
        call_analysis["customer_sentiment"] = transcript_detail.get("sentiment_customer", "Neutral")

    return {
        "tenant_id": tenant_id,
        "call_id": call_id,
        "duration_seconds": transcript_detail.get("duration_seconds", 120.0),
        "active_topics_in_db": topics,
        "active_intents_in_db": intents,
        "transcript_json": transcript_detail.get("transcript_json", []),
        "word_count": transcript_detail.get("word_count", 0),
        "turn_count": transcript_detail.get("turn_count", 0),
        "endcall_status": transcript_detail.get("endcall_status", "unknown"),
        "sentiment_overall": transcript_detail.get("sentiment_overall", "Neutral"),
        "emotion_overall": transcript_detail.get("emotion_overall", "normal"),
        "emotion_customer": transcript_detail.get("emotion_customer", "normal"),
        "emotion_agent": transcript_detail.get("emotion_agent", "normal"),
        "call_analysis": call_analysis,
        "raw_llm_analysis": call_analysis.get("raw_llm_analysis") if call_analysis else None,
        "message_analyses": transcript_detail.get("message_analyses", []),
        "qa_score": transcript_detail.get("qa_score")
    }


from typing import Any


class CreateTranscriptRequest(BaseModel):
    call_id: str
    transcript_json: list[dict[str, Any]]
    duration_seconds: float = 120.0

@router.post("/transcripts")
async def create_pending_transcript(
    req: CreateTranscriptRequest, request: Request, tenant_id: str = "916180a7-0b43-5c08-b3c8-c738826880bb"
):
    container: Container = request.app.state.container
    repo = container._transcript_repo  # pyright: ignore[reportPrivateUsage]
    assert repo is not None

    full_text = " ".join([str(t.get("text", "")) for t in req.transcript_json])
    word_count = len(full_text.split())
    turn_count = len(req.transcript_json)

    # Tính duration_seconds từ end_time của turn cuối cùng (nếu có)
    duration = req.duration_seconds
    if req.transcript_json and len(req.transcript_json) > 0:
        last_turn = req.transcript_json[-1]
        if "end_time" in last_turn:
            try:
                duration = float(last_turn["end_time"])
            except ValueError:
                pass

    transcript_id = await repo.create_transcript(
        tenant_id=tenant_id,
        call_id=req.call_id,
        transcript_json=req.transcript_json,
        duration_seconds=duration,
        word_count=word_count,
        turn_count=turn_count,
    )

    return {"message": "Success", "transcript_id": transcript_id}


class DeleteTranscriptRequest(BaseModel):
    call_ids: list[str]

@router.delete("/transcripts")
async def delete_transcripts(
    req: DeleteTranscriptRequest, request: Request, tenant_id: str = "916180a7-0b43-5c08-b3c8-c738826880bb"
):
    container: Container = request.app.state.container
    session_factory = container._session_factory  # pyright: ignore[reportPrivateUsage]
    assert session_factory is not None

    from sqlalchemy import delete

    from voiceiq.infrastructure.db.models import (
        CallAnalysisModel,
        CallIntentModel,
        CallScoreModel,
        CallTopicModel,
        CoachingQueueModel,
        ConversationSummaryModel,
        EventOutboxModel,
        MessageAnalysisModel,
        MessageEntityModel,
        TranscriptModel,
    )

    async with session_factory() as session:
        call_uuids = [uuid.UUID(cid) for cid in req.call_ids]

        # Delete related records
        await session.execute(delete(MessageEntityModel).where(MessageEntityModel.call_id.in_(call_uuids)))
        await session.execute(delete(MessageAnalysisModel).where(MessageAnalysisModel.call_id.in_(call_uuids)))
        await session.execute(delete(CallTopicModel).where(CallTopicModel.call_id.in_(call_uuids)))
        await session.execute(delete(CallIntentModel).where(CallIntentModel.call_id.in_(call_uuids)))
        await session.execute(delete(ConversationSummaryModel).where(ConversationSummaryModel.call_id.in_(call_uuids)))
        await session.execute(delete(EventOutboxModel).where(EventOutboxModel.aggregate_id.in_(call_uuids)))
        await session.execute(delete(CallAnalysisModel).where(CallAnalysisModel.call_id.in_(call_uuids)))
        await session.execute(delete(CallScoreModel).where(CallScoreModel.call_id.in_(call_uuids)))
        await session.execute(delete(CoachingQueueModel).where(CoachingQueueModel.call_id.in_(call_uuids)))

        # Finally delete transcript
        await session.execute(
            delete(TranscriptModel)
            .where(TranscriptModel.tenant_id == uuid.UUID(tenant_id))
            .where(TranscriptModel.call_id.in_(call_uuids))
        )
        await session.commit()
        await session.commit()

    return {"message": f"Successfully deleted {len(req.call_ids)} calls"}

@router.get("/explorer/calls")
async def get_explorer_calls(
    request: Request,
    tenant_id: str = "916180a7-0b43-5c08-b3c8-c738826880bb",
    intent: str = "",
    min_score: float = 0.0,
    max_score: float = 999.0
):
    from voiceiq.service.transcript.queries.get_explorer_calls import GetExplorerCallsQuery

    container = request.app.state.container
    handler = container.get_explorer_calls_handler()

    data = await handler.handle(GetExplorerCallsQuery(
        tenant_id=tenant_id,
        intent_filter=intent,
        min_score=min_score,
        max_score=max_score,
    ))

    return {"calls": data}
