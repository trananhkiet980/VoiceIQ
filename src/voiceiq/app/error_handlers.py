"""Global error handlers for RFC 7807 Problem Details."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from voiceiq.shared.problem_details import ProblemDetailsError


def register_error_handlers(app: FastAPI) -> None:
    """Register global exception handlers."""

    @app.exception_handler(ProblemDetailsError)
    async def problem_details_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: ProblemDetailsError
    ) -> JSONResponse:
        # Inject trace_id from request if available
        if not exc.trace_id:
            exc.trace_id = request.headers.get("x-request-id", "")
        return JSONResponse(
            status_code=exc.status,
            content=exc.to_dict(),
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(  # pyright: ignore[reportUnusedFunction]
        request: Request, exc: Exception
    ) -> JSONResponse:
        trace_id = request.headers.get("x-request-id", "")
        return JSONResponse(
            status_code=500,
            content={
                "type": "https://docs.VoiceIQ.vn/problems/VoiceIQ/internal-error",
                "title": "Internal Server Error",
                "status": 500,
                "detail": "An unexpected error occurred.",
                "code": "INTERNAL_ERROR",
                "trace_id": trace_id,
            },
        )
