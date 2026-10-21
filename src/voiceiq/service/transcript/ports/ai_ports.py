"""AI Model Ports - Abstract interfaces for specialized AI services."""

from __future__ import annotations

from typing import Any, Protocol


class IAiSummaryPort(Protocol):
    """Port for Generative LLM tasks (e.g. Ollama)."""

    async def generate_summary(self, full_text: str, output_language: str = "VI") -> dict[str, Any]:
        """Generate a summary of the call.
        Returns: {"issue": "...", "resolution": "...", "next_steps": "..."}
        """
        ...


class IAiSentimentPort(Protocol):
    """Port for fast real-time sentiment analysis."""

    async def analyze_sentiment_fast(self, text: str) -> tuple[str, float]:
        """Fast real-time sentiment analysis for a single turn."""
        ...

    async def analyze_sentiment_batch(self, texts: list[str]) -> list[tuple[str, float]]:
        """Batch analyze sentiment for multiple texts."""
        ...


class IAiZeroShotPort(Protocol):
    """Port for Zero-Shot Classification tasks (e.g. GLiClass)."""

    async def classify_text(
        self,
        text: str,
        labels: list[str],
        multi_label: bool = False,
    ) -> list[dict[str, Any]]:
        """Classify a single text into provided labels."""
        ...

    async def classify_text_batch(
        self,
        texts: list[str],
        labels: list[str],
        multi_label: bool = False,
    ) -> list[list[dict[str, Any]]]:
        """Classify a batch of texts into provided labels."""
        ...


class IAiNerPort(Protocol):
    """Port for Named Entity Recognition tasks (e.g. GLiNER)."""

    async def extract_entities(
        self,
        text: str,
        labels: list[str],
    ) -> list[dict[str, Any]]:
        """Extract entities matching the provided labels from text."""
        ...

    async def extract_entities_batch(
        self,
        texts: list[str],
        labels: list[str],
    ) -> list[list[dict[str, Any]]]:
        """Extract entities from a batch of texts."""
        ...


class IAiFullAnalysisPort(Protocol):
    """Abstract port for Full Analysis (LLM_ONLY strategy)."""

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
        """Analyze entire transcript and return a unified AiAnalysisResultContract dict."""
        ...

    async def analyze_qa_nba(
        self,
        transcript_text: str,
        intent_label: str,
        qa_criteria: list[dict[str, Any]],
        call_datetime: str = "",
    ) -> dict[str, Any]:
        """Analyze QA checklist and extract NBA based on the specific intent."""
        ...
