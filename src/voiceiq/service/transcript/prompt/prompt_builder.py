"""Prompt Builder - constructs final prompt for LLM."""

from __future__ import annotations

from typing import Any

from .context_builder import build_call_context, format_transcript_for_prompt
from .prompt_template import POST_CALL_TEMPLATE, PROMPT_VERSION
from .system_prompt import SYSTEM_PROMPT


def build_post_call_prompt(
    *,
    call_id: str,
    duration_seconds: float,
    turn_count: int,
    word_count: int,
    dialog_turns: list[dict[str, Any]],
    channel: str = "phone",
    customer_type: str = "standard",
) -> tuple[str, str, str]:
    """Build complete prompt for post-call analysis.

    Returns:
        Tuple of (system_prompt, user_prompt, prompt_version)
    """
    context = build_call_context(
        call_id=call_id,
        duration_seconds=duration_seconds,
        turn_count=turn_count,
        word_count=word_count,
        channel=channel,
        customer_type=customer_type,
    )

    transcript_text = format_transcript_for_prompt(dialog_turns)

    user_prompt = POST_CALL_TEMPLATE.format(
        context=context,
        transcript=transcript_text,
    )

    return SYSTEM_PROMPT, user_prompt, PROMPT_VERSION
