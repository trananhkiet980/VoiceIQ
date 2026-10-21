"""Token Manager - handles transcript chunking for LLM context window."""

from __future__ import annotations

from typing import Any

# Approximate chars-to-tokens ratio for Vietnamese text
CHARS_PER_TOKEN_ESTIMATE = 3.5
DEFAULT_MAX_TOKENS = 4096


def estimate_token_count(text: str) -> int:
    """Estimate token count for a text string."""
    return int(len(text) / CHARS_PER_TOKEN_ESTIMATE)


def truncate_transcript_if_needed(
    dialog_turns: list[dict[str, Any]],
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> list[dict[str, Any]]:
    """Truncate transcript dialog turns to fit within token limit.

    Strategy: Keep first 20% and last 40% of turns,
    summarize the middle section.
    """
    full_text = " ".join(t.get("text", "") for t in dialog_turns)
    estimated_tokens = estimate_token_count(full_text)

    if estimated_tokens <= max_tokens:
        return dialog_turns

    total = len(dialog_turns)
    keep_start = max(2, int(total * 0.2))
    keep_end = max(3, int(total * 0.4))

    start_turns = dialog_turns[:keep_start]
    end_turns = dialog_turns[-keep_end:]
    skipped = total - keep_start - keep_end

    # Insert a marker for skipped content
    marker: dict[str, Any] = {
        "turn_index": keep_start,
        "speaker": "system",
        "text": f"[... {skipped} lượt thoại ở giữa đã được lược bỏ để tối ưu token ...]",
        "start_time": 0.0,
        "end_time": 0.0,
    }

    return [*start_turns, marker, *end_turns]
