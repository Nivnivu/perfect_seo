import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

# Add project root to path so orchestrator/publisher/tools are importable
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from api.routes import sites, pipelines, history, gsc, posts, products, reviews, schedules, chat, upload  # noqa: E402


@asynccontextmanager
async def lifespan(app: FastAPI):
    from api.db import init_db
    from api.scheduler import scheduler, load_all
    init_db()
    load_all()
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(
    title="SEO Blog Engine API",
    version="1.0.0",
    description="Local API for the open-source SEO Blog Engine",
    lifespan=lifespan,
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
app.include_router(products.router, prefix="/api/products", tags=["products"])
app.include_router(reviews.router, prefix="/api/reviews", tags=["reviews"])
app.include_router(schedules.router, prefix="/api/schedules", tags=["schedules"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(upload.router, prefix="/api/upload", tags=["upload"])


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "1.0.0"}
