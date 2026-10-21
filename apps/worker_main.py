"""Background Worker entrypoint.

Placeholder for Taskiq worker. In PoC, background tasks
are handled by FastAPI BackgroundTasks.

Usage (future):
    uv run taskiq worker voiceiq.infrastructure.tasks.broker:broker
"""

if __name__ == "__main__":
    print("Worker entrypoint - using FastAPI BackgroundTasks for PoC.")
