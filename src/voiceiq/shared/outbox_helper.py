"""Helper for building Transactional Outbox events."""

from __future__ import annotations

import uuid
from typing import Any


def build_outbox_event(
    *,
    tenant_id: str,
    event_name: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Build a standardized outbox event dict."""
    return {
        "tenant_id": tenant_id,
        "event_id": str(uuid.uuid4()),
        "event_name": event_name,
        "aggregate_type": aggregate_type,
        "aggregate_id": aggregate_id,
        "payload": payload,
        "status": "pending",
        "attempts": 0,
    }
