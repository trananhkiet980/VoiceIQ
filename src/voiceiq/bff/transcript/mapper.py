"""Explicit DTO-to-Command/Query mapping.

Follows the Explicit Mapping Protocol - no magic auto-mapping.
"""

from __future__ import annotations

from typing import Any

from voiceiq.service.transcript.commands.analyze_post_call import AnalyzePostCallCommand
from voiceiq.service.transcript.queries.get_transcript_detail import GetTranscriptDetailQuery

from .request_dto import EndCallRequest
from .response_dto import TranscriptDetailResponse


def map_end_call_to_command(
    tenant_id: str,
    request: EndCallRequest,
) -> AnalyzePostCallCommand:
    """Map EndCallRequest DTO to AnalyzePostCallCommand."""
    return AnalyzePostCallCommand(
        tenant_id=tenant_id,
        call_id=request.call_id,
        transcript_json=request.transcript_json,
        duration_seconds=request.duration_seconds,
        word_count=request.to_word_count(),
        turn_count=request.to_turn_count(),
        dry_run=request.dry_run,
    )


def map_query_by_call_id(tenant_id: str, call_id: str) -> GetTranscriptDetailQuery:
    """Map path params to GetTranscriptDetailQuery."""
    return GetTranscriptDetailQuery(
        tenant_id=tenant_id,
        call_id=call_id,
    )


def map_db_row_to_response(data: dict[str, Any]) -> TranscriptDetailResponse:
    """Map DB result dict to TranscriptDetailResponse DTO."""
    return TranscriptDetailResponse(**data)
