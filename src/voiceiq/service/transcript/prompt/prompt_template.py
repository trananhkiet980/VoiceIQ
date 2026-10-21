"""Prompt templates with version management."""

from __future__ import annotations

PROMPT_VERSION = "v1"

POST_CALL_TEMPLATE = """\
## Thông tin cuộc gọi
{context}

## Nội dung hội thoại
{transcript}

## Yêu cầu
Phân tích toàn diện cuộc gọi trên và trả về kết quả JSON theo schema đã quy định.
"""

REALTIME_COACHING_TEMPLATES: dict[str, str] = {
    "Negative": "💡 Gợi ý: Hãy thể hiện sự đồng cảm với khách hàng. Ví dụ: ",
    "anger": "⚠️ Cảnh báo: Khách hàng đang rất tức giận. Hãy giữ bình tĩnh, lắng nghe và xin lỗi chân thành.",
    "unhappy": "💡 Gợi ý: Khách hàng không hài lòng. Hãy chủ động đề xuất giải pháp cụ thể.",
}
