"""Composition Root - Manual Dependency Injection."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from voiceiq.infrastructure.db.engine import create_db_engine, create_session_factory
from voiceiq.service.transcript.commands.analyze_post_call import AnalyzePostCallHandler
from voiceiq.service.transcript.commands.save_realtime_turn import SaveRealtimeTurnHandler
from voiceiq.service.transcript.infra.ai_adapters.ollama_full_adapter import OllamaFullAdapter
from voiceiq.service.transcript.infra.db_adapters.file_outbox_repo import FileOutboxRepo
from voiceiq.service.transcript.infra.db_adapters.sqlalchemy_transcript_repo import (
    SqlAlchemyTranscriptRepo,
)
from voiceiq.service.transcript.queries.get_active_topics_intents import (
    GetActiveTopicsIntentsHandler,
)
from voiceiq.service.transcript.queries.get_explorer_calls import GetExplorerCallsHandler
from voiceiq.service.transcript.queries.get_transcript_detail import GetTranscriptDetailHandler

from .settings import get_settings


class Container:
    """DI Container - manages lifecycle of all adapters and handlers."""

    def __init__(self) -> None:
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None

        # AI adapter (single Ollama adapter replaces all old gateway adapters)
        self._ai_adapter: OllamaFullAdapter | None = None

        # DB adapters
        self._transcript_repo: SqlAlchemyTranscriptRepo | None = None
        self._outbox_repo: FileOutboxRepo | None = None

    async def init(self) -> None:
        """Initialize all resources."""
        settings = get_settings()

        # Database
        self._engine = create_db_engine(settings.DATABASE_URL)
        self._session_factory = create_session_factory(self._engine)

        # AI adapter — Ollama local LLM (Qwen, Llama, etc.)
        self._ai_adapter = OllamaFullAdapter(
            api_url=settings.OLLAMA_URL,
            default_model=settings.OLLAMA_MODEL,
        )

        # DB adapters
        self._transcript_repo = SqlAlchemyTranscriptRepo(self._session_factory)
        self._outbox_repo = FileOutboxRepo()

    async def shutdown(self) -> None:
        """Cleanup resources."""
        if self._engine:
            await self._engine.dispose()

    # --- Handler factories ---

    def get_analyze_post_call_handler(self) -> AnalyzePostCallHandler:
        """Create handler for post-call analysis."""
        assert self._ai_adapter is not None
        assert self._transcript_repo is not None
        return AnalyzePostCallHandler(
            ai_full_port=self._ai_adapter,
            transcript_repo_port=self._transcript_repo,
        )

    def get_save_realtime_turn_handler(self) -> SaveRealtimeTurnHandler:
        """Create handler for saving realtime turns."""
        assert self._ai_adapter is not None
        assert self._transcript_repo is not None
        return SaveRealtimeTurnHandler(
            ai_full_port=self._ai_adapter,
            repo_port=self._transcript_repo,
        )

    def get_transcript_detail_handler(self) -> GetTranscriptDetailHandler:
        """Create handler for querying transcript details."""
        assert self._transcript_repo is not None
        return GetTranscriptDetailHandler(
            transcript_repo_port=self._transcript_repo,
        )

    def get_explorer_calls_handler(self) -> GetExplorerCallsHandler:
        """Create handler for querying explorer calls."""
        assert self._transcript_repo is not None
        return GetExplorerCallsHandler(
            transcript_repo_port=self._transcript_repo,
        )

    def get_active_topics_intents_handler(self) -> GetActiveTopicsIntentsHandler:
        """Create handler for querying active topics and intents."""
        assert self._transcript_repo is not None
        return GetActiveTopicsIntentsHandler(
            transcript_repo_port=self._transcript_repo,
        )

    @property
    def outbox_repo(self) -> FileOutboxRepo:
        assert self._outbox_repo is not None
        return self._outbox_repo
