import asyncio
import json
import os

from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/postgres")

async def extract_calls():
    print("Bắt đầu trích xuất...")
    with open("scratch/eval_config.json", encoding="utf-8-sig") as f:
        config = json.load(f)

    tenant_id = config.get("tenant_id")
    call_ids = config.get("call_ids", [])
    output_path = config.get("input_dataset_path", "scratch/sample_dataset.json")
    db_config_path = "scratch/database_config.json"

    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    dataset = []
    db_config = {"topics": [], "intents": [], "keywords": [], "qa_criteria": []}

    async with async_session() as session:
        # 1. Trích xuất Transcripts
        print("Đang trích xuất Transcripts...")
        for cid in call_ids:
            query = text("""
                SELECT call_id, full_text_combined, transcript_json, duration_seconds, turn_count
                FROM transcripts 
                WHERE tenant_id = :tenant_id AND call_id = :call_id
            """)
            result = await session.execute(query, {"tenant_id": tenant_id, "call_id": cid})
            row = result.fetchone()

            if row:
                transcript_text = row.full_text_combined
                if not transcript_text and row.transcript_json:
                    turns = row.transcript_json if isinstance(row.transcript_json, list) else json.loads(row.transcript_json)
                    transcript_text = "\n".join([f"{t.get('speaker', 'Unknown')}: {t.get('text', '')}" for t in turns])

                dataset.append({
                    "id": str(row.call_id),
                    "transcript": transcript_text or "",
                    "duration_seconds": float(row.duration_seconds) if row.duration_seconds else 0.0,
                    "turn_count": int(row.turn_count) if row.turn_count else 0
                })
                print(f" OK: {cid}")
            else:
                print(f" Not found: {cid}")

        # 2. Trích xuất Cấu hình Động (Topic, Intent, Keywords, QA)
        print("Đang trích xuất Cấu hình Động (Topic, Intent, QA)...")

        # Topics
        t_query = text("SELECT label_vi FROM topic_registry WHERE tenant_id = :tenant_id AND status = 'active'")
        t_res = await session.execute(t_query, {"tenant_id": tenant_id})
        db_config["topics"] = [r.label_vi for r in t_res.fetchall()]

        # Intents
        i_query = text("SELECT display_name_vi FROM intent_taxonomy WHERE tenant_id = :tenant_id AND status = 'active'")
        i_res = await session.execute(i_query, {"tenant_id": tenant_id})
        db_config["intents"] = [r.display_name_vi for r in i_res.fetchall()]

        # Keywords
        k_query = text("SELECT keyword FROM keyword_registry WHERE tenant_id = :tenant_id AND status = 'active'")
        k_res = await session.execute(k_query, {"tenant_id": tenant_id})
        db_config["keywords"] = [r.keyword for r in k_res.fetchall()]

        # QA Criteria
        q_query = text("SELECT name, description, scoring_type, score_value FROM scorecard_criteria WHERE tenant_id = :tenant_id")
        q_res = await session.execute(q_query, {"tenant_id": tenant_id})
        db_config["qa_criteria"] = [{"name": r.name, "description": r.description or "", "scoring_type": r.scoring_type, "score_weight_percent": float(r.score_value) if r.score_value else 0.0} for r in q_res.fetchall()]

    # Ghi file
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)
    print(f"✅ Đã lưu Transcripts vào {output_path}")

    with open(db_config_path, "w", encoding="utf-8") as f:
        json.dump(db_config, f, ensure_ascii=False, indent=2)
    print(f"✅ Đã lưu Cấu hình Động (Topic/Intent/QA) vào {db_config_path}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(extract_calls())
