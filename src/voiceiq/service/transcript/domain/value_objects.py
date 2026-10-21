"""Domain value objects and enums - pure Python.

This module MUST NOT import any framework.
"""

from __future__ import annotations

from enum import StrEnum


class SentimentLabel(StrEnum):
    """Sentiment classification labels."""

    POSITIVE = "Positive"
    NEUTRAL = "Neutral"
    NEGATIVE = "Negative"


class EmotionLabel(StrEnum):
    """Emotion classification labels."""

    ANGER = "anger"
    UNHAPPY = "unhappy"
    MID_PRIORITY = "mid_priority"
    NORMAL = "normal"


class EndcallStatus(StrEnum):
    """Call conclusion status."""

    SATISFY = "satisfy"
    NORMAL = "normal"
    BAD = "bad"


class Speaker(StrEnum):
    """Call participant roles."""

    AGENT = "agent"
    CUSTOMER = "customer"


class SentimentTrend(StrEnum):
    """Trend of customer sentiment over the call."""

    IMPROVED = "Cải thiện"
    UNCHANGED = "Giữ nguyên"
    WORSENED = "Xấu đi"
    UNKNOWN = "Không rõ"


class LeadInterestLevel(StrEnum):
    """Customer interest level (hot, warm, cold)."""

    HOT = "Nóng"
    WARM = "Ấm"
    COLD = "Lạnh"
    UNKNOWN = "Không rõ"


class CallOutcome(StrEnum):
    """Final outcome of the call."""

    CLOSED_WON = "Chốt đăng ký"
    FOLLOW_UP = "Hẹn tư vấn tiếp"
    NURTURE = "Follow-up / Nuôi lead"
    REJECTED = "Từ chối"
    UNREACHABLE = "Không liên lạc được"
    ESCALATED = "Chuyển bộ phận khác"
    UNKNOWN = "Không rõ"


class ObjectionType(StrEnum):
    """Common customer objections."""

    PRICE = "Giá cao"
    TIME = "Chưa có thời gian"
    AUTHORITY = "Cần bàn với gia đình"
    PROCRASTINATION = "Để suy nghĩ thêm"
    COMPETITION = "So sánh trung tâm khác"
    UNCERTAINTY = "Chưa chắc chọn chứng chỉ"
    LACK_OF_CONFIDENCE = "Lo không theo được"
    NONE = "Không có"
    UNKNOWN = "Khác"

# NOTE: Topics and Intents are dynamically loaded from DB per tenant_id to support multi-tenancy.


# Confidence threshold for Active Learning
CONFIDENCE_THRESHOLD: float = 0.7
