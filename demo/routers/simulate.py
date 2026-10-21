from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from voiceiq.app.container import Container
from voiceiq.app.settings import get_settings
from voiceiq.service.transcript.commands.analyze_post_call import AnalyzePostCallCommand
from voiceiq.service.transcript.commands.save_realtime_turn import SaveRealtimeTurnCommand

router = APIRouter(prefix="/api/v1/demo/simulate", tags=["Simulate"])


class RealtimeTurnRequest(BaseModel):
    text: str
    speaker: str
    start_time: float
    end_time: float
    decibel_db: float | None = None
    is_overlap: bool | None = None
    speech_rate_wpm: float | None = None
    confidence_score: float | None = None
    silence_before_seconds: float | None = None
    overlap_duration_seconds: float | None = None
    call_id: str | None = None
    turn_id: int | str | None = None
    save_to_db: bool = Field(default=False)


class TranscriptTurn(BaseModel):
    text: str
    speaker: str
    start_time: float
    end_time: float
    decibel_db: float | None = None
    is_overlap: bool | None = None
    speech_rate_wpm: float | None = None
    confidence_score: float | None = None
    silence_before_seconds: float | None = None
    overlap_duration_seconds: float | None = None


class SimulatePostCallRequest(BaseModel):
    tenant_id: str
    call_id: str
    duration_seconds: float = 120.0
    transcript_json: list[TranscriptTurn]
    override_topics: list[Any] = Field(default_factory=list)
    override_intents: list[Any] = Field(default_factory=list)
    save_to_db: bool = Field(default=False)
    pipeline_mode: str = Field(default="CASE_1")
    label_format: Literal["FULL", "ONLY_LABEL", "ONLY_DESC"] = Field(default="FULL")
    threshold: float = Field(default=0.5)
    model: str | None = None
    prompt_template: str | None = None


@router.post("/realtime")
async def simulate_realtime(
    req: RealtimeTurnRequest, request: Request, tenant_id: str = "916180a7-0b43-5c08-b3c8-c738826880bb"
):
    container: Container = request.app.state.container
    handler = container.get_save_realtime_turn_handler()
    command = SaveRealtimeTurnCommand(
        tenant_id=tenant_id,
        call_id=req.call_id or "simulated-call",
        speaker=req.speaker,
        text=req.text,
        start_time=req.start_time,
        end_time=req.end_time,
        dry_run=not req.save_to_db,
    )
    result = await handler.handle(command)
    return result


@router.post("/postcall")
async def simulate_postcall(req: SimulatePostCallRequest, request: Request):
    container: Container = request.app.state.container
    tenant_id = req.tenant_id
    settings = get_settings()
    old_mode = settings.AI_PIPELINE_MODE
    settings.AI_PIPELINE_MODE = req.pipeline_mode
    handler = None
    original_repo = None

    try:
        if req.pipeline_mode in ["PROMPT_1", "PROMPT_2", "PROMPT_3"]:
            import os
            prompt_file = {
                "PROMPT_1": "v1_full.txt",
                "PROMPT_2": "v2_short.txt",
                "PROMPT_3": "v3_fewshot.txt"
            }.get(req.pipeline_mode)

            prompt_path = os.path.join("scratch", "prompts", prompt_file)
            if os.path.exists(prompt_path):
                with open(prompt_path, encoding="utf-8") as f:
                    req.prompt_template = f.read()
            req.pipeline_mode = "LLM_ONLY"  # fall back to standard pipeline handling after setting prompt

        handler = container.get_analyze_post_call_handler()
        if req.label_format != "FULL" and not req.override_topics and not req.override_intents:
            from voiceiq.service.transcript.queries.get_active_topics_intents import (
                GetActiveTopicsIntentsQuery,
            )

            topics_handler = container.get_active_topics_intents_handler()
            topics_list, intents_list = await topics_handler.handle(GetActiveTopicsIntentsQuery(
                tenant_id=req.tenant_id,
                label_format=req.label_format,
            ))

            req.override_topics = topics_list
            req.override_intents = intents_list

        original_repo = handler._repo  # pyright: ignore[reportPrivateUsage]

        class MockOverrideRepo:
            def __getattr__(self, name: str) -> Any:
                return getattr(original_repo, name)

            async def get_active_topics(self, tid: str) -> list[Any]:
                if original_repo is None:
                    return req.override_topics
                return req.override_topics if req.override_topics else await original_repo.get_active_topics(tid)

            async def get_active_intents(self, tid: str) -> list[Any]:
                if original_repo is None:
                    return req.override_intents
                return req.override_intents if req.override_intents else await original_repo.get_active_intents(tid)

        handler._repo = MockOverrideRepo()  # pyright: ignore[reportAttributeAccessIssue, reportPrivateUsage]

        command = AnalyzePostCallCommand(
            tenant_id=tenant_id,
            call_id=req.call_id,
            duration_seconds=req.duration_seconds,
            transcript_json=[t.model_dump() for t in req.transcript_json],
            word_count=sum(len(str(t.text).split()) for t in req.transcript_json),
            turn_count=len(req.transcript_json),
            dry_run=not req.save_to_db,
            confidence_threshold=req.threshold,
            model=req.model,
            prompt_template=req.prompt_template,
        )
        try:
            result = await handler.handle(command)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))

        if result:
            result["pipeline_version"] = req.pipeline_mode
            result["db_report"] = {
                "saved_status": "Success" if req.save_to_db else "Simulated",
            }
        return result
    finally:
        settings.AI_PIPELINE_MODE = old_mode
        if handler is not None and original_repo is not None:
            handler._repo = original_repo  # pyright: ignore[reportPrivateUsage]

@router.get("/scorecard-config")
async def get_scorecard_config(request: Request, tenant_id: str = "916180a7-0b43-5c08-b3c8-c738826880bb"):
    container: Container = request.app.state.container
    session_factory = container._session_factory  # pyright: ignore[reportPrivateUsage]
    assert session_factory is not None, "session_factory not initialized"
    import uuid

    from sqlalchemy import select

    from voiceiq.infrastructure.db.models import (
        ScorecardBandModel,
        ScorecardCriteriaModel,
        ScorecardModel,
    )

    async with session_factory() as session:
        # Fetch active scorecard
        scorecard_result = await session.execute(
            select(ScorecardModel).where(
                ScorecardModel.tenant_id == uuid.UUID(tenant_id),
                ScorecardModel.status == "active"
            )
        )
        scorecard = scorecard_result.scalar_one_or_none()
        if not scorecard:
            return {"criteria": [], "bands": []}

        # Fetch criteria
        c_stmt = select(ScorecardCriteriaModel).where(
            ScorecardCriteriaModel.scorecard_id == scorecard.scorecard_id
        )
        c_res = await session.execute(c_stmt)
        criteria = [
            {
                "title": c.name,
                "type": c.criteria_type,
                "intent_codes": c.detection_config.get("intents", []) if c.detection_config else [],
                "score_value": c.score_value,
                "auto_fail": c.auto_fail
            }
            for c in c_res.scalars().all()
        ]

        # Fetch bands
        b_stmt = select(ScorecardBandModel).where(
            ScorecardBandModel.scorecard_id == scorecard.scorecard_id
        )
        b_res = await session.execute(b_stmt)
        bands = [{"name": b.label_vi or b.code, "actions": b.action_detail or {}} for b in b_res.scalars().all()]

        return {"criteria": criteria, "bands": bands}
