"""Heuristics rules for aggregating turn-by-turn labels into call-level labels."""

from collections import defaultdict
from typing import Any


def aggregate_labels_from_turns(
    message_analyses: list[dict[str, Any]], min_confidence: float = 0.5
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Calculate heuristic voting for overall call topics and intents based on SAPP turn-by-turn rules.
    """
    topic_weights: dict[str, float] = defaultdict(float)

    total_turns = len(message_analyses)
    ignore_topics = {"Filler", "Khác", "Unknown", "None", "", None, "Xã giao & Off-topic"}

    # Track intents for priority logic
    found_intents = set()

    for idx, turn in enumerate(message_analyses):
        conf = float(turn.get("confidence_score") or 0.0)
        if conf < min_confidence:
            continue

        # Topic: Weight by duration
        t_label = str(turn.get("topic_label") or "")
        start = float(turn.get("start_time") or 0.0)
        end = float(turn.get("end_time") or 0.0)
        duration = max(end - start, 1.0) # minimal 1s weight

        if t_label not in ignore_topics:
            topic_weights[t_label] += duration

        # Intent collection
        i_label = str(turn.get("intent_label") or "")
        if i_label and i_label not in {"Filler", "Khác", "Unknown", "None", "Xã giao & Off-topic"}:
            found_intents.add(i_label)

    # 1. Topic Aggregation (Top 3 by duration)
    def get_top_topics(weights_dict: dict[str, float], k: int = 3) -> list[dict[str, Any]]:
        if not weights_dict:
            return []
        sorted_items = sorted(weights_dict.items(), key=lambda x: x[1], reverse=True)
        top_k_items = sorted_items[:k]

        total_weight = sum(weights_dict.values())
        results: list[dict[str, Any]] = []
        for i, (label, weight) in enumerate(top_k_items):
            # Normalize confidence based on duration share
            conf = min(weight / total_weight + 0.5, 0.99) if total_weight > 0 else 0.5
            results.append({"label": label, "confidence": round(conf, 4), "is_primary": (i == 0)})
        return results

    top_topics = get_top_topics(topic_weights, k=3)

    # 2. Intent Priority Aggregation (SAPP Rule 6.2)
    final_intent_label = "Unknown"

    if "Yêu cầu đăng ký" in found_intents or "Chốt sale" in found_intents:
        final_intent_label = "Chốt đăng ký"
    elif "Khiếu nại" in found_intents or "Yêu cầu hoàn tiền" in found_intents:
        final_intent_label = "Khiếu nại"
    elif "Hẹn gọi lại" in found_intents or "Xác nhận quan tâm" in found_intents:
        final_intent_label = "Follow-up / Nuôi lead"
    elif any("Từ chối" in i for i in found_intents) or "Trì hoãn quyết định" in found_intents:
        final_intent_label = "Từ chối"
    elif any("Hỏi " in i for i in found_intents) or "Tư vấn" in found_intents:
        final_intent_label = "Tư vấn thông tin"

    top_intents = []
    if final_intent_label != "Unknown":
        top_intents.append({
            "label": final_intent_label,
            "confidence": 0.99,
            "is_primary": True
        })

    return top_topics, top_intents

def generate_dynamic_summary(
    templates: list[Any],
    summary: dict[str, Any],
    qa_score: float,
    objection_handling_rate: float,
    total_objections: int,
    final_intent: str,
    next_best_actions: list[dict[str, Any]],
    agent_talk_ratio: float,
    call_analysis_topics: list[dict[str, Any]],
    overall_sentiment: str,
    sentiment_trend: str,
    has_over_promise: bool,
    missed_qa: list[str],
    call_analysis_intents: list[dict[str, Any]] = None,
    intent_transitions: list[dict[str, Any]] = None
) -> str:
    """Generate the markdown summary string dynamically using templates from DB."""

    primary_topics = [t.get("label", "") for t in call_analysis_topics if t.get("is_primary")]
    secondary_topics = [t.get("label", "") for t in call_analysis_topics if not t.get("is_primary")]

    # 1. Headline / Call Outcome
    resolution_text = str(summary.get('resolution', final_intent))
    lines = []

    if next_best_actions:
        first_act = next_best_actions[0]
        priority_emoji = "🔴" if first_act.get("priority") == "Cao" else "🟡"
        icon = "🛠️ TASK" if first_act.get("type") == "task" else "🎓 COACHING"
        priority_text = first_act.get("priority", "Trung bình")

        lines.append(f"## 🎯 Hướng xử lý tiếp theo: {priority_emoji} [{icon}] {first_act.get('title', '')}")
        lines.append(f"*(Mức độ: {priority_text})*")
    else:
        lines.append(f"## 🎯 Hướng xử lý tiếp theo: **{resolution_text}**")

    lines.append("")

    # 2. Executive Summary (from LLM)
    lines.append("### 📝 Tóm tắt nhanh")
    lines.append(f"- **Vấn đề / Nhu cầu:** {str(summary.get('issue', 'Không có thông tin'))}")

    if next_best_actions:
        for act in next_best_actions:
            action_text = act.get('action') or act.get('title')
            lines.append(f"- **Hành động (NBA):** {action_text}")
    elif summary.get('next_steps'):
        lines.append(f"- **Hành động (NBA):** {str(summary.get('next_steps', ''))}")

    lines.append("")

    # 4. Topic Classification
    lines.append("### 🏷️ Phân loại Chủ đề & Mục đích")

    intents = call_analysis_intents or []
    customer_intent = next((t.get("label") for t in intents if t.get("speaker") == "customer"), final_intent)
    agent_intent = next((t.get("label") for t in intents if t.get("speaker") == "agent"), None)

    topics = call_analysis_topics or []
    customer_topic = next((t.get("label") for t in topics if t.get("speaker") == "customer"), ', '.join(primary_topics))
    agent_topic = next((t.get("label") for t in topics if t.get("speaker") == "agent"), None)

    def _format_with_conf(lbl: str | None, speaker: str, items: list[dict[str, Any]]) -> str:
        if not lbl or lbl in ("Unknown", "Không rõ", "KhA'ng rA", "KhA'ng rA"):
            return "Không rõ"
        conf = next((t.get("confidence") for t in items if t.get("speaker") == speaker), None)
        if conf is not None:
            return f"{lbl} ({int(conf * 100)}%)"
        return lbl

    lines.append(f"- **Mục đích của Khách hàng:** {_format_with_conf(customer_intent, 'customer', intents)}")
    lines.append(f"- **Chủ đề KH quan tâm:** {_format_with_conf(customer_topic, 'customer', topics)}")
    lines.append(f"- **Mục đích của Tư vấn viên:** {_format_with_conf(agent_intent, 'agent', intents)}")
    lines.append(f"- **Chủ đề Sale đề cập:** {_format_with_conf(agent_topic, 'agent', topics)}")

    if intent_transitions:
        lines.append("")
        lines.append("### 🔄 Luân chuyển Cuộc gọi (Intent Transitions)")
        for tr in intent_transitions:
            phase = tr.get("phase", "Chuyển tiếp")
            speaker = "👤 Khách" if tr.get("speaker") == "customer" else "🎧 Sale"
            intent = tr.get("intent", "Unknown")
            topic = tr.get("topic", "Unknown")
            lines.append(f"- **{phase}:** {speaker} 👉 {intent} ({topic})")

    return "\n".join(lines)
