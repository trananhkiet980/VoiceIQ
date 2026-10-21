from typing import Any, Literal

from fastapi import APIRouter, Request

from voiceiq.app.container import Container

router = APIRouter(prefix="/api/v1/demo", tags=["Labels"])


@router.get("/all-labels")
async def get_all_labels(
    request: Request, label_format: Literal["FULL", "ONLY_LABEL", "ONLY_DESC"] = "FULL"
) -> list[dict[str, Any]]:
    container: Container = request.app.state.container
    session_factory = container._session_factory  # pyright: ignore[reportPrivateUsage]
    assert session_factory is not None
    from sqlalchemy import select

    from voiceiq.infrastructure.db.models import IntentTaxonomyModel, TopicRegistryModel

    async with session_factory() as session:
        result_topics = await session.execute(
            select(TopicRegistryModel).where(TopicRegistryModel.status == "active")
        )
        all_topics = result_topics.scalars().all()
        result_intents = await session.execute(
            select(IntentTaxonomyModel).where(IntentTaxonomyModel.status == "active")
        )
        all_intents = result_intents.scalars().all()

    grouped_data: dict[str, dict[str, Any]] = {}
    for t in all_topics:
        tid = str(t.tenant_id)
        if tid not in grouped_data:
            grouped_data[tid] = {"tenant_id": tid, "topics": [], "intents": []}
        display_name = t.label_vi or t.label
        if label_format == "ONLY_LABEL":
            desc = f"{display_name}"
        elif label_format == "ONLY_DESC":
            desc = t.description_nli or ""
        else:
            desc = f"{display_name}"
            if t.description_nli:
                desc += f": {t.description_nli}"
        grouped_data[tid]["topics"].append(desc)

    for i in all_intents:
        tid = str(i.tenant_id)
        if tid not in grouped_data:
            grouped_data[tid] = {"tenant_id": tid, "topics": [], "intents": []}
        display_name = i.display_name_vi or i.label
        if label_format == "ONLY_LABEL":
            desc = f"{display_name}"
        elif label_format == "ONLY_DESC":
            desc = i.description_nli or ""
        else:
            desc = f"{display_name}"
            if i.description_nli:
                desc += f": {i.description_nli}"
        grouped_data[tid]["intents"].append(desc)

    return list(grouped_data.values())
