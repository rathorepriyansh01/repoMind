from __future__ import annotations

import logging
from typing import Any

from app.config import get_settings
from app.logging_utils import safe_error
from app.services.analyzer import analyze_repository_evidence
from app.services.chunking import chunk_files
from app.services.github_client import GitHubError, collect_repository
from app.services.github_url import parse_repo_url
from app.services.llm import enrich_report
from app.services.local_embeddings import embed_documents
from app.services.retrieval import replace_chunks
from app.services.store import find_cached, save_repository, update_job

logger = logging.getLogger(__name__)


async def run_analysis_job(
    job_id: str,
    url: str,
    force: bool = False,
) -> None:
    """
    Complete repository analysis pipeline.

    Flow:
    GitHub Repository
        -> Fetch repository data
        -> Analyze repository structure
        -> Generate optional LLM report
        -> Chunk repository files
        -> Generate local semantic embeddings
        -> Store chunks and embeddings
    """

    try:
        # Step 1: Validate repository URL
        await update_job(
            job_id,
            status="running",
            progress="Validating repository URL",
        )

        parsed = parse_repo_url(url)

        # Step 2: Fetch repository metadata and files
        await update_job(
            job_id,
            progress="Fetching GitHub metadata",
        )

        payload = await collect_repository(parsed)

        settings = get_settings()

        # Use embedding model name for cache identification
        embedding_model = (
            settings.embedding_model.strip()
            or "BAAI/bge-small-en-v1.5"
        )

        # Step 3: Check cached analysis
        cached = await find_cached(
            payload["facts"]["full_name"],
            payload["commit_sha"],
            embedding_model,
        )

        if cached and not force:
            await update_job(
                job_id,
                status="succeeded",
                repository_id=cached["id"],
                progress="Reused cached analysis for this commit",
                error=None,
            )
            return

        # Step 4: Analyze repository
        await update_job(
            job_id,
            progress="Analyzing files",
        )

        report = analyze_repository_evidence(payload)

        # Step 5: Generate optional LLM summary
        await update_job(
            job_id,
            progress="Generating AI repository summary",
        )

        report = await enrich_report(
            report,
            payload.get("files") or [],
        )

        # Step 6: Save repository analysis
        repo_id = await save_repository(
            payload,
            report,
            embedding_model,
        )

        # Step 7: Create chunks from repository files
        await update_job(
            job_id,
            progress="Chunking repository files",
        )

        chunks = chunk_files(
            payload.get("files") or [],
            payload["commit_sha"],
        )

        # Step 8: Generate local semantic embeddings
        embeddings = None

        if chunks:
            try:
                await update_job(
                    job_id,
                    progress="Generating local semantic embeddings",
                )

                texts = [
                    chunk["content"][:4000]
                    for chunk in chunks
                ]

                embeddings = embed_documents(texts)

                logger.info(
                    "Generated %s local embeddings successfully",
                    len(embeddings),
                )

            except Exception as exc:
                logger.warning(
                    "Local embedding generation failed: %s",
                    safe_error(exc),
                )

                report.setdefault(
                    "limitations",
                    [],
                ).append(
                    "Local semantic embeddings could not be generated; "
                    "chat retrieval will use keyword search."
                )

        # Step 9: Store chunks and embeddings
        await update_job(
            job_id,
            progress="Saving search index",
        )

        await replace_chunks(
            repo_id,
            chunks,
            embeddings,
        )

        # Step 10: Mark analysis as complete
        await update_job(
            job_id,
            status="succeeded",
            repository_id=repo_id,
            progress="Complete",
            error=None,
        )

    except GitHubError as exc:
        logger.info(
            "Analysis GitHub error: %s",
            exc,
        )

        await update_job(
            job_id,
            status="failed",
            error=str(exc),
            progress="Failed",
        )

    except ValueError as exc:
        await update_job(
            job_id,
            status="failed",
            error=str(exc),
            progress="Failed",
        )

    except Exception as exc:
        logger.exception("Analysis failed")

        await update_job(
            job_id,
            status="failed",
            error=(
                f"Repository analysis failed "
                f"({safe_error(exc)})."
            ),
            progress="Failed",
        )


async def analyze_sync_for_tests(
    url: str,
) -> dict[str, Any]:
    """
    Used by tests that need a complete analysis
    without polling.
    """

    parsed = parse_repo_url(url)

    # Fetch repository
    payload = await collect_repository(parsed)

    # Analyze repository
    report = analyze_repository_evidence(payload)

    # Get embedding model name
    settings = get_settings()

    embedding_model = (
        settings.embedding_model.strip()
        or "BAAI/bge-small-en-v1.5"
    )

    # Save repository
    repo_id = await save_repository(
        payload,
        report,
        embedding_model,
    )

    # Create repository chunks
    chunks = chunk_files(
        payload.get("files") or [],
        payload["commit_sha"],
    )

    # Generate local embeddings
    embeddings = None

    if chunks:
        try:
            texts = [
                chunk["content"][:4000]
                for chunk in chunks
            ]

            embeddings = embed_documents(texts)

            logger.info(
                "Generated %s test embeddings successfully",
                len(embeddings),
            )

        except Exception as exc:
            logger.warning(
                "Test embedding generation failed: %s",
                safe_error(exc),
            )

    # Save chunks and embeddings
    await replace_chunks(
        repo_id,
        chunks,
        embeddings,
    )

    return {
        "id": repo_id,
        "report": report,
        "payload": payload,
    }