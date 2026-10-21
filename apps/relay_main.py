# """Outbox Relay Worker.

# Scans the outbox table for unpublished events and processes them.
# Mock implementation for PoC - logs events instead of publishing to Kafka.

# Usage:
#     uv run python apps/relay_main.py
# """

# from __future__ import annotations

# import asyncio
# import logging

# from voiceiq.app.settings import get_settings
# from voiceiq.infrastructure.db.engine import create_db_engine, create_session_factory

# logger = logging.getLogger(__name__)
# logging.basicConfig(level=logging.INFO)

# MAX_ATTEMPTS = 5
# POLL_INTERVAL_SECONDS = 5


# async def relay_loop() -> None:
#     """Main relay loop - polls outbox and processes events."""
#     settings = get_settings()
#     engine = create_db_engine(settings.DATABASE_URL)
#     session_factory = create_session_factory(engine)
#     outbox_repo = FileOutboxRepo()

#     logger.info("Outbox Relay started. Polling every %ds...", POLL_INTERVAL_SECONDS)

#     while True:
#         try:
#             events = await outbox_repo.fetch_unpublished_batch(batch_size=100)

#             for event in events:
#                 event_id = event["event_id"]
#                 event_name = event["event_name"]

#                 try:
#                     # Mock publish - in production, this would publish to Kafka/RedPanda
#                     logger.info(
#                         "[MOCK PUBLISH] Event: %s | ID: %s | Aggregate: %s/%s",
#                         event_name,
#                         event_id,
#                         event["aggregate_type"],
#                         event["aggregate_id"],
#                     )

#                     # Mark as published
#                     await outbox_repo.mark_published(event_id)

#                 except Exception:
#                     attempts = await outbox_repo.increment_attempts(event_id)
#                     if attempts >= MAX_ATTEMPTS:
#                         logger.error(
#                             "Event %s exceeded max attempts, marking failed",
#                             event_id,
#                         )
#                         await outbox_repo.mark_failed(event_id)
#                     else:
#                         logger.warning(
#                             "Event %s failed, attempt %d/%d",
#                             event_id,
#                             attempts,
#                             MAX_ATTEMPTS,
#                         )

#         except Exception:
#             logger.exception("Relay loop error")

#         await asyncio.sleep(POLL_INTERVAL_SECONDS)


# if __name__ == "__main__":
#     asyncio.run(relay_loop())
