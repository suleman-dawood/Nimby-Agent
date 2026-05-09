"""FastAPI application for Nimby Agent."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.deps import configure_api_keys
from api.routers import auth, briefs, qa, search, site_context, submissions, tokens


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_api_keys()
    yield


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


@app.get("/api/health")
def health():
    return {"status": "ok"}
