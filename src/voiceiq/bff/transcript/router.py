"""API Router for transcript endpoints.

Responsibilities:
- Parse input, validate DTO
- Extract auth/tenant context from headers
- Call command/query handlers
- Map response/error

MUST NOT contain business logic or direct DB access.
"""

from __future__ import annotations

import time

from fastapi import APIRouter, BackgroundTasks, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from voiceiq.shared.problem_details import not_found

from .mapper import map_db_row_to_response, map_end_call_to_command, map_query_by_call_id
from .request_dto import EndCallRequest, RealtimeTurnRequest
from .response_dto import BaseResponse, RealtimeTurnResponse, TranscriptDetailResponse

router = APIRouter()


def _get_container(request: Request):
    """Extract container from app state."""
    return request.app.state.container


@router.post("/api/v1/calls/end", response_model=BaseResponse)
async def process_end_call(
    request: Request,
    payload: EndCallRequest,
    background_tasks: BackgroundTasks,
) -> BaseResponse | JSONResponse:
    """Submit a completed call for post-call AI analysis.

    The analysis runs in a background task to avoid blocking the API.
    """
    tenant_id = request.headers.get("x-tenant-id", "")
    container = _get_container(request)

    handler = container.get_analyze_post_call_handler()
    command = map_end_call_to_command(tenant_id, payload)

    # Run analysis in background or foreground based on dry_run
    if payload.dry_run:
        result = await handler.handle(command)
        return JSONResponse(content=result)

    background_tasks.add_task(handler.handle, command)

    return BaseResponse(
        success=True,
        message="Đã tiếp nhận yêu cầu phân tích hậu kỳ (Post-call).",
    )


@router.get("/api/v1/calls/{call_id}", response_model=TranscriptDetailResponse)
async def get_call_detail(
    request: Request,
    call_id: str,
) -> TranscriptDetailResponse | JSONResponse:
    """Get transcript analysis detail by call_id."""
    tenant_id = request.headers.get("x-tenant-id", "")
    container = _get_container(request)

    handler = container.get_transcript_detail_handler()
    query = map_query_by_call_id(tenant_id, call_id)
    result = await handler.handle(query)

    if result is None:
        err = not_found(
            "transcript",
            call_id,
            trace_id=request.headers.get("x-request-id", ""),
        )
        return JSONResponse(status_code=err.status, content=err.to_dict())

    return map_db_row_to_response(result)


@router.websocket("/ws/v1/live/{call_id}")
async def realtime_agent_assist(
    websocket: WebSocket,
    call_id: str,
) -> None:
    """Real-time Agent Assist via WebSocket.

    Receives dialog turns, runs fast sentiment analysis,
    returns coaching signals instantly.
    """
    await websocket.accept()
    container = websocket.app.state.container
    handler = container.get_save_realtime_turn_handler()

    # Dùng MOCK_TENANT_ID cho môi trường dev
    from voiceiq.app.settings import get_settings

    settings = get_settings()
    tenant_id = settings.MOCK_TENANT_ID

    try:
        while True:
            data = await websocket.receive_json()
            turn_req = RealtimeTurnRequest(**data)

            start_t = time.time()
            result_dict = await handler.handle_realtime(
                turn_req.text,
                tenant_id=tenant_id,
                call_id=call_id,
                speaker=turn_req.speaker,
                start_time=turn_req.start_time,
                end_time=turn_req.end_time,
            )
            latency = (time.time() - start_t) * 1000

            sentiment_result = result_dict.get("sentiment", "neutral")
            topic_label = result_dict.get("topic_label")
            topic_confidence = result_dict.get("topic_confidence")
            intent_label = result_dict.get("intent_label")
            intent_confidence = result_dict.get("intent_confidence")

            # Generate coaching signal for negative sentiment
            coaching: str | None = None
            if sentiment_result == "negative":
                coaching = "💡 Hãy thể hiện sự đồng cảm: 'Em hiểu sự bất tiện mà anh/chị đang gặp phải...'"
            elif intent_label == "Hủy hợp đồng" or intent_label == "Chuyển mạng":
                coaching = "⚠️ Chú ý: Khách có rủi ro rời mạng (Churn). Hãy đưa ra các ưu đãi giữ chân!"

            resp = RealtimeTurnResponse(
                sentiment=sentiment_result,
                topic_label=topic_label,
                topic_confidence=topic_confidence,
                intent_label=intent_label,
                intent_confidence=intent_confidence,
                coaching_signal=coaching,
                latency_ms=round(latency, 2),
                turn_id=turn_req.turn_id,
            )
            await websocket.send_json(resp.model_dump())

    except WebSocketDisconnect:
        pass
