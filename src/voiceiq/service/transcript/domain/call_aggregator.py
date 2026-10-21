"""Call Aggregator - Aggregates turn-by-turn data into Call-level outcomes for VoiceIQ."""

from .value_objects import CallOutcome, SentimentTrend


def determine_final_intent(intents_list: list[str]) -> CallOutcome:
    """Determine final outcome based on SAPP priority (Chốt đăng ký > Hẹn tư vấn tiếp > ...)."""
    priorities = {
        CallOutcome.CLOSED_WON.value: 1,
        CallOutcome.FOLLOW_UP.value: 2,
        CallOutcome.NURTURE.value: 3,
        CallOutcome.ESCALATED.value: 4,
        CallOutcome.REJECTED.value: 5,
        CallOutcome.UNREACHABLE.value: 6,
    }

    best_intent = CallOutcome.UNKNOWN
    best_priority = 999

    for intent in intents_list:
        prio = priorities.get(intent, 999)
        if prio < best_priority:
            best_priority = prio
            try:
                best_intent = CallOutcome(intent)
            except ValueError:
                pass

    return best_intent

def determine_sentiment_trend(sentiments: list[str]) -> SentimentTrend:
    """Determine the trend comparing first half and second half of call."""
    if not sentiments:
        return SentimentTrend.UNKNOWN

    if len(sentiments) < 3:
        return SentimentTrend.UNCHANGED

    first_half = sentiments[:len(sentiments)//2]
    second_half = sentiments[len(sentiments)//2:]

    first_neg = sum(1 for s in first_half if s.lower() == "negative")
    second_neg = sum(1 for s in second_half if s.lower() == "negative")
    first_pos = sum(1 for s in first_half if s.lower() == "positive")
    second_pos = sum(1 for s in second_half if s.lower() == "positive")

    if second_neg < first_neg or second_pos > first_pos:
        return SentimentTrend.IMPROVED
    elif second_neg > first_neg or second_pos < first_pos:
        return SentimentTrend.WORSENED

    return SentimentTrend.UNCHANGED
