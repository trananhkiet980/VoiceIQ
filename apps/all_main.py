"""Local development entrypoint - boots API server.

For production, use separate entrypoints (api_main, relay_main, etc).

Usage:
    uv run python apps/all_main.py
"""

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("apps.api_main:app", host="0.0.0.0", port=8000, reload=True)
