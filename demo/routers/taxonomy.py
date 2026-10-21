import uuid

from fastapi import APIRouter, Request
from pydantic import BaseModel
from sqlalchemy import delete, select, update

from voiceiq.app.container import Container
from voiceiq.infrastructure.db.models import IntentTaxonomyModel, TopicRegistryModel

router = APIRouter(prefix="/api/v1/demo/taxonomy", tags=["Taxonomy"])


class TopicDTO(BaseModel):
    label: str
    label_vi: str | None = None
    description_nli: str | None = None
    parent_topic_id: str | None = None
    applicable_speaker: str | None = "both"


class IntentDTO(BaseModel):
    label: str
    display_name_vi: str | None = None
    description_nli: str | None = None
    applicable_speaker: str | None = "both"


@router.get("/{tenant_id}")
async def get_taxonomy(tenant_id: str, request: Request):
    container: Container = request.app.state.container
    session_factory = container._session_factory  # pyright: ignore[reportPrivateUsage]
    assert session_factory is not None
    async with session_factory() as session:
        topics_result = await session.execute(
            select(TopicRegistryModel).where(TopicRegistryModel.tenant_id == uuid.UUID(tenant_id))
        )
        intents_result = await session.execute(
            select(IntentTaxonomyModel).where(IntentTaxonomyModel.tenant_id == uuid.UUID(tenant_id))
        )
        topics = [
            {
                "id": str(t.topic_id),
                "label": t.label,
                "label_vi": t.label_vi,
                "description_nli": t.description_nli,
                "parent_id": str(t.parent_topic_id) if t.parent_topic_id else None,
                "metadata": t.metadata_json or {},
            }
            for t in topics_result.scalars().all()
        ]
        intents = [
            {
                "id": str(i.intent_id),
                "label": i.label,
                "display_name_vi": i.display_name_vi,
                "description_nli": i.description_nli,
                "detection_rules": i.detection_rules or {},
            }
            for i in intents_result.scalars().all()
        ]
        return {"topics": topics, "intents": intents}


@router.post("/{tenant_id}/topics")
async def create_topic(tenant_id: str, data: TopicDTO, request: Request):
    container: Container = request.app.state.container
    session_factory = container._session_factory  # pyright: ignore[reportPrivateUsage]
    assert session_factory is not None
    async with session_factory() as session:
        topic = TopicRegistryModel(
            tenant_id=uuid.UUID(tenant_id),
            label=data.label,
            label_vi=data.label_vi,
            description_nli=data.description_nli,
            parent_topic_id=uuid.UUID(data.parent_topic_id) if data.parent_topic_id else None,
            metadata_json={"applicable_speaker": data.applicable_speaker},
        )
        session.add(topic)
        await session.commit()
        return {"status": "success", "id": str(topic.topic_id)}


@router.put("/{tenant_id}/topics/{topic_id}")
async def update_topic(tenant_id: str, topic_id: str, data: TopicDTO, request: Request):
    container: Container = request.app.state.container
    session_factory = container._session_factory  # pyright: ignore[reportPrivateUsage]
    assert session_factory is not None
    async with session_factory() as session:
        stmt = (
            update(TopicRegistryModel)
            .where(
                TopicRegistryModel.topic_id == uuid.UUID(topic_id), TopicRegistryModel.tenant_id == uuid.UUID(tenant_id)
            )
            .values(
                label=data.label,
                label_vi=data.label_vi,
                description_nli=data.description_nli,
                parent_topic_id=uuid.UUID(data.parent_topic_id) if data.parent_topic_id else None,
                metadata_json={"applicable_speaker": data.applicable_speaker},
            )
        )
        await session.execute(stmt)
        await session.commit()
        return {"status": "success"}


@router.delete("/{tenant_id}/topics/{topic_id}")
async def delete_topic(tenant_id: str, topic_id: str, request: Request):
    container: Container = request.app.state.container
    session_factory = container._session_factory  # pyright: ignore[reportPrivateUsage]
    assert session_factory is not None
    async with session_factory() as session:
        stmt = delete(TopicRegistryModel).where(
            TopicRegistryModel.topic_id == uuid.UUID(topic_id), TopicRegistryModel.tenant_id == uuid.UUID(tenant_id)
        )
        await session.execute(stmt)
        await session.commit()
        return {"status": "success"}


@router.post("/{tenant_id}/intents")
async def create_intent(tenant_id: str, data: IntentDTO, request: Request):
    container: Container = request.app.state.container
    session_factory = container._session_factory  # pyright: ignore[reportPrivateUsage]
    assert session_factory is not None
    async with session_factory() as session:
        intent = IntentTaxonomyModel(
            tenant_id=uuid.UUID(tenant_id),
            label=data.label,
            display_name_vi=data.display_name_vi,
            description_nli=data.description_nli,
            detection_rules={"applicable_speaker": data.applicable_speaker},
        )
        session.add(intent)
        await session.commit()
        return {"status": "success", "id": str(intent.intent_id)}


@router.put("/{tenant_id}/intents/{intent_id}")
async def update_intent(tenant_id: str, intent_id: str, data: IntentDTO, request: Request):
    container: Container = request.app.state.container
    session_factory = container._session_factory  # pyright: ignore[reportPrivateUsage]
    assert session_factory is not None
    async with session_factory() as session:
        stmt = (
            update(IntentTaxonomyModel)
            .where(
                IntentTaxonomyModel.intent_id == uuid.UUID(intent_id),
                IntentTaxonomyModel.tenant_id == uuid.UUID(tenant_id),
            )
            .values(
                label=data.label,
                display_name_vi=data.display_name_vi,
                description_nli=data.description_nli,
                detection_rules={"applicable_speaker": data.applicable_speaker},
            )
        )
        await session.execute(stmt)
        await session.commit()
        return {"status": "success"}


@router.delete("/{tenant_id}/intents/{intent_id}")
async def delete_intent(tenant_id: str, intent_id: str, request: Request):
    container: Container = request.app.state.container
    session_factory = container._session_factory  # pyright: ignore[reportPrivateUsage]
    assert session_factory is not None
    async with session_factory() as session:
        stmt = delete(IntentTaxonomyModel).where(
            IntentTaxonomyModel.intent_id == uuid.UUID(intent_id), IntentTaxonomyModel.tenant_id == uuid.UUID(tenant_id)
        )
        await session.execute(stmt)
        await session.commit()
        return {"status": "success"}
