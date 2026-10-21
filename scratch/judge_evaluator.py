import asyncio
import json
import os
from datetime import datetime

import httpx
from dotenv import load_dotenv

load_dotenv(".env")
API_KEY = os.getenv("OPENAI_API_KEY", "").replace('"', '').replace("'", "").strip()
API_URL = os.getenv("OLLAMA_URL", "http://10.10.207.115:8190") + "/v1/llm/chat"

JUDGE_MODEL = "gpt-4o"
INPUT_PATH = "scratch/evaluation_results.json"
OUT_REPORT_PATH = "scratch/report/expert_evaluation_report.md"

def extract_json(text):
    if not isinstance(text, str): return {}
    try: return json.loads(text)
    except: pass
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1: return json.loads(text[start:end+1])
    except: pass
    return {}

async def call_judge(client, transcript, candidate_out, judge_prompt_template):
    try:
        user_prompt = judge_prompt_template.replace("{transcript_text}", str(transcript)).replace("{candidate_json}", str(candidate_out))
        payload = {"model": JUDGE_MODEL, "messages": [{"role": "user", "content": user_prompt}], "temperature": 0.0, "response_format": {"type": "json_object"}}
        headers = {"Content-Type": "application/json"}
        if API_KEY: headers["X-API-Key"] = API_KEY
        resp = await client.post(API_URL, headers=headers, json=payload, timeout=120.0)
        resp.raise_for_status()
        data = resp.json()
        out_text = ""
        if "choices" in data and isinstance(data["choices"], list) and len(data["choices"]) > 0: out_text = data["choices"][0].get("message", {}).get("content", "")
        elif "response" in data and isinstance(data["response"], dict) and "choices" in data["response"]: out_text = data["response"]["choices"][0].get("message", {}).get("content", "")
        if not out_text:
            print("\n[Judge Error] Empty response from API.")
            return {}
        res_json = extract_json(out_text)
        if not res_json:
            print("\n[Judge Error] Could not parse JSON from API output.")
        return res_json
    except Exception as e:
        print(f"\n[Judge Error] {e.__class__.__name__}: {str(e)[:100]}")
        return {}

