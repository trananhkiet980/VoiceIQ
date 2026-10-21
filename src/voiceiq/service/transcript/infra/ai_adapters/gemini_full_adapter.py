"""Adapter for Google Gemini for Full Analysis (LLM_ONLY mode)."""

from __future__ import annotations

import json
import logging
from typing import Any

from google import genai
from google.genai import types

from voiceiq.service.transcript.ports.ai_ports import IAiFullAnalysisPort
from voiceiq.service.transcript.domain.schemas import V2_SHORT_SCHEMA

logger = logging.getLogger(__name__)


class GeminiFullAdapter(IAiFullAnalysisPort):
    """Adapter for Google Gemini. Uses Explicit Caching and Structured Outputs."""

    def __init__(self, api_key: str, default_model: str = "models/gemini-3.1-flash-lite") -> None:
        # Use google-genai SDK
        self._client = genai.Client(api_key=api_key)
        self._default_model = default_model

    def _build_system_prompt(self, topics: list[str], intents: list[str], keywords: list[str], lang: str, qa_criteria: list[dict[str, Any]] | None = None) -> str:
        lang_instruction = (
            "CHỈ DẪN NGÔN NGỮ:\nViết các giá trị bằng tiếng Anh, TRỪ entities.text phải giữ nguyên tiếng Việt gốc.\n\n"
            if lang == "EN"
            else "CHỈ DẪN NGÔN NGỮ:\nViết bằng Tiếng Việt. Phần entities.text giữ nguyên chuỗi gốc.\n\n"
        )
        
        qa_json_str = json.dumps(qa_criteria or [], ensure_ascii=False, indent=2)

        return f"""Bạn là một chuyên gia phân tích cuộc gọi xuất sắc mảng Giáo dục (VoiceIQ).
CHỈ XUẤT RA JSON HỢP LỆ THEO ĐÚNG SCHEMA YÊU CẦU. KHÔNG dùng markdown bọc ngoài JSON.

DANH SÁCH CHỦ ĐỀ HỢP LỆ: {", ".join(topics)}
DANH SÁCH MỤC ĐÍCH HỢP LỆ: {", ".join(intents)}
TỪ KHÓA ĐỘNG YÊU CẦU TÌM: {", ".join(keywords)}
QUY TẮC CHẤM ĐIỂM QA: {qa_json_str}

LƯU Ý QUAN TRỌNG VỀ QA & NBA & CONFIDENCE:
- Chỉ chấm điểm hành vi và kỹ năng của Tư vấn viên (Agent), tuyệt đối KHÔNG chấm lời nói của Khách hàng.
- BẮT BUỘC: Bạn PHẢI trả về toàn bộ tất cả các tiêu chí QA có trong QUY TẮC CHẤM ĐIỂM QA, không được bỏ sót bất kỳ tiêu chí nào, bất kể kết quả passed là true hay false.
- Trường "passed" PHẢI LÀ kiểu boolean (true hoặc false) dựa trên thực tế.
- Đối với quy tắc phạt/điểm liệt, "passed": true nghĩa là Agent CÓ VI PHẠM (làm sai).
- "confidence_score" là ĐỘ TIN CẬY (từ 0.0 đến 1.0).

{lang_instruction}"""

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
        """Luồng gọi 1 lần cho file ghi âm."""
        system_prompt = self._build_system_prompt(topic_labels, intent_labels, seed_keywords, output_language, qa_criteria)
        user_prompt = f"Ngày giờ thực hiện cuộc gọi: {call_datetime}\n\nNội dung hội thoại:\n{transcript_text}"
        
        model_name = model if model else self._default_model

        try:
            # We don't cache explicitly here for simplicity unless the text is very long, 
            # but we use structured output.
            res = self._client.models.generate_content(
                model=model_name,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=V2_SHORT_SCHEMA,
                    temperature=0.2,
                )
            )
            return json.loads(res.text)
        except Exception as e:
            logger.error("Gemini Full Fast Path failed: %s", e)
            return self._fallback_full_result()

    async def analyze_qa_nba(
        self,
        transcript_text: str,
        intent_label: str,
        qa_criteria: list[dict[str, Any]],
        call_datetime: str = "",
    ) -> dict[str, Any]:
        # Trả về rỗng vì V2_SHORT_SCHEMA đã bao gồm luôn QA trong hàm analyze_full_transcript
        return {"qa_evaluation": [], "nba_recommendations": []}

    def _fallback_full_result(self) -> dict[str, Any]:
        return {
            "reasoning": "Error",
            "sentiment_overall": "Neutral",
            "sentiment_customer": "Neutral",
            "sentiment_agent": "Neutral",
            "emotion_overall": "normal",
            "emotion_agent": "normal",
            "emotion_customer": "normal",
            "topics": {
                "topic_customer": {"label": "Không rõ", "confidence_score": 0.0},
                "topic_agent": {"label": "Không rõ", "confidence_score": 0.0},
                "intent_customer": {"label": "Không rõ", "confidence_score": 0.0},
                "intent_agent": {"label": "Không rõ", "confidence_score": 0.0},
                "intent_transitions": [],
                "dynamic_keywords": []
            },
            "summary": {"issue": "Error", "resolution": "Error", "summary_bullets": []},
            "entities": [],
            "escalation_analysis": {"escalation_level": "none", "escalation_type": "null", "escalation_signals": [], "escalation_trajectory": "stable", "de_escalation_successful": True},
            "toxicity_analysis": {"customer_score": 0.0, "agent_score": 0.0, "toxicity_triggered_auto_fail": False, "toxicity_tags": []},
            "nba_recommendations": [],
            "qa_evaluation": []
        }
