"""Query Handler: Get Active Topics and Intents.

Returns active topics and intents for a tenant.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..ports.transcript_repo_port import ITranscriptRepoPort


@dataclass(frozen=True)
class GetActiveTopicsIntentsQuery:
    """Query for retrieving active topics and intents."""

    tenant_id: str
    label_format: str = "FULL"


class GetActiveTopicsIntentsHandler:
    """Handler for active topics and intents query."""

    def __init__(self, transcript_repo_port: ITranscriptRepoPort) -> None:
        self._repo = transcript_repo_port

    async def handle(self, query: GetActiveTopicsIntentsQuery) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Execute query and return formatted topics and intents."""
        active_topics = await self._repo.get_active_topics(query.tenant_id)
        active_intents = await self._repo.get_active_intents(query.tenant_id)

        # Format based on label_format
        if query.label_format != "FULL":
            formatted_topics = []
            for t in active_topics:
                # 'name' contains the original display_name
                name = t.get("name", "")
                # 'label' contains the full string "name: description"
                full_label = t.get("label", "")

                label_val = name
                if query.label_format == "ONLY_LABEL":
                    label_val = name
                elif query.label_format == "ONLY_DESC":
                    # Extract description from full_label if possible, or just use full_label
                    if ": " in full_label:
                        label_val = full_label.split(": ", 1)[1]
                    else:
                        label_val = full_label

                formatted_topics.append({
                    "id": t.get("id"),
                    "label": label_val,
                    "parent_id": t.get("parent_id"),
                    "metadata": t.get("metadata", {}),
                })

            formatted_intents = []
            for i in active_intents:
                name = i.get("name", "")
                full_label = i.get("label", "")

                label_val = name
                if query.label_format == "ONLY_LABEL":
                    label_val = name
                elif query.label_format == "ONLY_DESC":
                    if ": " in full_label:
                        label_val = full_label.split(": ", 1)[1]
                    else:
                        label_val = full_label

                formatted_intents.append({
                    "id": i.get("id"),
                    "label": label_val,
                    "detection_rules": i.get("detection_rules", {}),
                })

            return formatted_topics, formatted_intents

        return active_topics, active_intents