async def main():
    print("============================================================")
    print("👨‍⚖️ CHẠY HỆ THỐNG TRỌNG TÀI ĐỂ CHẤM ĐIỂM (TÁCH THEO TỪNG CUỘC GỌI)")
    if not os.path.exists(INPUT_PATH):
        print(f"❌ Không tìm thấy file {INPUT_PATH}"); return
    with open(INPUT_PATH, encoding="utf-8") as f:
        data = json.load(f)
        calls = data.get("fast_path", []) if isinstance(data, dict) else data
    with open("scratch/prompts/judge_prompt.txt", encoding="utf-8") as f:
        judge_prompt_tpl = f.read()

    global_leaderboard = {}
    call_evaluations = []

    async with httpx.AsyncClient(timeout=120.0) as client:
        for call_idx, call in enumerate(calls):
            transcript = call["transcript"]
            call_lb = {}
            for m, m_data in call.get("model_results", {}).items():
                for ev in m_data.get("evals", []):
                    p_name = ev["prompt_name"]
                    key = f"{p_name} - {m}"
                    if key not in call_lb:
                        call_lb[key] = {"runs": 0, "lat": 0, "out_tokens": 0, "faith": 0, "comp": 0, "miss": 0, "f_sum": 0, "f_ent": 0, "f_top": 0, "f_qa": 0, "sample_summary": "", "sample_entities": "", "sample_topics": "", "sample_intents": "", "sample_qa": "", "sample_nba": "", "total": 1, "failed": 0, "errors": []}
                    if key not in global_leaderboard:
                        global_leaderboard[key] = {"runs": 0, "lat": 0, "out_tokens": 0, "total": 0, "failed": 0, "faith": 0, "comp": 0, "miss": 0, "f_sum": 0, "f_ent": 0, "f_top": 0, "f_qa": 0, "errors": [], "overall_comments": [], "medals": 0}
                    c_lb = call_lb[key]; g_lb = global_leaderboard[key]
                    g_lb["total"] += 1
                    if not ev["valid"]:
                        c_lb["failed"] += 1; g_lb["failed"] += 1
                        continue
                    print(f" 🤖 Chấm Cuộc gọi {call_idx+1} | {key}...", end="", flush=True)
                    score_json = await call_judge(client, transcript, ev["output"], judge_prompt_tpl)
                    print(" Xong!")
                    for lb in [c_lb, g_lb]:
                        lb["runs"] += 1; lb["lat"] += ev["latency"]; lb["out_tokens"] += ev["tokens_out"]
                        m_obj = score_json.get("metrics", {})
                        try: lb["faith"] += float(m_obj.get("faithfulness", 0)); lb["comp"] += float(m_obj.get("completeness", 0)); lb["miss"] += float(m_obj.get("missing_rate", 0))
                        except: pass
                        fs = score_json.get("field_scores", {})
                        try: lb["f_sum"] += float(fs.get("summary", 0)); lb["f_ent"] += float(fs.get("entities", 0)); lb["f_top"] += float(fs.get("topics_intents", 0)); lb["f_qa"] += float(fs.get("qa_nba", 0))
                        except: pass
                    errs = score_json.get("error_logs", [])
                    if errs: g_lb["errors"].extend(errs); c_lb["errors"].extend(errs)
                    cmt = score_json.get("overall_comment", "")
                    if cmt: g_lb["overall_comments"].append(cmt)

                    try:
                        cand_json = extract_json(ev["output"]) or {}
                        sum_obj = cand_json.get("summary", {})
                        if isinstance(sum_obj, dict):
                            issue = str(sum_obj.get("issue", "")).replace("\n", " ")
                            res = str(sum_obj.get("resolution", "")).replace("\n", " ")
                            blt_str = "<br> - ".join([str(b) for b in sum_obj.get("summary_bullets")]) if isinstance(sum_obj.get("summary_bullets"), list) else ""
                            sum_text = f"**Vấn đề:** {issue}<br>**Xử lý:** {res}<br>**Chi tiết:**<br> - {blt_str}"
                        else: sum_text = str(sum_obj).replace("\n", " ")
                        
                        entities = cand_json.get("entities", [])
                        ent_str = ", ".join([str(e.get("text", "")) for e in entities if isinstance(e, dict)]) if isinstance(entities, list) else ""
                        
                        topics_obj = cand_json.get("topics", {})
                        if isinstance(topics_obj, dict):
                            t_c = topics_obj.get("topic_customer", "")
                            c_lb["sample_topics"] = json.dumps(t_c, ensure_ascii=False) if isinstance(t_c, dict) else str(t_c).replace("\n", "<br>")
                            
                            i_c = topics_obj.get("intent_customer", "")
                            c_lb["sample_intents"] = json.dumps(i_c, ensure_ascii=False) if isinstance(i_c, dict) else str(i_c).replace("\n", "<br>")
                        
                        c_lb["sample_summary"] = sum_text
                        c_lb["sample_entities"] = ent_str
                        
                        qa_arr = cand_json.get("qa_evaluation", [])
                        qa_details = []
                        if isinstance(qa_arr, list):
                            for q in qa_arr:
                                if isinstance(q, dict):
                                    if q.get("passed") is False:
                                        crit = str(q.get("criterion", "Tiêu chí"))
                                        s_type = str(q.get("scoring_type", ""))
                                        weight = q.get("score_weight_percent", "")
                                        type_mark = s_type
                                        if s_type == "addition": type_mark = "+"
                                        elif s_type == "deduction": type_mark = "-"
                                        elif "fatal" in s_type.lower() or "auto" in s_type.lower() or "fail" in s_type.lower(): type_mark = "x - auto fail"
                                        weight_str = f"{weight}%" if weight != "" else ""
                                        qa_details.append(f"🔴 {crit} ({type_mark}{weight_str})")
                        c_lb["sample_qa"] = "<br>".join(qa_details) if qa_details else "🟢 Không có vi phạm / All Passed"
                        nba_arr = cand_json.get("nba_recommendations", [])
                        nba_details = []
                        if isinstance(nba_arr, list):
                            for n in nba_arr:
                                if isinstance(n, dict):
                                    st = n.get("structured_data", {})
                                    if isinstance(st, dict): nba_details.append(f"📌 {st.get('action_verb', '')} qua {st.get('channel', '')}")
                        c_lb["sample_nba"] = "<br>".join(nba_details) if nba_details else "Không có NBA"
                    except Exception:
                        c_lb["sample_summary"] = "LỖI PARSE"; c_lb["sample_entities"] = "LỖI PARSE"; c_lb["sample_qa"] = "LỖI PARSE"; c_lb["sample_nba"] = "LỖI PARSE"
            call_evaluations.append({"call_id": call["id"], "lb": call_lb})

    # Render Markdown
    md = [
        "# 📊 BÁO CÁO ĐÁNH GIÁ MÔ HÌNH (MODEL METRICS)\n",
        f"**Ngày tạo:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n",
        f"**Model giám khảo:** `{JUDGE_MODEL}`\n\n"
    ]

    # PRE-CALCULATE MEDALS BEFORE RENDERING
    for c_idx, c_eval in enumerate(call_evaluations):
        c_lb = c_eval["lb"]
        valid_lbs = [lb for lb in c_lb.values() if lb["runs"] > 0]
        
        max_ent = max([lb["f_ent"]/lb["runs"] for lb in valid_lbs]) if valid_lbs else 0
        max_top = max([lb.get("f_top", 0)/lb["runs"] for lb in valid_lbs]) if valid_lbs else 0
        max_sum = max([lb["f_sum"]/lb["runs"] for lb in valid_lbs]) if valid_lbs else 0
        max_qa = max([lb["f_qa"]/lb["runs"] for lb in valid_lbs]) if valid_lbs else 0

        def get_tiebreaker(lb):
            return (lb.get("faith", 0) + lb.get("comp", 0) - lb.get("miss", 0)) / lb["runs"] if lb["runs"] > 0 else -999

        best_ent_k, best_top_k, best_sum_k, best_qa_k = None, None, None, None

        if max_ent > 0:
            best_ent_k = max([k for k, lb in c_lb.items() if lb["runs"] > 0 and round(lb["f_ent"]/lb["runs"], 1) == max_ent], key=lambda k: get_tiebreaker(c_lb[k]))
        if max_top > 0:
            best_top_k = max([k for k, lb in c_lb.items() if lb["runs"] > 0 and round(lb.get("f_top", 0)/lb["runs"], 1) == max_top], key=lambda k: get_tiebreaker(c_lb[k]))
        if max_sum > 0:
            best_sum_k = max([k for k, lb in c_lb.items() if lb["runs"] > 0 and round(lb["f_sum"]/lb["runs"], 1) == max_sum], key=lambda k: get_tiebreaker(c_lb[k]))
        if max_qa > 0:
            best_qa_k = max([k for k, lb in c_lb.items() if lb["runs"] > 0 and round(lb["f_qa"]/lb["runs"], 1) == max_qa], key=lambda k: get_tiebreaker(c_lb[k]))

        c_eval["best_ent_k"] = best_ent_k
        c_eval["best_top_k"] = best_top_k
        c_eval["best_sum_k"] = best_sum_k
        c_eval["best_qa_k"] = best_qa_k

        if best_ent_k: global_leaderboard[best_ent_k]["medals"] += 1
        if best_top_k: global_leaderboard[best_top_k]["medals"] += 2 # Topic and Intent
        if best_sum_k: global_leaderboard[best_sum_k]["medals"] += 1
        if best_qa_k: global_leaderboard[best_qa_k]["medals"] += 1

    # GLOBAL LEADERBOARD SECTION
    md.append("## 🏆 1. BẢNG XẾP HẠNG TỔNG QUÁT (GLOBAL LEADERBOARD)\n")
    md.append("| Model & Prompt | Tỷ lệ Thành công | Tốc độ TB | Điểm Chất lượng TB | Tỷ lệ Sót/Bịa TB | Tổng Huy Chương 🏅 |")
    md.append("|---|---|---|---|---|---|")

    def get_avg(lb):
        r = lb["runs"]
        if r == 0: return -9999
        return ((lb["faith"] + lb["comp"] + lb["f_sum"] + lb["f_ent"] + lb["f_qa"]) / r) - (lb["miss"] / r)

    def get_sort_key(lb):
        success_rate = lb["runs"] / lb["total"] if lb["total"] > 0 else 0
        score = get_avg(lb)
        medals = lb.get("medals", 0)
        # Sort priority: 1. Success Rate -> 2. Quality Score -> 3. Medals
        return (success_rate, score, medals)

    sorted_glb = sorted(global_leaderboard.items(), key=lambda x: get_sort_key(x[1]), reverse=True)

    for k, lb in sorted_glb:
        if lb["total"] == 0: continue
        pass_rate = f'{lb["runs"]}/{lb["total"]} ({int(lb["runs"]/lb["total"]*100)}%)'
        if lb["runs"] == 0:
            md.append(f"| **{k}** | {pass_rate} | - | 0 / 50 | 100% | 0 |")
            continue
        r = lb["runs"]
        avg_lat = lb["lat"] / r
        tps = f"{round(lb['out_tokens']/r / avg_lat, 1)} t/s" if avg_lat > 0 else "0"
        avg_score = round((lb["faith"] + lb["comp"] + lb["f_sum"] + lb["f_ent"] + lb["f_qa"]) / r, 1)
        avg_miss = f"{round(lb['miss'] / r, 1)}%"
        medals = lb.get("medals", 0)
        medal_str = f"🏅 x {medals}" if medals > 0 else "0"
        md.append(f"| **{k}** | {pass_rate} | {tps} | **{avg_score} / 50** | {avg_miss} | {medal_str} |")

    md.append("") # Break table

    md.append("---\n## 📝 2. CHI TIẾT ĐÁNH GIÁ TỪNG CUỘC GỌI\n")

    for c_idx, c_eval in enumerate(call_evaluations):
        md.append(f"### ĐÁNH GIÁ CUỘC GỌI {c_idx + 1} (ID: {c_eval['call_id']})\n")
        md.append("<details><summary>👉 Nhấn để xem/ẩn chi tiết bảng điểm cuộc gọi này</summary>\n")
        c_lb = c_eval["lb"]

        md.append(f"#### {c_idx + 1}.1 BẢNG CHỈ SỐ CHẤT LƯỢNG MÔ HÌNH")
        md.append("| Model | Prompt | Tốc độ | Token Đầu Ra | Faithfulness | Completeness | Tỷ lệ sót thông tin |")
        md.append("|---|---|---|---|---|---|---|")
        for k, lb in c_lb.items():
            if lb["total"] == 0: continue
            p_name, mod_name = k.split(" - ", 1)
            if lb["runs"] == 0:
                md.append(f"| **{mod_name}** | {p_name} | - | - | ❌ LỖI JSON | ❌ LỖI JSON | 100% |")
                continue
            runs = lb["runs"]
            avg_lat = lb["lat"] / runs
            tps = f"{round(lb['out_tokens']/runs / avg_lat, 1)} t/s" if avg_lat > 0 else "0"
            avg_out = f"{int(lb['out_tokens'] / runs)}"
            fac = round(lb["faith"]/runs, 1)
            comp = round(lb["comp"]/runs, 1)
            miss = f"{round(lb['miss']/runs, 1)}%"
            md.append(f"| **{mod_name}** | {p_name} | {tps} | {avg_out} | {fac}/10 | {comp}/10 | {miss} |")
        md.append("")

        md.append(f"#### {c_idx + 1}.2 MA TRẬN THỰC THỂ & PHÂN LOẠI")
        md.append("| PROMPT - MODEL | Entities | Topic | Intent | Huy chương |")
        md.append("|---|---|---|---|---|")

        for k, lb in c_lb.items():
            if lb["total"] == 0: continue
            if lb["runs"] == 0:
                md.append(f"| **{k}** | ❌ LỖI JSON | ❌ LỖI JSON | ❌ LỖI JSON | - |")
                continue
            
            best_badges = []
            if k == c_eval["best_ent_k"]: best_badges.append("🏅 Entities")
            if k == c_eval["best_top_k"]:
                best_badges.append("🏅 Topic")
                best_badges.append("🏅 Intent")
                
            best_str = "<br>".join(best_badges) if best_badges else "-"
            
            ent_display = f"*{lb['sample_entities']}*"
            topic_str = str(lb.get('sample_topics', ''))
            intent_str = str(lb.get('sample_intents', ''))
            md.append(f"| **{k}** | {ent_display} | {topic_str} | {intent_str} | {best_str} |")
        md.append("")

        md.append(f"#### {c_idx + 1}.3 MA TRẬN TÓM TẮT & QA")
        md.append("| PROMPT - MODEL | Summary | QA & NBA | Huy chương |")
        md.append("|---|---|---|---|")
        for k, lb in c_lb.items():
            if lb["total"] == 0: continue
            if lb["runs"] == 0:
                md.append(f"| **{k}** | ❌ LỖI JSON | ❌ LỖI JSON | - |")
                continue

            best_badges = []
            if k == c_eval["best_sum_k"]: best_badges.append("🏅 Summary")
            if k == c_eval["best_qa_k"]: best_badges.append("🏅 QA/NBA")
            
            best_str = "<br>".join(best_badges) if best_badges else "-"
            sum_display = f"{lb['sample_summary']}"
            qa_nba_display = f"{lb.get('sample_qa', '')}<br><br>**NBA:**<br>{lb.get('sample_nba', '')}"
            md.append(f"| **{k}** | {sum_display} | {qa_nba_display} | {best_str} |")
        md.append("")

        md.append(f"#### {c_idx + 1}.4 PHÂN TÍCH LỖI (HALLUCINATION & MISSING LOGS)\n")
        has_errors = False
        for k, lb in c_lb.items():
            if lb.get("errors"):
                has_errors = True
                md.append(f"**🛑 Lỗi của `{k}`**")
                for err in lb["errors"]:
                    md.extend([
                        f"- **Loại lỗi:** `{err.get('error_type', 'N/A')}` (Trường: `{err.get('field_name', 'N/A')}`)",
                        f"  - **Trong Ghi âm:** {err.get('in_transcript', 'N/A')}",
                        f"  - **Model Output:** {err.get('model_output', 'N/A')}",
                        f"  - **Tại sao là lỗi:** {err.get('reason', 'N/A')}"
                    ])
                md.append("")
        if not has_errors:
            md.append("*Không phát hiện lỗi Hallucination hoặc Missing nghiêm trọng trong cuộc gọi này.*\n")

        md.append("\n</details>\n")

    # KẾT LUẬN TỔNG QUÁT SECTION
    best_pair = "Chưa xác định"
    if sorted_glb:
        best_pair = sorted_glb[0][0]

    md.extend([
        "\n---\n## 3. KẾT LUẬN TỔNG QUÁT & ĐỀ XUẤT TỪ HỆ THỐNG",
        f"### 🏆 HỆ THỐNG ĐỀ XUẤT LỰA CHỌN TỐI ƯU NHẤT: `{best_pair}`",
        "*(Lựa chọn được tự động tính toán dựa trên tổng điểm trung bình của toàn bộ các cuộc gọi)*\n",
        "**Giải thích từ Giám khảo AI:**"
    ])
    if best_pair in global_leaderboard:
        cmts = list(set(global_leaderboard[best_pair].get("overall_comments", [])))
        for c in cmts:
            if c: md.append(f"- {c}")

    os.makedirs(os.path.dirname(OUT_REPORT_PATH), exist_ok=True)

    with open(OUT_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("✅ Đã tạo báo cáo tách riêng từng bảng cho mỗi cuộc gọi!")

if __name__ == "__main__":
    asyncio.run(main())
