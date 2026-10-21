"""Factory for resolving the correct LLM adapter based on model or provider name."""

from __future__ import annotations

import logging
from typing import Any

from voiceiq.service.transcript.ports.ai_ports import IAiFullAnalysisPort
from .gemini_full_adapter import GeminiFullAdapter
from .openai_full_adapter import OpenAIFullAdapter
from .ollama_full_adapter import OllamaFullAdapter

logger = logging.getLogger(__name__)


class AdapterFactory(IAiFullAnalysisPort):
    """Dynamic routing adapter that implements the port and delegates to specific providers."""

    def __init__(
        self,
        gemini_api_key: str = "",
        openai_api_key: str = "",
        ollama_api_url: str = "http://localhost:11434",
        ollama_default_model: str = "qwen2.5:14b",
    ) -> None:
        self.gemini_adapter = GeminiFullAdapter(api_key=gemini_api_key) if gemini_api_key else None
        self.openai_adapter = OpenAIFullAdapter(api_key=openai_api_key) if openai_api_key else None
        self.ollama_adapter = (
            OllamaFullAdapter(api_url=ollama_api_url, default_model=ollama_default_model)
            if ollama_api_url
            else None
        )

    def _get_adapter_for_model(self, model: str | None) -> IAiFullAnalysisPort:
        """Route to the correct adapter based on model name prefix."""
        if not model:
            if self.ollama_adapter:
                return self.ollama_adapter
            if self.openai_adapter:
                return self.openai_adapter
            if self.gemini_adapter:
                return self.gemini_adapter
            raise ValueError("No LLM adapter configured.")

        model_lower = model.lower()
        if "gemini" in model_lower:
            if self.gemini_adapter:
                return self.gemini_adapter
            logger.warning("Gemini requested but not configured, falling back to Ollama")
            if self.ollama_adapter:
                return self.ollama_adapter

        elif "gpt" in model_lower or "o1" in model_lower:
            if self.openai_adapter:
                return self.openai_adapter
            logger.warning("OpenAI requested but not configured, falling back to Ollama")
            if self.ollama_adapter:
                return self.ollama_adapter

        if self.ollama_adapter:
            return self.ollama_adapter
        if self.openai_adapter:
            return self.openai_adapter
        if self.gemini_adapter:
            return self.gemini_adapter

        raise ValueError(f"Could not resolve adapter for model {model}")

    async def analyze_full_transcript(
        self,
        transcript_text: str,
        topic_labels: list[str],
        intent_labels: list[str],
        ner_labels: list[str],
        seed_keywords: list[str],
        output_language: str = "VI",
        model: str | None = None,
        prompt_template: str | None = None,
        qa_criteria: list[dict[str, Any]] | None = None,
        call_datetime: str = "",
    ) -> dict[str, Any]:
        adapter = self._get_adapter_for_model(model)
        return await adapter.analyze_full_transcript(
            transcript_text,
            topic_labels,
            intent_labels,
            ner_labels,
            seed_keywords,
            output_language,
            model,
            prompt_template,
            qa_criteria,
            call_datetime,
        )

    async def analyze_qa_nba(
        self,
        transcript_text: str,
        intent_label: str,
        qa_criteria: list[dict[str, Any]],
        call_datetime: str = "",
    ) -> dict[str, Any]:
        adapter = self._get_adapter_for_model(None)
        return await adapter.analyze_qa_nba(transcript_text, intent_label, qa_criteria, call_datetime)
