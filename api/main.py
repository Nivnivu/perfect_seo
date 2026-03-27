import sys
from pathlib import Path

# Add project root to path so orchestrator/publisher/tools are importable
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import sites, pipelines, history, gsc, posts

app = FastAPI(
    title="SEO Blog Engine API",
    version="1.0.0",
    description="Local API for the open-source SEO Blog Engine",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sites.router, prefix="/api/sites", tags=["sites"])
app.include_router(pipelines.router, prefix="/api/pipelines", tags=["pipelines"])
app.include_router(history.router, prefix="/api/history", tags=["history"])
app.include_router(gsc.router, prefix="/api/gsc", tags=["gsc"])
app.include_router(posts.router, prefix="/api/posts", tags=["posts"])


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
