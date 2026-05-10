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
    # Auto-start batch process on boot (resumes from where it left off)
    asyncio.create_task(_auto_batch())
    yield
    task.cancel()


async def _auto_batch():
    """Auto-trigger batch processing 60s after startup."""
    await asyncio.sleep(60)
    global _batch_task
    if _batch_task and not _batch_task.done():
        return  # already running
    from pipeline.process_batch import process_all_batched
    async def _run():
        await asyncio.to_thread(process_all_batched, stages=None, batch_size=3)
    _batch_task = asyncio.create_task(_run())


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


_batch_task = None

@app.post("/api/admin/batch-process")
async def batch_process(stages: str = "all", batch_size: int = 5):
    """Run full batch pipeline (scrape → extract → embed → cleanup) on Railway.

    Runs as background task — returns immediately. Check /api/admin/batch-status for progress.
    """
    global _batch_task

    if _batch_task and not _batch_task.done():
        return {"status": "already_running"}

    async def _run():
        import asyncio
        from pipeline.process_batch import process_all_batched
        stage_list = None if stages == "all" else [s.strip() for s in stages.split(",")]
        await asyncio.to_thread(process_all_batched, stages=stage_list, batch_size=batch_size)

    _batch_task = asyncio.create_task(_run())
    return {"status": "started", "stages": stages, "batch_size": batch_size}


@app.get("/api/admin/batch-status")
async def batch_status():
    """Check batch processing status."""
    global _batch_task

    if _batch_task is None:
        return {"status": "never_started"}
    if _batch_task.done():
        exc = _batch_task.exception()
        if exc:
            return {"status": "failed", "error": str(exc)}
        return {"status": "completed"}
    return {"status": "running"}
