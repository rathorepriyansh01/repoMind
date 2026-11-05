from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.config import get_settings
from app.db import close_db, init_db
from app.logging_utils import configure_logging
from app.routers import analyze, health, repositories
from app.services.chat import answer_question
from app.services.store import get_repository


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    await init_db()
    yield
    await close_db()


app = FastAPI(
    title="RepoMind AI API",
    version="1.0.0",
    description="Public GitHub repository analyzer and grounded coding assistant.",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

app.include_router(health.router)
app.include_router(analyze.router)
app.include_router(repositories.router)


@app.middleware("http")
async def limit_body_size(request: Request, call_next):
    length = request.headers.get("content-length")
    if length and length.isdigit() and int(length) > 1_000_000:
        return JSONResponse({"detail": "Request is too large."}, status_code=413)
    return await call_next(request)


class LegacyChatRequest(BaseModel):
    repository_id: str
    question: str = Field(min_length=2, max_length=1500)
    chat_id: str | None = None


@app.post("/api/v1/chat")
async def legacy_chat(req: LegacyChatRequest):
    repo = await get_repository(req.repository_id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository analysis not found.")
    return await answer_question(repo, req.question, req.chat_id)
