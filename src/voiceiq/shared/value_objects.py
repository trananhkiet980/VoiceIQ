"""Shared value object types."""

from __future__ import annotations

from typing import NewType

TenantId = NewType("TenantId", str)
TranscriptId = NewType("TranscriptId", str)
CallId = NewType("CallId", str)
UserId = NewType("UserId", str)
RequestId = NewType("RequestId", str)
