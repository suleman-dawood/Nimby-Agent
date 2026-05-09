"""FastAPI application for Nimby Agent."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.deps import configure_api_keys
from api.routers import auth, briefs, qa, search, site_context, submissions, tokens, watchers


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_api_keys()
    # Start background worker
    from workers.scheduler import worker_loop
    task = asyncio.create_task(worker_loop())
    yield
    task.cancel()


app = FastAPI(
    title="Nimby Agent API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://*.up.railway.app",
    ],
    allow_origin_regex=r"https://.*\.up\.railway\.app",
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(search.router)
app.include_router(briefs.router)
app.include_router(qa.router)
app.include_router(submissions.router)
app.include_router(tokens.router)
app.include_router(site_context.router)
app.include_router(watchers.router)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/admin/trigger-scrape")
async def trigger_scrape():
    """Manual trigger for scrape + notify cycle. For demos."""
    from workers.scheduler import trigger_scrape
    return await trigger_scrape()
