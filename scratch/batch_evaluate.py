import asyncio
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import httpx
import tiktoken
from dotenv import load_dotenv

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

CONFIG_PATH = "scratch/eval_config.json"

MAP_PROMPT_PATH = "scratch/prompts/map_prompt.txt"

encoder = tiktoken.get_encoding("cl100k_base")
SAFE_TOKEN_LIMIT = 2500

def count_tokens(text: str) -> int:
    return len(encoder.encode(text))

def chunk_transcript_by_tokens(text: str, max_tokens=2500, overlap_tokens=300):
    lines = text.split('\n')
    chunks = []
    current_chunk_lines = []
    current_tokens = 0

    for line in lines:
        line_tokens = len(encoder.encode(line + '\n'))
        if current_tokens + line_tokens > max_tokens and current_chunk_lines:
            chunks.append('\n'.join(current_chunk_lines))
            # Keep overlap lines
            overlap_lines = []
            overlap_count = 0
            for prev_line in reversed(current_chunk_lines):
                prev_line_tokens = len(encoder.encode(prev_line + '\n'))
                if overlap_count + prev_line_tokens > overlap_tokens:
                    break
                overlap_lines.insert(0, prev_line)
                overlap_count += prev_line_tokens
            current_chunk_lines = overlap_lines
            current_tokens = overlap_count

        current_chunk_lines.append(line)
        current_tokens += line_tokens

    if current_chunk_lines:
        chunks.append('\n'.join(current_chunk_lines))
        
    return chunks

def get_tokens(data):
    def find_key(d, k):
        if k in d: return d[k]
        for key, v in d.items():
            if isinstance(v, dict):
                res = find_key(v, k)
                if res is not None: return res
        return None
    return find_key(data, "prompt_tokens") or 0, find_key(data, "completion_tokens") or 0

def extract_json(text):
    try:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except:
        pass
    return {}

def validate_json_schema(text):
    js = extract_json(text)
    required_keys = ["sentiment_overall", "summary", "topics"]
    if all(k in js for k in required_keys):
        return True
    return False

async def call_llm(client: httpx.AsyncClient, model_name: str, sys_prompt: str, user_prompt: str, is_map_task: bool = False):
    start_time = time.time()
    tokens_in = 0
    tokens_out = 0
    is_valid = False
    out = ""

    import json
    # Vẫn dùng V2_SHORT_SCHEMA để xác thực kết quả sau khi AI trả về (Validate)
    from voiceiq.service.transcript.domain.schemas import V2_SHORT_SCHEMA, MAP_CHUNK_SCHEMA
    
    active_schema = MAP_CHUNK_SCHEMA if is_map_task else V2_SHORT_SCHEMA

    # Đọc lại 2 biến cũ của Cổng Ollama nội bộ
    api_url = os.getenv("OLLAMA_URL", "http://10.10.207.115:8190").rstrip("/")
    api_key = os.getenv("OPENAI_API_KEY", "").replace('"', '').replace("'", "").strip()
    
    headers = {"Content-Type": "application/json"}
    if api_key: headers["X-API-Key"] = api_key
    
    # Đối với Ollama (chưa hỗ trợ Strict Schema API), chúng ta dùng response_format: "json_object" cơ bản
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2
    }

    try:
        res = await client.post(f"{api_url}/v1/llm/chat", headers=headers, json=payload, timeout=180.0)
        res.raise_for_status()
        data = res.json()
        
        out = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if not out:
            out = data.get("response", {}).get("choices", [{}])[0].get("message", {}).get("content", str(data))

        tokens_in, tokens_out = get_tokens(data)
        
        # Mặc dù Gateway không ép được Schema lúc sinh, nhưng ta vẫn dùng Schema để KIỂM TRA ĐẦU RA
        is_valid = validate_json_schema(out)

    except Exception as e:
        out = f"LỖI API: {str(e)}"

    return out, round(time.time() - start_time, 2), tokens_in, tokens_out, is_valid

