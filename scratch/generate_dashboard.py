import json

def generate_dashboard():
    with open('scratch/eval_config.json', 'r', encoding='utf-8') as f:
        eval_cfg = json.load(f)
        
    with open('scratch/database_config.json', 'r', encoding='utf-8') as f:
        db_cfg = json.load(f)
        
    md_content = f"""# 🎛️ Bảng Điều Khiển Cấu Hình Thử Nghiệm (Experiment Dashboard)
*File này tổng hợp các cấu hình đang được sử dụng để chạy Test trong thư mục `scratch`, tách biệt hoàn toàn khỏi kết quả phân tích.*

---

## 1. ⚙️ Cấu Hình Chạy (Evaluation Config)
*(Đọc từ `eval_config.json`)*

- **Tenant ID:** `{eval_cfg.get('tenant_id', 'N/A')}`
- **Dataset đầu vào:** `{eval_cfg.get('input_dataset_path', 'N/A')}`
- **Báo cáo đầu ra:** `{eval_cfg.get('output_report_path', 'N/A')}`
- **Số lượng cuộc gọi Test:** `{len(eval_cfg.get('call_ids', []))}` calls

**🤖 Models tham gia Test:**
"""
    for m in eval_cfg.get('models_to_test', []):
        md_content += f"- `{m}`\n"
        
    md_content += "\n**📝 Các biến thể Prompt (Matrix):**\n"
    for p in eval_cfg.get('prompts_to_test', []):
        md_content += f"- **{p['name']}** (`{p['filepath']}`)\n"

    md_content += f"""
---

## 2. 🗄️ Cấu Hình Dữ Liệu Chuyên Môn (Database Config)
*(Đọc từ `database_config.json`)*

### 2.1. 🏷️ Danh sách Chủ đề (Topics) - Tổng: {len(db_cfg.get('topics', []))}
<details><summary>👉 Nhấn để xem toàn bộ Topics</summary>

"""
    for t in db_cfg.get('topics', []):
        md_content += f"- {t}\n"
        
    md_content += f"""
</details>

### 2.2. 🎯 Danh sách Mục đích (Intents) - Tổng: {len(db_cfg.get('intents', []))}
<details><summary>👉 Nhấn để xem toàn bộ Intents</summary>

"""
    for i in db_cfg.get('intents', []):
        md_content += f"- {i}\n"
        
    md_content += f"""
</details>

### 2.3. ⚖️ Tiêu chí Chấm điểm (QA Criteria) - Tổng: {len(db_cfg.get('qa_criteria', []))}
<details><summary>👉 Nhấn để xem chi tiết Bộ tiêu chí QA</summary>

| Tiêu chí (Criterion) | Kiểu chấm | Điểm | Bắt lỗi tự động (Auto-fail) |
|---|---|---|---|
"""
    for qa in db_cfg.get('qa_criteria', []):
        auto_fail = "🔴 Có" if qa.get('auto_fail') else "⚪ Không"
        md_content += f"| **{qa.get('criterion')}**<br>_{qa.get('description')}_ | `{qa.get('scoring_type')}` | {qa.get('score_weight_percent')}% | {auto_fail} |\n"
        
    md_content += """
</details>
"""

    # --- PHẦN 3: SCHEMA ---
    md_content += """
---

## 3. 📄 Cấu Trúc Dữ Liệu (Schemas)
*(Trích xuất từ `src/voiceiq/service/transcript/domain/schemas.py`)*
### Cấu trúc này hiện tại (3/9/2026) chưa được sử dụng với Ollama nội bộ hiện tại nhưng có ý nghĩa là chuẩn đầu ra mọi LLM để BE lấy dữ liệu và xử lý.
<details><summary>👉 Nhấn để xem cấu trúc JSON Schema yêu cầu LLM trả về</summary>

```python
"""
    
    # Đọc file schemas.py
    try:
        with open('src/voiceiq/service/transcript/domain/schemas.py', 'r', encoding='utf-8') as f:
            schemas_content = f.read()
            # Trích xuất V2_SHORT_SCHEMA
            if "V2_SHORT_SCHEMA = {" in schemas_content:
                start_idx = schemas_content.find("V2_SHORT_SCHEMA = {")
                md_content += schemas_content[start_idx:]
            else:
                md_content += "Không tìm thấy V2_SHORT_SCHEMA trong file."
    except Exception as e:
        md_content += f"Lỗi đọc file schemas: {str(e)}"
        
    md_content += """
```
</details>

---

## 4. 🧠 Danh sách Prompts (Ma trận thử nghiệm)
*(Các nội dung Prompt thực tế được nạp vào LLM)*

"""
    for p in eval_cfg.get('prompts_to_test', []):
        md_content += f"### 🔹 {p['name']}\n"
        md_content += f"*(File: `{p['filepath']}`)*\n"
        md_content += "<details><summary>👉 Nhấn để xem nội dung Prompt</summary>\n\n```text\n"
        try:
            with open(p['filepath'], 'r', encoding='utf-8') as pf:
                md_content += pf.read().strip()
        except Exception as e:
            md_content += f"Lỗi đọc file: {str(e)}"
        md_content += "\n```\n</details>\n\n"

    with open('scratch/report/configuration_dashboard.md', 'w', encoding='utf-8') as f:
        f.write(md_content)
        
if __name__ == "__main__":
    generate_dashboard()
