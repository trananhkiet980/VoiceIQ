"""Dynamic Scoring Engine & VoiceIQ Rule Engine."""

from typing import Any


def evaluate_qa_compliance(speaker: str, intent_label: str, qa_checklist_intents: list[str]) -> bool:
    """Check if the current turn satisfies a QA checklist item."""
    if str(speaker).lower() != "agent":
        return False
    if not intent_label:
        return False
    return intent_label in qa_checklist_intents

class DynamicScoringEngine:
    """Evaluates transcripts against dynamic scorecards from the database."""

    def __init__(self, scorecard: dict[str, Any]):
        self.scorecard = scorecard

    def evaluate(self, message_analyses: list[dict[str, Any]]) -> dict[str, Any]:
        """Evaluate a call and return scores, bands, and triggered coaching."""
        if not self.scorecard:
            return {"score": 0.0, "compliance": {}, "bands": [], "coaching_actions": []}

        base_score = self.scorecard.get("base_score", 0.0)
        max_score = self.scorecard.get("max_score", 100.0)
        criteria_list = self.scorecard.get("criteria", [])
        categories = self.scorecard.get("categories", [])
        bands = self.scorecard.get("bands", [])

        # Extract agent text & intents
        agent_turns = [m for m in message_analyses if str(m.get("speaker")).lower() == "agent"]
        agent_intents = [str(m.get("intent_label") or "") for m in agent_turns]
        agent_text_combined = " ".join([str(m.get("text_content") or m.get("text") or "").lower() for m in agent_turns])

        score = base_score
        details = []
        is_auto_fail = False
        checked_codes = []

        for crit in criteria_list:
            hit = False
            method = crit.get("detection_method")
            config = crit.get("detection_config", {})
            code = crit.get("code")

            if method == "intent":
                target_intents = config.get("intents", [])
                if any(ti in agent_intents for ti in target_intents):
                    hit = True
            elif method == "keyword":
                target_keywords = config.get("keywords", [])
                if any(tk.lower() in agent_text_combined for tk in target_keywords):
                    hit = True

            if hit:
                checked_codes.append(code)
                scoring_type = crit.get("scoring_type")
                val = crit.get("score_value", 0.0)
                if scoring_type == "regular" or scoring_type == "addition":
                    score += val
                elif scoring_type == "deduction":
                    score -= val

                if crit.get("auto_fail"):
                    is_auto_fail = True

            details.append({
                "criteria_id": crit.get("criteria_id"),
                "code": code,
                "hit": hit
            })

        # Ensure score bounds
        score = max(0.0, min(score, max_score))
        if is_auto_fail:
            score = 0.0

        # Evaluate bands
        triggered_bands = []
        coaching_actions = []
        for band in bands:
            if band["min_score"] <= score <= band["max_score"] or (is_auto_fail and band.get("is_auto_fail_band")):
                triggered_bands.append(band)
                if band.get("action_code") == "coaching_1on1":
                    detail = band.get("action_detail") or {}
                    coaching_actions.append({
                        "type": "coaching",
                        "priority": "Trung bình",
                        "title": detail.get("title", "Coaching Needed"),
                        "action": detail.get("action", "Review call"),
                        "coaching": detail.get("coaching", "Improve script compliance")
                    })

        return {
            "score": score,
            "is_auto_fail": is_auto_fail,
            "checked_codes": checked_codes,
            "details": details,
            "bands": [b["code"] for b in triggered_bands],
            "coaching_actions": coaching_actions,
            "total_checklist": len([c for c in criteria_list if c.get("scoring_type") in ("addition", "regular")])
        }


