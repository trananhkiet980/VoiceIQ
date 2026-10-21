"""RFC 7807 Problem Details for HTTP APIs."""

from __future__ import annotations


class ProblemDetailsError(Exception):
    """Standard error following RFC 7807 Problem Details."""

    def __init__(
        self,
        *,
        status: int,
        code: str,
        title: str,
        detail: str,
        trace_id: str = "",
    ) -> None:
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail
        self.trace_id = trace_id
        super().__init__(detail)

    def to_dict(self) -> dict[str, object]:
        return {
            "type": f"https://docs.VoiceIQ.vn/problems/VoiceIQ/{self.code.lower().replace('_', '-')}",
            "title": self.title,
            "status": self.status,
            "detail": self.detail,
            "code": self.code,
            "trace_id": self.trace_id,
        }


# Common error factory functions
def not_found(resource: str, identifier: str, *, trace_id: str = "") -> ProblemDetailsError:
    code = f"{resource.upper()}_NOT_FOUND"
    return ProblemDetailsError(
        status=404,
        code=code,
        title="Resource not found",
        detail=f"{resource} not found",
        trace_id=trace_id,
    )


def invalid_arguments(detail: str, *, trace_id: str = "") -> ProblemDetailsError:
    return ProblemDetailsError(
        status=422,
        code="INVALID_ARGUMENTS",
        title="Invalid arguments",
        detail=detail,
        trace_id=trace_id,
    )


def ai_processing_failed(detail: str, *, trace_id: str = "") -> ProblemDetailsError:
    return ProblemDetailsError(
        status=500,
        code="AI_PROCESSING_FAILED",
        title="AI processing failed",
        detail=detail,
        trace_id=trace_id,
    )
