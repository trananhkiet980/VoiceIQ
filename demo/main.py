import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from demo.routers import labels, simulate, taxonomy, transcripts, websocket
from voiceiq.app.container import Container


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.container = Container()
    await app.state.container.init()
    yield
    await app.state.container.shutdown()


app = FastAPI(title="VoiceIQ - Demo Testing API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/demo")
async def get_demo_page():
    file_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    try:
        with open(file_path, encoding="utf-8") as f:
            html = f.read()
        return HTMLResponse(content=html)
    except Exception as e:
        return HTMLResponse(content=f"Error loading index.html: {str(e)}", status_code=500)

@app.get("/explorer")
async def get_explorer_page():
    file_path = os.path.join(os.path.dirname(__file__), "templates", "explorer.html")
    try:
        with open(file_path, encoding="utf-8") as f:
            html = f.read()
        return HTMLResponse(content=html)
    except Exception as e:
        return HTMLResponse(content=f"Error loading explorer.html: {str(e)}", status_code=500)


app.include_router(labels.router)
app.include_router(transcripts.router)
app.include_router(simulate.router)
app.include_router(websocket.router)
app.include_router(taxonomy.router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
