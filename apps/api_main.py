"""API entrypoint - FastAPI REST + WebSocket.

Usage:
    uvicorn apps.api_main:app --reload --host 0.0.0.0 --port 8000
"""

from voiceiq.app.create_app import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("apps.api_main:app", host="0.0.0.0", port=8000, reload=True)
