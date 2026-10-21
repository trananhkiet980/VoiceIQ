"""Domain logic for PII masking."""

from __future__ import annotations


def mask_pii(value: str, pattern: str | None) -> str:
    """Mask a string value according to the specified PII pattern.

    Supported patterns:
    - `***{last4}`: Mask all but the last 4 characters.
    - `{first1}***`: Keep the first character, mask the rest (handles names,
    keeps first letter of each word if possible, or just the very first letter).
    - `[REDACTED]`: Replace entirely.

    If pattern is None or unrecognized, defaults to `[REDACTED]`.
    """
    if not value:
        return value

    if not pattern:
        return "[REDACTED]"

    pattern = pattern.strip()

    if pattern == "[REDACTED]":
        return "[REDACTED]"

    if pattern == "***{last4}":
        if len(value) <= 4:
            return "***" + value
        return "***" + value[-4:]

    if pattern == "{first1}***":
        # For names, it's often better to mask per word
        words = value.split()
        if len(words) > 1:
            masked_words = [w[0] + "***" if len(w) > 0 else w for w in words]
            return " ".join(masked_words)
        else:
            if len(value) <= 1:
                return value + "***"
            return value[0] + "***"

    # Default fallback
    return "[REDACTED]"
