"""Context Builder - assembles call context for LLM prompt."""

from __future__ import annotations

from typing import Any


def build_call_context(
    *,
    call_id: str,
    duration_seconds: float,
    turn_count: int,
    word_count: int,
    channel: str = "phone",
    customer_type: str = "standard",
) -> str:
    """Build formatted context string for the LLM prompt."""
    lines = [
        f"- Mã cuộc gọi: {call_id}",
        f"- Thời lượng: {duration_seconds:.0f} giây",
        f"- Số lượt thoại: {turn_count}",
        f"- Số từ: {word_count}",
        f"- Kênh: {channel}",
        f"- Loại khách hàng: {customer_type}",
    ]
    return "\n".join(lines)


def format_transcript_for_prompt(
    dialog_turns: list[dict[str, Any]],
) -> str:
    """Format dialog turns into readable text for LLM."""
    lines: list[str] = []
    for turn in dialog_turns:
        speaker = turn.get("speaker", "unknown")
        text = turn.get("text", "")
        role = "Nhân viên" if speaker == "agent" else "Khách hàng"
        lines.append(f"{role}: {text}")
    return "\n".join(lines)