def evaluate_next_best_actions(
    final_intent: str,
    sentiment_trend: str,
    customer_intents: list[str],
    coaching_actions: list[dict[str, Any]] = None,
    has_over_promise: bool = False
) -> list[dict[str, Any]]:
    """Determine next best actions (tasks) based on outcome, trend and objections (Rule 8.1 and extended)."""
    actions = []

    if coaching_actions:
        actions.extend(coaching_actions)

    # 1. Closed Won
    if final_intent == "Chốt đăng ký":
        actions.append({
            "type": "task",
            "priority": "Cao",
            "title": "Hoàn tất thủ tục ghi danh",
            "action": "Gửi hợp đồng + hướng dẫn thanh toán; tạo tài khoản LMS; bàn giao cho bộ phận học vụ.",
            "coaching": "Xác nhận lại thông tin & thu tiền đúng quy trình."
        })

    # 2. Follow-up + Cải thiện
    if final_intent == "Follow-up / Nuôi lead" and sentiment_trend == "Cải thiện":
        actions.append({
            "type": "task",
            "priority": "Cao",
            "title": "Nuôi lead ấm",
            "action": "Gửi lộ trình/bảng giá qua Zalo; đặt lịch gọi lại trong 2–3 ngày.",
            "coaching": "Giữ nhịp, đừng để nguội lead ấm."
        })

    # 3. Objections & Intent Signals

    # 3.1. Băn khoăn Giá
    if "Từ chối vì chưa đủ tiền" in customer_intents or "Kêu giá cao so với bên khác" in customer_intents or "Từ chối vì giá" in customer_intents:
        actions.append({
            "type": "coaching",
            "priority": "Cao",
            "title": "Xử lý băn khoăn giá",
            "action": "Gửi phương án trả góp 0% + thông tin học bổng; nhắc ưu đãi có hạn.",
            "coaching": "Lần sau chủ động nêu trả góp sớm hơn."
        })

    # 3.2. Trì hoãn / Bận rộn
    if "Xin hỏi ý kiến gia đình" in customer_intents or "Từ chối vì đang đi làm bận" in customer_intents or "Trì hoãn quyết định" in customer_intents or "Hẹn qua đợt sau đăng ký" in customer_intents:
        actions.append({
            "type": "task",
            "priority": "Trung bình",
            "title": "Chống trì hoãn",
            "action": "Gửi tài liệu tóm tắt cho khách chia sẻ; đặt lịch hẹn gọi lại rõ ràng.",
            "coaching": "Đề nghị gọi lại khi khách hàng có thời gian rảnh hoặc có người cùng quyết định."
        })

    # 3.3. So sánh / Chưa chắc chứng chỉ
    if "Nhờ tư vấn so sánh chứng chỉ" in customer_intents or "Hỏi chứng chỉ nào học nhanh dễ hơn" in customer_intents:
        actions.append({
            "type": "task",
            "priority": "Trung bình",
            "title": "Tư vấn chuyển đổi / So sánh",
            "action": "Đừng cố bán cố định! Định hướng sang CMA (ngắn hơn) hoặc gửi link Test đánh giá năng lực.",
            "coaching": "Cần linh hoạt đổi sản phẩm tư vấn phù hợp với nhu cầu học nhanh của khách."
        })

    # 3.4. Lo ngại hình thức học
    if "Lo ngại học online không hiệu quả" in customer_intents:
        actions.append({
            "type": "coaching",
            "priority": "Cao",
            "title": "Cho học thử (Try-before-buy)",
            "action": "Gửi tài khoản trải nghiệm LMS 7 ngày và trích dẫn Review của học viên online thi đậu.",
            "coaching": "Khách chưa tin tưởng online, cần đưa bằng chứng và cho trải nghiệm thực tế."
        })

    # 3.5. Cơ hội việc làm BIG4
    if "Hỏi khả năng xin việc BIG4" in customer_intents:
        actions.append({
            "type": "task",
            "priority": "Trung bình",
            "title": "Chứng minh đầu ra BIG4",
            "action": "Gửi Case Study các học viên SAPP đã đậu BIG4 và thông tin Network hỗ trợ tuyển dụng.",
            "coaching": "Nhấn mạnh lợi thế networking của SAPP."
        })

    # 3.6. Hỏi về miễn môn
    if "Hỏi điều kiện xét miễn môn ACCA" in customer_intents or "Hỏi quy trình xin miễn" in customer_intents:
        actions.append({
            "type": "task",
            "priority": "Cao",
            "title": "Thúc đẩy nộp hồ sơ miễn môn",
            "action": "Gửi ngay Form thu thập bảng điểm Đại học và hẹn lịch tư vấn lộ trình cá nhân hóa.",
            "coaching": "Khách đang rất quan tâm lộ trình rút gọn, cần action ngay."
        })

    # 3.7. Lo sợ rớt
    if "Hỏi chính sách học lại khi rớt" in customer_intents or "Hỏi hợp đồng cam kết đầu ra" in customer_intents:
        actions.append({
            "type": "task",
            "priority": "Cao",
            "title": "Trấn an bằng văn bản",
            "action": "Gửi bản tóm tắt hợp đồng 'Cam kết đầu ra' và điều kiện học lại miễn phí.",
            "coaching": "Khách có rào cản sợ rớt, cần tạo sự an tâm tuyệt đối."
        })

    # 4. Khiếu nại / Xấu đi
    if final_intent == "Khiếu nại" or sentiment_trend == "Xấu đi" or "Phàn nàn giảng viên dạy chán" in customer_intents or "Chê dịch vụ CSKH chậm trễ" in customer_intents:
        actions.append({
            "type": "task",
            "priority": "Cao",
            "title": "Xử lý khiếu nại / Khách không hài lòng",
            "action": "Chuyển bộ phận CSKH/quản lý; ghi nhận phàn nàn; hẹn phản hồi.",
            "coaching": "Ưu tiên xoa dịu, không đẩy bán."
        })

    # 5. Rủi ro / Flags
    if has_over_promise:
        actions.append({
            "type": "coaching",
            "priority": "Cao",
            "title": "Cảnh báo rủi ro cam kết",
            "action": "QA sẽ review lại đoạn ghi âm; quản lý cần nhắc nhở agent.",
            "coaching": "Tuyệt đối không hứa 'đảm bảo đậu 100%' hoặc các cam kết ngoài chính sách."
        })

    return actions

