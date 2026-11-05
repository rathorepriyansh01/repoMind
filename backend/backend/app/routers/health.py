from fastapi import APIRouter

from app.config import get_settings
from app.db import db

router = APIRouter()


@router.get("/api/v1/health")
async def health():
    return {"status": "ok", "service": "repomind-ai"}


@router.get("/api/v1/ready")
async def ready():
    settings = get_settings()
    database_ok = False
    try:
        cursor = await db().execute("SELECT 1")
        await cursor.fetchone()
        database_ok = True
    except Exception:
        database_ok = False
    status = "ok" if database_ok else "degraded"
    return {
        "status": status,
        "database": database_ok,
        "llm_configured": settings.llm_configured,
        "embeddings_configured": settings.embeddings_configured,
        "github_token_configured": bool(settings.github_token.strip()),
        "notes": [
            "Landing page and public metadata analysis work without an LLM key.",
            "Natural-language summaries and chat synthesis require LLM_BASE_URL, LLM_API_KEY, and LLM_MODEL.",
            "Semantic retrieval requires EMBEDDING_MODEL plus an embedding-compatible provider; otherwise keyword search is used.",
        ],
    }