async def main():
    print("="*60)
    print("BẮT ĐẦU CHẠY BATCH EVALUATION PROMPT (MULTI-MODEL & AUTO-QA)")


    with open(CONFIG_PATH, encoding="utf-8-sig") as f:
        config = json.load(f)

    db_config_path = "scratch/database_config.json"
    with open(db_config_path, encoding="utf-8") as f:
        db_config = json.load(f)

    DB_TOPICS = db_config.get("topics", [])
    DB_INTENTS = db_config.get("intents", [])
    DB_KEYWORDS = db_config.get("keywords", [])
    DB_QA = db_config.get("qa_criteria", [])


    models_to_test = config.get("models_to_test", ["qwen2.5:7b"])
    dataset_path = config.get("input_dataset_path", "scratch/sample_dataset.json")
    out_md_path = config.get("output_report_path", ".report/prompt_optimization_report.md")

    with open(dataset_path, encoding="utf-8") as f:
        calls = json.load(f)

    prompts = []
    for p in config["prompts_to_test"]:
        if os.path.exists(p["filepath"]):
            with open(p["filepath"], encoding="utf-8") as f:
                prompts.append({"name": p["name"], "content": f.read()})

    map_prompt_content = ""
    if os.path.exists(MAP_PROMPT_PATH):
        with open(MAP_PROMPT_PATH, encoding="utf-8") as f:
            map_prompt_content = f.read()

    results_fast = []
    results_mr = []
    leaderboard = {}

    for m in models_to_test:
        for p in prompts:
            leaderboard[f"{m} || {p['name']}"] = {"fast_lat": 0, "fast_in": 0, "fast_out": 0, "fast_runs": 0, "mr_lat": 0, "mr_in": 0, "mr_out": 0, "mr_runs": 0}

    print("\n" + "="*60)
    print("📊 PHÂN BỔ DỮ LIỆU CUỘC GỌI (PREVIEW)")
    fast_calls = []
    mr_calls = []
    for idx, call in enumerate(calls):
        t_count = count_tokens(call["transcript"])
        if t_count >= SAFE_TOKEN_LIMIT:
            mr_calls.append((idx + 1, call.get("id", "N/A"), t_count))
        else:
            fast_calls.append((idx + 1, call.get("id", "N/A"), t_count))
    
    print(f"Tổng số cuộc gọi: {len(calls)}")
    print(f"⚡ FAST PATH (< {SAFE_TOKEN_LIMIT} tokens): {len(fast_calls)} cuộc gọi")
    for c in fast_calls:
        print(f"   - Call {c[0]} (ID: {c[1]}) - {c[2]} tokens")
    
    print(f"🧩 MAP-REDUCE (>= {SAFE_TOKEN_LIMIT} tokens): {len(mr_calls)} cuộc gọi")
    for c in mr_calls:
        print(f"   - Call {c[0]} (ID: {c[1]}) - {c[2]} tokens")
        
    print("="*60)
    print("Chọn chế độ xử lý:")
    print("  0. Xử lý tất cả (Mặc định)")
    print("  1. Chỉ xử lý cuộc gọi FAST PATH")
    print("  2. Chỉ xử lý cuộc gọi MAP-REDUCE")
    choice = input("👉 Nhập số (0/1/2) và nhấn ENTER (hoặc Ctrl+C để hủy): ").strip()
    
    if choice == "1":
        calls = [c for c in calls if count_tokens(c["transcript"]) < SAFE_TOKEN_LIMIT]
        print(f"👉 Đã lọc: Chỉ chạy {len(calls)} cuộc gọi FAST PATH.")
    elif choice == "2":
        calls = [c for c in calls if count_tokens(c["transcript"]) >= SAFE_TOKEN_LIMIT]
        print(f"👉 Đã lọc: Chỉ chạy {len(calls)} cuộc gọi MAP-REDUCE.")
    else:
        print("👉 Chạy tất cả cuộc gọi.")
        
    if not calls:
        print("❌ Không có cuộc gọi nào phù hợp để xử lý. Kết thúc.")
        return
    async with httpx.AsyncClient(timeout=180.0) as client:
        for idx, call in enumerate(calls):
            t_count = count_tokens(call["transcript"])
            is_mr = t_count >= SAFE_TOKEN_LIMIT

            print(f"\n--- [Call {idx+1}/{len(calls)}] Token: {t_count} | Mode: {'MAP-REDUCE' if is_mr else 'FAST PATH'} ---")

            call_result = {
                "id": call["id"], "transcript": call["transcript"], "duration": call.get("duration_seconds", 0),
                "turns": call.get("turn_count", 0), "token_count": t_count, "is_mr": is_mr, "model_results": {}
            }

            for m in models_to_test:
                print(f" 🤖 Chạy Model: {m}")
                m_res = {"evals": [], "map_stats": None, "map_combined": ""}

                if not is_mr:
                    for p in prompts:
                        # Thực hiện Dynamic Injection (Như F-string)
                        sys_prompt = p["content"].replace("{topics}", ", ".join(DB_TOPICS)) \
                                                 .replace("{intents}", ", ".join(DB_INTENTS)) \
                                                 .replace("{keywords}", ", ".join(DB_KEYWORDS))

                        qa_json = ",\n    ".join([
                            f'{{"criterion": "{c.get("name", "")}", "description": "{c.get("description", "")}", "scoring_type": "{c.get("scoring_type", "")}", "score_weight_percent": {c.get("score_weight_percent", 0)}, "passed": "<true hoặc false>", "reason": "Giải thích chi tiết tại sao"}}'
                            if isinstance(c, dict) else str(c) for c in DB_QA
                        ])
                        sys_prompt = sys_prompt.replace("{qa_rules}", qa_json)

                        user_prompt = f"Hội thoại:\n{call['transcript']}"

                        # TÍNH TOÁN TOKEN CỰC KỲ CHI TIẾT THEO YÊU CẦU SẾP
                        base_tokens = count_tokens(sys_prompt)
                        transcript_tokens = count_tokens(user_prompt)
                        total_req_tokens = base_tokens + transcript_tokens

                        print(f"    -> Đang chạy {p['name']}...")
                        print(f"       [Token check] Base Prompt: {base_tokens} tk | Transcript: {transcript_tokens} tk | TỔNG ĐẦU VÀO: {total_req_tokens} tk")

                        if total_req_tokens > 10000:
                            print("       ⚠️ CẢNH BÁO: Tổng Token quá lớn, nguy cơ bị API Gateway chặn (20k ký tự)!")

                        out, lat, t_in, t_out, valid = await call_llm(client, m, sys_prompt, user_prompt)
                        print(f"       ✅ Xong ({lat}s) - Trả về: {t_out} tokens")

                        m_res["evals"].append({"prompt_name": p["name"], "output": out, "latency": lat, "tokens_in": t_in, "tokens_out": t_out, "valid": valid, "input_prompt": sys_prompt + "\n\n" + user_prompt})
                        lb_key = f"{m} || {p['name']}"
                        leaderboard[lb_key]["fast_lat"] += lat; leaderboard[lb_key]["fast_in"] += t_in; leaderboard[lb_key]["fast_out"] += t_out
                        leaderboard[lb_key]["fast_runs"] += 1

                else:
                    chunks = chunk_transcript_by_tokens(call['transcript'], SAFE_TOKEN_LIMIT, 300)
                    m_res["num_chunks"] = len(chunks)

                    map_tasks = []
                    
                    qa_json = ",\n    ".join([
                        f'{{"criterion": "{c.get("name", "")}", "description": "{c.get("description", "")}"}}'
                        if isinstance(c, dict) else str(c) for c in DB_QA
                    ])
                    map_prompt_rendered = map_prompt_content.replace("{topics}", ", ".join(DB_TOPICS)) \
                                                            .replace("{intents}", ", ".join(DB_INTENTS)) \
                                                            .replace("{keywords}", ", ".join(DB_KEYWORDS)) \
                                                            .replace("{qa_rules}", qa_json)
                    
                    for i, chunk in enumerate(chunks):
                        map_tasks.append(call_llm(client, m, map_prompt_rendered, f"Đoạn thoại phần {i+1}:\n{chunk}", is_map_task=True))

                    map_res_list = await asyncio.gather(*map_tasks)
                    map_lat = round(max([r[1] for r in map_res_list]) if map_res_list else 0, 2)
                    map_in = sum(r[2] for r in map_res_list)
                    map_out = sum(r[3] for r in map_res_list)

                    combined_text = "\n--- DỮ LIỆU TÓM TẮT TRUNG GIAN (TỪ MAP PHASE) ---\n"
                    for i, r in enumerate(map_res_list):
                        js = extract_json(r[0])
                        summary = js.get("chunk_summary", r[0][:100] + "...")
                        entities = js.get("entities", [])
                        escalation_detected = js.get("escalation_detected", False)
                        toxicity_detected = js.get("toxicity_detected", False)
                        escalation_signals = js.get("escalation_signals", [])
                        toxicity_tags = js.get("toxicity_tags", [])
                        qa_evidence = js.get("qa_evidence", [])
                        nba_clues = js.get("nba_clues", [])
                        detected_topics = js.get("detected_topics", [])
                        detected_intents = js.get("detected_intents", [])
                        dynamic_keywords = js.get("dynamic_keywords", [])
                        s_cust = js.get("sentiment_customer", "")
                        s_agent = js.get("sentiment_agent", "")
                        e_cust = js.get("emotion_customer", "")
                        e_agent = js.get("emotion_agent", "")
                        
                        combined_text += f"Phần {i+1}:\n"
                        combined_text += f"- Tóm tắt: {summary}\n"
                        if s_cust or e_cust:
                            combined_text += f"- Cảm xúc Khách hàng: {s_cust} / {e_cust}\n"
                        if s_agent or e_agent:
                            combined_text += f"- Cảm xúc Agent: {s_agent} / {e_agent}\n"
                        if detected_topics:
                            combined_text += f"- Chủ đề (Topics): {detected_topics}\n"
                        if detected_intents:
                            combined_text += f"- Mục đích (Intents): {detected_intents}\n"
                        if dynamic_keywords:
                            combined_text += f"- Từ khóa (Keywords): {dynamic_keywords}\n"
                        combined_text += f"- Thực thể (Entities): {entities}\n"
                        if escalation_detected:
                            combined_text += f"- Có dấu hiệu leo thang (Escalation): {escalation_signals}\n"
                        if toxicity_detected:
                            combined_text += f"- Có độc hại/chửi thề (Toxicity): {toxicity_tags}\n"
                        if qa_evidence:
                            combined_text += f"- Bằng chứng QA: {qa_evidence}\n"
                        if nba_clues:
                            combined_text += f"- Manh mối NBA: {nba_clues}\n"
                        combined_text += "\n"

                    m_res["map_combined"] = combined_text
                    m_res["map_stats"] = {"lat": map_lat, "in": map_in, "out": map_out}

                    for p in prompts:
                        sys_prompt = p["content"].replace("{topics}", ", ".join(DB_TOPICS)) \
                                                 .replace("{intents}", ", ".join(DB_INTENTS)) \
                                                 .replace("{keywords}", ", ".join(DB_KEYWORDS))
                        qa_json = ",\n    ".join([
                            f'{{"criterion": "{c.get("name", "")}", "description": "{c.get("description", "")}", "scoring_type": "{c.get("scoring_type", "")}", "score_weight_percent": {c.get("score_weight_percent", 0)}, "passed": "<true hoặc false>", "reason": "Giải thích chi tiết tại sao"}}'
                            if isinstance(c, dict) else str(c) for c in DB_QA
                        ])
                        sys_prompt = sys_prompt.replace("{qa_rules}", qa_json)

                        print(f"    -> Đang chạy REDUCE {p['name']}...", end="", flush=True)
                        out, red_lat, red_in, red_out, valid = await call_llm(client, m, sys_prompt, f"TỔNG HỢP CÁC BẰNG CHỨNG TỪ MAP:\n{combined_text}")
                        print(f" Xong ({red_lat}s)")
                        total_lat = round(map_lat + red_lat, 2)
                        total_in = map_in + red_in
                        total_out = map_out + red_out
                        m_res["evals"].append({"input_prompt": sys_prompt + "\n\n" + f"TỔNG HỢP CÁC BẰNG CHỨNG TỪ MAP:\n{combined_text}",
                            "prompt_name": p["name"], "output": out, "latency": total_lat, "reduce_latency": red_lat,
                            "tokens_in": total_in, "tokens_out": total_out, "reduce_in": red_in, "reduce_out": red_out, "valid": valid
                        })
                        lb_key = f"{m} || {p['name']}"
                        leaderboard[lb_key]["mr_lat"] += total_lat; leaderboard[lb_key]["mr_in"] += total_in; leaderboard[lb_key]["mr_out"] += total_out
                        leaderboard[lb_key]["mr_runs"] += 1

                call_result["model_results"][m] = m_res

            if not is_mr:
                results_fast.append(call_result)
            else:
                results_mr.append(call_result)

    print("\n📝 Đang tạo Báo cáo Markdown...")
    print("\n📝 Đang tạo Báo cáo Markdown...")
    md = ["# 📊 Báo Cáo Tối Ưu LLM (Matrix: Models x Prompts)", f"**Ngày tạo:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"]

    # 1. TỔNG QUAN CHI PHÍ TOKEN
    md.extend(["## 1. BẢNG SO SÁNH HIỆU NĂNG: FAST PATH vs MAP-REDUCE\n"])

    fast_count = len(results_fast)
    mr_count = len(results_mr)

    md.extend([
        f"- **Tổng số cuộc gọi phân tích:** {len(calls)} (Fast: {fast_count} | Map-Reduce: {mr_count})",
        "*(Các chỉ số dưới đây là **Trung bình cho mỗi cuộc gọi**, giúp bạn dễ dàng so sánh tốc độ xử lý và lượng Token tiêu thụ)*\n",
        "| Model | Prompt | ⚡ FAST PATH (Thời gian / In / Out) | 🧩 MAP-REDUCE (Thời gian / In / Out) |",
        "|---|---|---|---|"
    ])

    for m in models_to_test:
        for p in prompts:
            lb_key = f"{m} || {p['name']}"
            if lb_key in leaderboard:
                lb = leaderboard[lb_key]
                if lb["fast_runs"] == 0 and lb["mr_runs"] == 0: continue

                f_lat = round(lb['fast_lat'] / lb['fast_runs'], 2) if lb['fast_runs'] > 0 else 0
                f_in = f"{int(lb['fast_in'] / lb['fast_runs']):,}" if lb['fast_runs'] > 0 else "0"
                f_out = f"{int(lb['fast_out'] / lb['fast_runs']):,}" if lb['fast_runs'] > 0 else "0"
                fast_str = f"**{f_lat}s** / {f_in} tk / {f_out} tk" if lb['fast_runs'] > 0 else "-"

                m_lat = round(lb['mr_lat'] / lb['mr_runs'], 2) if lb['mr_runs'] > 0 else 0
                m_in = f"{int(lb['mr_in'] / lb['mr_runs']):,}" if lb['mr_runs'] > 0 else "0"
                m_out = f"{int(lb['mr_out'] / lb['mr_runs']):,}" if lb['mr_runs'] > 0 else "0"
                mr_str = f"**{m_lat}s** / {m_in} tk / {m_out} tk" if lb['mr_runs'] > 0 else "-"

                md.append(f"| **{m}** | {p['name']} | {fast_str} | {mr_str} |")

    md.extend(["\n---\n"])

    # # 1. CHI TIẾT PROMPT
    # md.extend(["## 1. NỘI DUNG CÁC PROMPT (Để đối chiếu)\n", "<details><summary>👉 Nhấn để xem/ẩn nội dung các Prompt</summary>\n"])

    # for p in prompts:
    #     md.extend([f"### 🔹 {p['name']}", "```text", p['content'], "```\n"])
    # if map_prompt_content:
    #     md.extend(["### 🔹 MAP PROMPT (Dùng để tóm tắt các Chunks)", "```text", map_prompt_content, "```\n"])
    # md.extend(["</details>\n", "---\n"])

    # 2. DẪN CHỨNG JSON
    md.extend(["## 2. BẰNG CHỨNG THỰC TẾ (Transcript & JSON Output)\n", "*Sử dụng thẻ `<details>` để tránh làm báo cáo quá dài. Vui lòng click vào mũi tên để xem chi tiết JSON.*\n"])

    all_calls = results_fast + results_mr
    for call in all_calls:
        md.extend([f"### 📞 Call ID: `{call['id']}`", f"*(Chế độ: {'MAP-REDUCE' if call['is_mr'] else 'FAST PATH'} | Token: {call['token_count']})*\n", "<details><summary>👉 Nhấn để xem/ẩn chi tiết cuộc gọi này</summary>\n", "**Nội dung hội thoại:**"])
        formatted_transcript = call["transcript"].replace("\n", " <br> ")
        md.extend([f"> {formatted_transcript}\n"])

        for m in models_to_test:
            m_res = call["model_results"][m]
            md.extend([f"#### 🤖 Kết quả từ Model: `{m}`"])

            if call['is_mr'] and m_res.get("map_combined"):
                md.extend(["<details><summary>📂 <b>Dữ liệu tóm tắt trung gian (MAP Phase)</b></summary>", "", "```text", m_res["map_combined"].strip(), "```", "</details>", ""])

            for ev in m_res["evals"]:
                icon = "✅ HỢP LỆ" if ev['valid'] else "❌ LỖI FORMAT"

                # Dọn dẹp markdown rác do AI tự sinh ra
                clean_out = ev['output'].strip()
                if clean_out.startswith("```json"): clean_out = clean_out[7:]
                elif clean_out.startswith("```"): clean_out = clean_out[3:]
                if clean_out.endswith("```"): clean_out = clean_out[:-3]
                clean_out = clean_out.strip()

                input_text = ev.get('input_prompt', 'N/A')
                md.extend([
                    f"<details><summary><b>Xem Input {ev['prompt_name']}</b></summary>",
                    "",
                    "```text",
                    input_text,
                    "```",
                    "</details>",
                    f"<details><summary><b>Xem Output {ev['prompt_name']}</b> ({icon} | {ev['latency']}s | {ev['tokens_in']}/{ev['tokens_out']} tk)</summary>",
                    "",
                    "```json",
                    clean_out,
                    "```",
                    "</details>",
                    ""
                ])
        md.extend(["</details>\n", "---\n"])

    os.makedirs(os.path.dirname(out_md_path), exist_ok=True)
    with open(out_md_path, "w", encoding="utf-8") as f: f.write("\n".join(md))
    print(f"✅ HOÀN TẤT! Đã lưu báo cáo tại: {out_md_path}")

    # LƯU KẾT QUẢ THÔ CHO TRỌNG TÀI (EVALUATOR)
    raw_results = {
        "fast_path": results_fast,
        "map_reduce": results_mr
    }
    with open("scratch/evaluation_results.json", "w", encoding="utf-8") as f:
        json.dump(raw_results, f, ensure_ascii=False, indent=2)
    print("✅ Đã lưu kết quả thô tại: scratch/evaluation_results.json")

if __name__ == "__main__":
    asyncio.run(main())
