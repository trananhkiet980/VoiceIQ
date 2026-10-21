"""Application settings loaded from environment."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """VoiceIQ application configuration."""

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost/voiceiq"

    # AI Provider — choose "ollama" | "openai" | "gemini"
    AI_PROVIDER: str = "ollama"
    OLLAMA_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:14b"
    OPENAI_API_KEY: str = ""   # Optional: fallback to OpenAI
    GEMINI_API_KEY: str = ""   # Optional: fallback to Gemini

    # AI Behaviour
    AI_OUTPUT_LANGUAGE: str = "VI"   # "VI" or "EN"
    AI_PIPELINE_MODE: str = "LLM_ONLY"  # "LLM_ONLY" or "COMPOSITE"

    # App
    ENVIRONMENT: str = "local"   # "local" | "staging" | "production"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Dev helpers
    MOCK_TENANT_ID: str = "00000000-0000-0000-0000-000000000001"

    model_config = {"env_file": ".env", "extra": "ignore"}


# Singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get application settings singleton."""
    global _settings  # noqa: PLW0603
    if _settings is None:
        _settings = Settings()
    return _settings
