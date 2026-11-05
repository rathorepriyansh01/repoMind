from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings
from app.logging_utils import safe_error
from app.services.analyzer import analyze_repository_evidence
from app.services.chunking import chunk_files
from app.services.github_client import GitHubError, collect_repository
from app.services.github_url import parse_repo_url
from app.services.llm import LLMProvider, enrich_report
from app.services.retrieval import replace_chunks
from app.services.store import find_cached, save_repository, update_job

logger = logging.getLogger(__name__)


async def run_analysis_job(job_id: str, url: str, force: bool = False) -> None:
    try:
        await update_job(job_id, status="running", progress="Validating repository URL")
        parsed = parse_repo_url(url)
        await update_job(job_id, progress="Fetching GitHub metadata")
        payload = await collect_repository(parsed)
        settings = get_settings()
        embedding_model = settings.embedding_model.strip() or "keyword"
        cached = await find_cached(payload["facts"]["full_name"], payload["commit_sha"], embedding_model)
        if cached and not force:
            await update_job(
                job_id,
                status="succeeded",
                repository_id=cached["id"],
                progress="Reused cached analysis for this commit",
                error=None,
            )
            return
        await update_job(job_id, progress="Analyzing files")
        report = analyze_repository_evidence(payload)
        await update_job(job_id, progress="Optional LLM summary")
        report = await enrich_report(report, payload.get("files") or [])
        repo_id = await save_repository(payload, report, embedding_model)
        await update_job(job_id, progress="Indexing chunks")
        chunks = chunk_files(payload.get("files") or [], payload["commit_sha"])
        embeddings = None
        provider = LLMProvider()
        if settings.embeddings_configured:
            embeddings = await provider.embed([c["content"][:4000] for c in chunks])
            if embeddings is None:
                report.setdefault("limitations", []).append(
                    "Embedding provider was unavailable; chat retrieval uses keyword search."
                )
        await replace_chunks(repo_id, chunks, embeddings)
        await update_job(job_id, status="succeeded", repository_id=repo_id, progress="Complete", error=None)
    except GitHubError as exc:
        logger.info("Analysis GitHub error: %s", exc)
        await update_job(job_id, status="failed", error=str(exc), progress="Failed")
    except ValueError as exc:
        await update_job(job_id, status="failed", error=str(exc), progress="Failed")
    except Exception as exc:
        logger.exception("Analysis failed")
        await update_job(
            job_id,
            status="failed",
            error=f"Repository analysis failed ({safe_error(exc)}).",
            progress="Failed",
        )


async def analyze_sync_for_tests(url: str) -> dict[str, Any]:
    """Used by tests that need a complete analysis without polling."""
    parsed = parse_repo_url(url)
    payload = await collect_repository(parsed)
    report = analyze_repository_evidence(payload)
    embedding_model = get_settings().embedding_model.strip() or "keyword"
    repo_id = await save_repository(payload, report, embedding_model)
    chunks = chunk_files(payload.get("files") or [], payload["commit_sha"])
    await replace_chunks(repo_id, chunks, None)
    return {"id": repo_id, "report": report, "payload": payload}
