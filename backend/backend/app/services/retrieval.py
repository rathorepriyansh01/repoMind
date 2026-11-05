from __future__ import annotations

import math
import re
from typing import Any

from app.db import db, dumps, loads
from app.services.llm import LLMProvider

TOKEN_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]{2,}")


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall(text.lower())


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


async def replace_chunks(repository_id: str, chunks: list[dict[str, Any]], embeddings: list[list[float]] | None) -> None:
    conn = db()
    existing = await conn.execute("SELECT id FROM chunks WHERE repository_id = ?", (repository_id,))
    rows = await existing.fetchall()
    ids = [row["id"] for row in rows]
    if ids:
        placeholders = ",".join("?" for _ in ids)
        await conn.execute(f"DELETE FROM chunks_fts WHERE chunk_id IN ({placeholders})", ids)
    await conn.execute("DELETE FROM chunks WHERE repository_id = ?", (repository_id,))
    for index, chunk in enumerate(chunks):
        embedding_json = dumps(embeddings[index]) if embeddings and index < len(embeddings) else None
        cursor = await conn.execute(
            """
            INSERT INTO chunks (repository_id, file_path, start_line, end_line, content, content_hash, language, embedding_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                repository_id,
                chunk["file_path"],
                chunk["start_line"],
                chunk["end_line"],
                chunk["content"],
                chunk.get("content_hash"),
                chunk.get("language"),
                embedding_json,
            ),
        )
        await conn.execute(
            "INSERT INTO chunks_fts (content, file_path, chunk_id) VALUES (?, ?, ?)",
            (chunk["content"], chunk["file_path"], cursor.lastrowid),
        )
    await conn.commit()


async def retrieve(repository_id: str, question: str, limit: int = 6) -> tuple[list[dict[str, Any]], str]:
    conn = db()
    mode = "keyword"
    scored: dict[int, float] = {}
    terms = tokenize(question)
    query = " OR ".join(terms[:12]) if terms else None
    if query:
        try:
            cursor = await conn.execute(
                """
                SELECT chunk_id, bm25(chunks_fts) AS rank
                FROM chunks_fts
                WHERE chunks_fts MATCH ?
                ORDER BY rank
                LIMIT 40
                """,
                (query,),
            )
            for row in await cursor.fetchall():
                if row["chunk_id"] is not None:
                    scored[row["chunk_id"]] = float(-row["rank"]) if row["rank"] is not None else 0.0
        except Exception:
            pass
    cursor = await conn.execute(
        "SELECT id, file_path, start_line, end_line, content, language, embedding_json FROM chunks WHERE repository_id = ?",
        (repository_id,),
    )
    rows = [dict(row) for row in await cursor.fetchall()]
    if not scored:
        for row in rows:
            content = (row["content"] or "").lower()
            path = (row["file_path"] or "").lower()
            score = sum(3 for t in terms if t in path) + sum(content.count(t) for t in terms)
            if score:
                scored[row["id"]] = float(score)
    provider = LLMProvider()
    query_vectors = await provider.embed([question]) if provider.settings.embeddings_configured else None
    if query_vectors:
        qv = query_vectors[0]
        for row in rows:
            embedding = loads(row.get("embedding_json"), None)
            if isinstance(embedding, list) and embedding:
                semantic = cosine(qv, embedding)
                scored[row["id"]] = scored.get(row["id"], 0.0) + semantic * 8
                mode = "hybrid"
    ranked_ids = sorted(scored, key=lambda i: scored[i], reverse=True)[:limit]
    by_id = {row["id"]: row for row in rows}
    results = []
    for chunk_id in ranked_ids:
        row = by_id.get(chunk_id)
        if not row:
            continue
        results.append({
            "id": row["id"],
            "path": row["file_path"],
            "start_line": row["start_line"],
            "end_line": row["end_line"],
            "content": row["content"],
            "language": row["language"],
            "score": scored[chunk_id],
        })
    if not results:
        # fallback: first files
        for row in rows[:limit]:
            results.append({
                "id": row["id"],
                "path": row["file_path"],
                "start_line": row["start_line"],
                "end_line": row["end_line"],
                "content": row["content"],
                "language": row["language"],
                "score": 0,
            })
        mode = "fallback-first-chunks" if results else "empty"
    return results, mode
