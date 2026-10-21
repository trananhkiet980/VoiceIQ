import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from voiceiq.app.container import Container
from voiceiq.bff.transcript.response_dto import RealtimeTurnResponse

router = APIRouter(tags=["WebSocket"])


class RealtimeTurnRequest(BaseModel):
    text: str
    speaker: str
    start_time: float
    end_time: float
    call_id: str | None = None
    turn_id: int | str | None = None
    save_to_db: bool = False


@router.websocket("/ws/v1/live/{call_id}")
async def realtime_agent_assist_ws(
    websocket: WebSocket,
    call_id: str,
    tenant_id: str = "916180a7-0b43-5c08-b3c8-c738826880bb",
    label_format: str = "FULL",
    threshold: float = 0.5,
):
    await websocket.accept()
    if not tenant_id:
        tenant_id = "916180a7-0b43-5c08-b3c8-c738826880bb"
    container: Container = websocket.app.state.container
    handler = container.get_save_realtime_turn_handler()

    if label_format != "FULL":
        session_factory = container._session_factory  # pyright: ignore[reportPrivateUsage]
        assert session_factory is not None, "session_factory not initialized"
        import uuid

        from sqlalchemy import select

        from voiceiq.infrastructure.db.models import IntentTaxonomyModel, TopicRegistryModel

        async with session_factory() as session:
            topics = await session.execute(
                select(TopicRegistryModel).where(
                    TopicRegistryModel.tenant_id == uuid.UUID(tenant_id), TopicRegistryModel.status == "active"
                )
            )
            intents = await session.execute(
                select(IntentTaxonomyModel).where(
                    IntentTaxonomyModel.tenant_id == uuid.UUID(tenant_id), IntentTaxonomyModel.status == "active"
                )
            )
            topics_list: list[dict[str, Any]] = []
            for t in topics.scalars().all():
                name = t.label_vi or t.label
                label_val = name if label_format == "ONLY_LABEL" else (t.description_nli or "")
                topics_list.append(
                    {
                        "id": str(t.topic_id),
                        "label": label_val,
                        "parent_id": str(t.parent_topic_id) if t.parent_topic_id else None,
                        "metadata": t.metadata_json or {},
                    }
                )
            intents_list: list[dict[str, Any]] = []
            for i in intents.scalars().all():
                name = i.display_name_vi or i.label
                label_val = name if label_format == "ONLY_LABEL" else (i.description_nli or "")
                intents_list.append(
                    {"id": str(i.intent_id), "label": label_val, "detection_rules": i.detection_rules or {}}
                )

        original_repo = handler._repo  # pyright: ignore[reportPrivateUsage]

        class MockOverrideRepo2:
            def __getattr__(self, name: str) -> Any:
                return getattr(original_repo, name)

            async def get_active_topics(self, tid: str) -> list[Any]:
                return topics_list

            async def get_active_intents(self, tid: str) -> list[Any]:
                return intents_list

        handler._repo = MockOverrideRepo2()  # pyright: ignore[reportAttributeAccessIssue, reportPrivateUsage]

    try:
        while True:
            data = await websocket.receive_json()
            req = RealtimeTurnRequest(**data)
            start_t = time.time()
            result_dict = await handler.handle_realtime(
                req.text,
                tenant_id=tenant_id,
                call_id=req.call_id or "",
                speaker=req.speaker,
                start_time=req.start_time,
                end_time=req.end_time,
                dry_run=not req.save_to_db,
                threshold=threshold,
                turn_index=req.turn_id if isinstance(req.turn_id, int) else 0,
            )
            latency = (time.time() - start_t) * 1000

            sentiment_result = result_dict.get("sentiment", "neutral")
            topic_label = result_dict.get("topic_label")
            topic_confidence = result_dict.get("topic_confidence")
            intent_label = result_dict.get("intent_label")
            intent_confidence = result_dict.get("intent_confidence")

            coaching = None
            if sentiment_result == "negative":
                coaching = "💡 Hãy thể hiện sự đồng cảm: 'Em hiểu sự bất tiện mà anh/chị đang gặp phải...'"
            elif intent_label in ("Hủy hợp đồng", "Chuyển mạng"):
                coaching = "⚠️ Chú ý: Khách có rủi ro rời mạng. Đưa ra ưu đãi ngay!"

            resp = RealtimeTurnResponse(
                sentiment=sentiment_result,
                topic_label=topic_label,
                topic_confidence=topic_confidence,
                intent_label=intent_label,
                intent_confidence=intent_confidence,
                qa_compliance=result_dict.get("qa_compliance"),
                sentiment_score=result_dict.get("sentiment_score"),
                confidence_score=result_dict.get("confidence_score"),
                coaching_signal=coaching,
                latency_ms=round(latency, 2),
                turn_id=req.turn_id,
                speaker=req.speaker,
                text_content=req.text,
                entities=result_dict.get("entities"),
                outbox_events=result_dict.get("outbox_events"),
            )
            await websocket.send_json(resp.model_dump())
    except (WebSocketDisconnect, RuntimeError):
        pass
