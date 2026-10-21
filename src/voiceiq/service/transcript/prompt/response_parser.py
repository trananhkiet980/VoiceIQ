"""Response Parser - extracts and validates JSON from LLM output."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, cast

logger = logging.getLogger(__name__)


def parse_llm_response(raw_response: str) -> dict[str, Any]:
    """Parse LLM response and extract JSON.

    Handles common LLM output formats:
    - Pure JSON
    - JSON wrapped in markdown code blocks
    - JSON with explanatory text before/after

    Raises:
        ValueError: If no valid JSON found in response.
    """
    cleaned = raw_response.strip()

    # Try direct JSON parse first
    try:
        result = json.loads(cleaned)
        if isinstance(result, dict):
            return cast(dict[str, Any], result)
    except json.JSONDecodeError:
        pass

    # Try extracting JSON from markdown code block
    code_block_pattern = r"```(?:json)?\s*\n?(\{.*?\})\s*\n?```"
    match = re.search(code_block_pattern, cleaned, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group(1))
            if isinstance(result, dict):
                return cast(dict[str, Any], result)
        except json.JSONDecodeError:
            pass

    # Try finding first { ... } block
    brace_pattern = r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})"
    match = re.search(brace_pattern, cleaned, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group(1))
            if isinstance(result, dict):
                return cast(dict[str, Any], result)
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Failed to extract valid JSON from LLM response: {cleaned[:200]}")


def validate_required_fields(data: dict[str, Any]) -> list[str]:
    """Validate that required fields exist in parsed AI response.

    Returns list of missing field names (empty if all present).
    """
    required_fields = [
        "sentiment_overall",
        "emotion_overall",
        "endcall_status",
        "confidence_score",
        "topics",
        "summary",
    ]
    missing = [f for f in required_fields if f not in data]
    return missing
