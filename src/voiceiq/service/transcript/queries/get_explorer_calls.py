"""Query Handler: Get Explorer Calls.

Returns formatted list of calls for Explorer UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..ports.transcript_repo_port import ITranscriptRepoPort


@dataclass(frozen=True)
class GetExplorerCallsQuery:
    """Query for retrieving explorer calls."""

    tenant_id: str
    intent_filter: str = ""
    min_score: float = 0.0
    max_score: float = 999.0
    status_filter: str = "all"


class GetExplorerCallsHandler:
    """Handler for explorer calls query."""

    def __init__(self, transcript_repo_port: ITranscriptRepoPort) -> None:
        self._repo = transcript_repo_port

    async def handle(self, query: GetExplorerCallsQuery) -> list[dict[str, Any]]:
        """Execute query and format data for UI."""
        raw_data = await self._repo.get_explorer_calls(
            tenant_id=query.tenant_id,
            status_filter=query.status_filter,
        )

        data = []
        for row in raw_data:
            trans = row["transcript"]
            anal = row["call_analysis"]
            score = row["call_score"]

            # Filter by score
            if score:
                if not (query.min_score <= score["total_score"] <= query.max_score):
                    continue
            elif query.min_score > 0.0:
                continue

            # Extract main intent
            main_intent = "Chưa xác định"
            intent_color = "bg-slate-500/15 text-slate-400"
            if anal and anal.get("intents") and len(anal["intents"]) > 0:
                intents = anal["intents"]
                primary = next((i for i in intents if i.get("is_primary")), intents[0])
                label = primary.get("display_name") or primary.get("label") or "Unknown"
                main_intent = str(label)

                label_lower = main_intent.lower()
                if "chốt" in label_lower or "đăng ký" in label_lower or "thành công" in label_lower:
                    intent_color = "bg-emerald-500/15 text-emerald-400"
                elif "từ chối" in label_lower or "thất bại" in label_lower:
                    intent_color = "bg-rose-500/15 text-rose-400"
                elif "nuôi" in label_lower or "follow" in label_lower or "tiềm năng" in label_lower:
                    intent_color = "bg-amber-500/15 text-amber-400"
                else:
                    intent_color = "bg-indigo-500/15 text-indigo-400"

            # Apply intent filter
            if query.intent_filter and query.intent_filter.lower() != "all intents":
                if query.intent_filter.lower() not in main_intent.lower():
                    continue

            # Extract NBA
            nba_text = ""
            nba_priority = ""
            nba_deadline = ""
            if anal and anal.get("extracted_fields") and isinstance(anal["extracted_fields"], dict):
                sapp = anal["extracted_fields"].get("sapp_analysis", {})
                nbas = sapp.get("next_best_actions", [])
                if nbas and len(nbas) > 0:
                    nba_val = nbas[0]
                    if isinstance(nba_val, dict):
                        nba_text = nba_val.get("title", "") or nba_val.get("name", "") or str(nba_val)
                        nba_priority = nba_val.get("priority", "")
                        nba_deadline = nba_val.get("deadline", "")
                    else:
                        nba_text = str(nba_val)

            pipeline_ver = anal.get("pipeline_version") if anal else "N/A"
            status = "processed" if anal else "pending"

            data.append({
                "call_id": trans["call_id"],
                "tenant_id": trans["tenant_id"][:8],
                "pipeline_version": pipeline_ver,
                "agent_talk_percentage": 0.0,
                "qa_score": score["total_score"] if score else 0.0,
                "main_intent": main_intent,
                "intent_color": intent_color,
                "nba": nba_text,
                "nba_priority": nba_priority,
                "nba_deadline": nba_deadline,
                "status": status,
                "created_at": trans["created_at"],
                "analysis_created_at": anal.get("created_at") if anal else None,
                "duration": trans["duration_seconds"] or 0.0,
                "turn_count": trans["turn_count"] or 0,
                "title": f"Call Data #{str(trans['call_id'])[:6].upper()}"
            })

        return data
