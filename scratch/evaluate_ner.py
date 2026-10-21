import json
import os
from pathlib import Path
import httpx
from dotenv import load_dotenv

# ==============================================================================
# CẤU HÌNH API (AXON HUB LOCAL)
# ==============================================================================
# Load biến môi trường từ file .env ở thư mục gốc của project
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

API_URL = os.getenv("OLLAMA_URL", "http://10.10.207.115:8190").rstrip("/")
API_KEY = os.getenv("OPENAI_API_KEY", "").replace('"', '').replace("'", "").strip()

# ==============================================================================
# CẤU HÌNH ĐƯỜNG DẪN
# ==============================================================================
BASE_DIR = r"K:\VoiceIQ\gitlab\VoiceIQ-analysis-worker\scratch"
INPUT_FILE = os.path.join(BASE_DIR, "evaluation_results.json")
CONFIG_FILE = os.path.join(BASE_DIR, "eval_config.json")
REPORT_DIR = os.path.join(BASE_DIR, "report")


def review_entities_with_local_llm(transcript: str, model_name: str, prompt_name: str, entities: list, review_model: str) -> str:
    """
    Gọi LLM local thông qua Axon Hub Gateway để đọc hội thoại, đánh giá các entities và sửa lại cho đúng.
    """
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
        
    sys_prompt = "Bạn là một chuyên gia đánh giá và trích xuất thực thể có tên (NER)."
    user_prompt = f"""
Dưới đây là một đoạn hội thoại (Transcript) và danh sách các thực thể (Entities) đã được trích xuất bởi một mô hình AI ({model_name}) thông qua prompt ({prompt_name}).

### NỘI DUNG HỘI THOẠI (TRANSCRIPT)
{transcript}

### CÁC THỰC THỂ ĐÃ TRÍCH XUẤT BAN ĐẦU (TỪ MÔ HÌNH)
{json.dumps(entities, ensure_ascii=False, indent=2)}

### YÊU CẦU:
1. Đọc kỹ đoạn hội thoại và đối chiếu với danh sách các thực thể đã trích xuất ở trên.
2. Nhận xét xem mô hình đã trích xuất đúng, thiếu, hay sai (ảo giác/nhầm lẫn) những thực thể nào.
3. Sửa lại cho đúng và xuất kết quả thành một bảng Markdown.
Bảng Markdown phải có các cột: [Loại thực thể (Type), Trích xuất ban đầu (Original Text), Sửa lại (Corrected Text), Nhận xét/Lý do (Reason)]

Chỉ trả về nội dung bảng Markdown và một đoạn nhận xét ngắn gọn, KHÔNG cần thêm các giải thích thừa thãi ngoài lề.
"""

    payload = {
        "model": review_model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2
    }

    try:
        # Tăng timeout một chút vì LLM đọc toàn bộ transcript và sinh ra bảng dài
        with httpx.Client(timeout=300.0) as client:
            res = client.post(f"{API_URL}/v1/llm/chat", headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()
            
            # Parsing response from gateway format
            out = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not out:
                out = data.get("response", {}).get("choices", [{}])[0].get("message", {}).get("content", str(data))
                
            return out
    except Exception as e:
        print(f"Lỗi khi gọi LLM cho đánh giá: {e}")
        return f"Lỗi gọi LLM: {str(e)}"


def extract_ner_baseline(transcript: str, review_model: str) -> str:
    """
    Yêu cầu Model Giám Khảo tự trích xuất NER trực tiếp từ đoạn hội thoại gốc (không tham khảo kết quả cũ).
    """
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["X-API-Key"] = API_KEY
        
    sys_prompt = "Bạn là một AI chuyên trích xuất thực thể có tên (NER)."
    user_prompt = f"""Hãy đọc kỹ đoạn hội thoại dưới đây và trích xuất TẤT CẢ các thực thể có tên (NER) quan trọng (ví dụ: Tên người, Khóa học, Giá tiền, Chứng chỉ, Tổ chức, Kênh liên lạc...).
Trình bày kết quả thành một bảng Markdown có 2 cột: [Loại thực thể (Type), Văn bản trích xuất (Text)].
Chỉ trả về bảng, không giải thích thêm.

### NỘI DUNG HỘI THOẠI:
{transcript}"""

    payload = {
        "model": review_model,
        "messages": [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.1
    }

    try:
        with httpx.Client(timeout=300.0) as client:
            res = client.post(f"{API_URL}/v1/llm/chat", headers=headers, json=payload)
            res.raise_for_status()
            data = res.json()
            out = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not out:
                out = data.get("response", {}).get("choices", [{}])[0].get("message", {}).get("content", str(data))
            return out
    except Exception as e:
        print(f"Lỗi khi gọi LLM Baseline: {e}")
        return f"Lỗi gọi LLM: {str(e)}"



def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    
    # 1. ĐỌC DANH SÁCH MODEL TỪ CONFIG
    models_to_test = []
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            cfg = json.load(f)
            models_to_test = cfg.get("models_to_test", [])
            
    if not models_to_test:
        models_to_test = ["qwen2.5:7b"] # Fallback an toàn
    
    # 2. ĐỌC KẾT QUẢ ĐÁNH GIÁ (evaluation_results.json)
    if not os.path.exists(INPUT_FILE):
        print(f"❌ Không tìm thấy file: {INPUT_FILE}")
        return

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"❌ Lỗi cú pháp JSON trong file đầu vào: {e}")
            return
        
    all_calls = data.get("fast_path", []) + data.get("map_reduce", [])
    if not all_calls:
        print("❌ Không tìm thấy cuộc gọi nào trong dữ liệu.")
        return
        
    # 3. QUÉT DỮ LIỆU ĐỂ TÌM CÁC CUỘC GỌI CÓ CHỨA ENTITIES (LỌC LỖI FORMAT)
    valid_calls = []
    for call in all_calls:
        call_id = call.get("id", "Unknown_ID")
        is_mr = call.get("is_mr", False)
        transcript = call.get("transcript", "")
        if not transcript:
            continue
            
        combinations = []
        model_results = call.get("model_results", {})
        
        for model_name, result in model_results.items():
            for ev in result.get("evals", []):
                prompt_name = ev.get("prompt_name", "Unknown_Prompt")
                output_str = ev.get("output", "")
                input_prompt_text = ev.get("input_prompt", "")
                
                entities = None
                try:
                    if isinstance(output_str, dict):
                        entities = output_str.get("entities")
                    else:
                        out_data = json.loads(output_str)
                        entities = out_data.get("entities")
                except:
                    pass
                
                # Chỉ lấy những trường hợp parse được mảng entities
                if entities is not None and isinstance(entities, list):
                    combinations.append({
                        "model": model_name,
                        "prompt": prompt_name,
                        "input_prompt": input_prompt_text,
                        "entities": entities
                    })
        
        # Nếu cuộc gọi này có ít nhất 1 trường hợp trích xuất thành công, đưa vào danh sách chọn
        if combinations:
            valid_calls.append({
                "id": call_id,
                "is_mr": is_mr,
                "transcript": transcript,
                "combinations": combinations
            })
            
    if not valid_calls:
        print("❌ Không có cuộc gọi nào parse được entities (có thể toàn bộ kết quả đều bị lỗi JSON).")
        return
        
    # 4. HIỂN THỊ MENU CHO NGƯỜI DÙNG CHỌN CUỘC GỌI
    print("\n" + "="*80)
    print(" DANH SÁCH CÁC CUỘC GỌI ĐÃ PHÂN TÍCH (CÓ NER HỢP LỆ)")
    print("="*80)
    for idx, c in enumerate(valid_calls, 1):
        mode = "MAP-REDUCE" if c["is_mr"] else "FAST PATH"
        print(f" {idx:2d}. ID Cuộc Gọi: {c['id']} | Loại: {mode}")
        print(f"     ✅ Bắt được {len(c['combinations'])} trường hợp (Prompt - Model)")
        print()
        
    try:
        call_choice = input(f"👉 Nhập số thứ tự cuộc gọi muốn Review (1 - {len(valid_calls)}): ").strip()
        call_idx = int(call_choice) - 1
        if call_idx < 0 or call_idx >= len(valid_calls):
            raise ValueError()
        selected_call = valid_calls[call_idx]
    except:
        print("❌ Lựa chọn không hợp lệ, thoát chương trình.")
        return
        
    # 5. HIỂN THỊ MENU CHO NGƯỜI DÙNG CHỌN MODEL GIÁM KHẢO
    print("\n" + "="*80)
    print(" CHỌN MODEL ĐỂ LÀM GIÁM KHẢO (ĐỌC & SỬA NER)")
    print("="*80)
    for idx, m in enumerate(models_to_test, 1):
        print(f" {idx}. {m}")
        
    try:
        model_choice = input(f"👉 Nhập số (1 - {len(models_to_test)}): ").strip()
        model_idx = int(model_choice) - 1
        if model_idx < 0 or model_idx >= len(models_to_test):
            raise ValueError()
        review_model = models_to_test[model_idx]
    except:
        print("❌ Lựa chọn không hợp lệ, thoát chương trình.")
        return
        
    # 6. TIẾN HÀNH CHẠY REVIEW TRÊN CUỘC GỌI ĐÃ CHỌN
    print(f"\n🚀 Bắt đầu đánh giá Cuộc Gọi {selected_call['id']}")
    print(f"🤖 Giám khảo: {review_model}")
    print("-"*50)
    
    # Khởi tạo nội dung Markdown
    md_content = [
        f"# BÁO CÁO TỔNG HỢP & SỬA LỖI NER",
        f"- **ID Cuộc gọi:** `{selected_call['id']}`",
        f"- **Loại File:** `{'MAP-REDUCE' if selected_call['is_mr'] else 'FAST PATH'}`",
        f"- **Model Giám Khảo (Reviewer):** `{review_model}`",
        "",
        "## 1. PROMPT THỰC TẾ GỬI CHO MODEL GIÁM KHẢO (REVIEWER)",
        "**System Prompt:**",
        "```text",
        "Bạn là một chuyên gia đánh giá và trích xuất thực thể có tên (NER).",
        "```",
        "**User Prompt (Cấu trúc mẫu):**",
        "```text",
        "Dưới đây là một đoạn hội thoại (Transcript) và danh sách các thực thể (Entities) đã được trích xuất bởi một mô hình AI ({model_name}) thông qua prompt ({prompt_name}).",
        "",
        "### NỘI DUNG HỘI THOẠI (TRANSCRIPT)",
        "[... NỘI DUNG CUỘC GỌI GỐC ...]",
        "",
        "### CÁC THỰC THỂ ĐÃ TRÍCH XUẤT BAN ĐẦU (TỪ MÔ HÌNH)",
        "[... DANH SÁCH ENTITIES ĐƯỢC TRÍCH XUẤT DƯỚI DẠNG JSON ...]",
        "",
        "### YÊU CẦU:",
        "1. Đọc kỹ đoạn hội thoại và đối chiếu với danh sách các thực thể đã trích xuất ở trên.",
        "2. Nhận xét xem mô hình đã trích xuất đúng, thiếu, hay sai (ảo giác/nhầm lẫn) những thực thể nào.",
        "3. Sửa lại cho đúng và xuất kết quả thành một bảng Markdown.",
        "Bảng Markdown phải có các cột: [Loại thực thể (Type), Trích xuất ban đầu (Original Text), Sửa lại (Corrected Text), Nhận xét/Lý do (Reason)]",
        "",
        "Chỉ trả về nội dung bảng Markdown và một đoạn nhận xét ngắn gọn, KHÔNG cần thêm các giải thích thừa thãi ngoài lề.",
        "```",
        "",
        "## 2. KẾT QUẢ ĐỐI CHIẾU CỦA TỪNG TRƯỜNG HỢP",
        ""
    ]
    
    for idx, comb in enumerate(selected_call["combinations"], 1):
        print(f"⏳ [{idx}/{len(selected_call['combinations'])}] Đang duyệt: {comb['model']} + {comb['prompt']}...")
        
        review_result = review_entities_with_local_llm(
            selected_call['transcript'],
            comb['model'],
            comb['prompt'],
            comb['entities'],
            review_model
        )
        
        # Thêm kết quả vào báo cáo
        md_content.extend([
            f"### Trường hợp {idx}: Model `{comb['model']}` | Prompt `{comb['prompt']}`",
            "",
            "**Bảng đánh giá & Đề xuất sửa đổi từ Giám Khảo:**",
            review_result,
            "",
            "---\n"
        ])
        
    print(f"⏳ Đang yêu cầu Giám khảo {review_model} tự trích xuất NER độc lập (Baseline)...")
    baseline_result = extract_ner_baseline(selected_call['transcript'], review_model)
    
    md_content.extend([
        "## 3. KẾT QUẢ TRÍCH XUẤT CỦA MODEL GIÁM KHẢO CHỈ TẬP TRUNG VÀO NER",
        "### 3.1 PROMPT GỬI VÀO (CHỈ GỬI ĐOẠN HỘI THOẠI GỐC CHO MODEL GIÁM KHẢO)",
        "**System Prompt:**",
        "```text",
        "Bạn là một AI chuyên trích xuất thực thể có tên (NER).",
        "```",
        "**User Prompt:**",
        "```text",
        "Hãy đọc kỹ đoạn hội thoại dưới đây và trích xuất TẤT CẢ các thực thể có tên (NER) quan trọng (ví dụ: Tên người, Khóa học, Giá tiền, Chứng chỉ, Tổ chức, Kênh liên lạc...).",
        "Trình bày kết quả thành một bảng Markdown có 2 cột: [Loại thực thể (Type), Văn bản trích xuất (Text)].",
        "Chỉ trả về bảng, không giải thích thêm.",
        "",
        "### NỘI DUNG HỘI THOẠI:",
        "[... NỘI DUNG CUỘC GỌI GỐC ...]",
        "```",
        "",
        "### 3.2 KẾT QUẢ",
        baseline_result,
        ""
    ])
        
    # Lưu file báo cáo
    safe_call_id = selected_call['id'].replace(":", "_").replace("/", "_")
    out_file = os.path.join(REPORT_DIR, f"NER_Review_Call_{safe_call_id}.md")
    
    with open(out_file, "w", encoding="utf-8") as f:
        f.write("\n".join(md_content))
        
    print(f"\n✅ Xong! Toàn bộ đánh giá đã được lưu chung vào file: {out_file}")


if __name__ == "__main__":
    main()
