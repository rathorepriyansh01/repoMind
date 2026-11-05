from __future__ import annotations

import math
import re
from typing import Any

from app.db import db, dumps, loads
from app.services.local_embeddings import embed_query


# Extract useful words from the user's question
TOKEN_RE = re.compile(r"[a-zA-Z_][a-zA-Z0-9_]{2,}")


def tokenize(text: str) -> list[str]:
    """
    Convert text into searchable tokens.
    """
    return TOKEN_RE.findall(text.lower())


def cosine(a: list[float], b: list[float]) -> float:
    """
    Calculate cosine similarity between two embedding vectors.
    """

    if not a or not b or len(a) != len(b):
        return 0.0

    dot = sum(x * y for x, y in zip(a, b))

    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


async def replace_chunks(
    repository_id: str,
    chunks: list[dict[str, Any]],
    embeddings: list[list[float]] | None,
) -> None:
    """
    Replace all existing repository chunks and store new chunks
    along with their embeddings.
    """

    conn = db()

    # Find existing chunks for this repository
    existing = await conn.execute(
        "SELECT id FROM chunks WHERE repository_id = ?",
        (repository_id,),
    )

    rows = await existing.fetchall()
    chunk_ids = [row["id"] for row in rows]

    # Remove old FTS records first
    if chunk_ids:
        placeholders = ",".join("?" for _ in chunk_ids)

        await conn.execute(
            f"DELETE FROM chunks_fts WHERE chunk_id IN ({placeholders})",
            chunk_ids,
        )

    # Remove old chunks
    await conn.execute(
        "DELETE FROM chunks WHERE repository_id = ?",
        (repository_id,),
    )

    # Insert fresh chunks
    for index, chunk in enumerate(chunks):

        embedding_json = None

        if embeddings and index < len(embeddings):
            embedding_json = dumps(embeddings[index])

        cursor = await conn.execute(
            """
            INSERT INTO chunks (
                repository_id,
                file_path,
                start_line,
                end_line,
                content,
                content_hash,
                language,
                embedding_json
            )
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

        # Add chunk to Full Text Search table
        await conn.execute(
            """
            INSERT INTO chunks_fts (
                content,
                file_path,
                chunk_id
            )
            VALUES (?, ?, ?)
            """,
            (
                chunk["content"],
                chunk["file_path"],
                cursor.lastrowid,
            ),
        )

    await conn.commit()


async def retrieve(
    repository_id: str,
    question: str,
    limit: int = 6,
) -> tuple[list[dict[str, Any]], str]:
    """
    Retrieve the most relevant repository chunks.

    Uses:
    1. Keyword search using SQLite FTS
    2. Semantic search using local embeddings
    3. Hybrid scoring to combine both methods
    """

    conn = db()

    keyword_scores: dict[int, float] = {}
    semantic_scores: dict[int, float] = {}

    terms = tokenize(question)

    # --------------------------------------------------
    # STEP 1: KEYWORD SEARCH
    # --------------------------------------------------

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

            fts_rows = await cursor.fetchall()

            for row in fts_rows:

                chunk_id = row["chunk_id"]

                if chunk_id is not None:

                    # SQLite BM25 returns lower/negative values
                    rank = row["rank"]

                    score = float(-rank) if rank is not None else 0.0

                    keyword_scores[chunk_id] = score

        except Exception:
            # If FTS fails, normal lexical search below will still work
            pass

    # --------------------------------------------------
    # STEP 2: LOAD ALL REPOSITORY CHUNKS
    # --------------------------------------------------

    cursor = await conn.execute(
        """
        SELECT
            id,
            file_path,
            start_line,
            end_line,
            content,
            language,
            embedding_json
        FROM chunks
        WHERE repository_id = ?
        """,
        (repository_id,),
    )

    rows = [dict(row) for row in await cursor.fetchall()]

    if not rows:
        return [], "empty"

    # --------------------------------------------------
    # STEP 3: FALLBACK LEXICAL SCORING
    # --------------------------------------------------

    if not keyword_scores:

        for row in rows:

            content = (row["content"] or "").lower()
            path = (row["file_path"] or "").lower()

            score = 0.0

            for term in terms:

                # File path match gets higher importance
                if term in path:
                    score += 3.0

                # Content match
                score += float(content.count(term))

            if score > 0:
                keyword_scores[row["id"]] = score

    # --------------------------------------------------
    # STEP 4: LOCAL SEMANTIC SEARCH
    # --------------------------------------------------

    try:

        query_vector = embed_query(question)

        if query_vector:

            for row in rows:

                embedding = loads(
                    row.get("embedding_json"),
                    None,
                )

                if isinstance(embedding, list) and embedding:

                    similarity = cosine(
                        query_vector,
                        embedding,
                    )

                    # Keep only useful semantic matches
                    if similarity > 0:
                        semantic_scores[row["id"]] = similarity

    except Exception:
        # Semantic search failure should not break chatbot
        semantic_scores = {}

    # --------------------------------------------------
    # STEP 5: HYBRID SCORE
    # --------------------------------------------------

    combined_scores: dict[int, float] = {}

    all_chunk_ids = (
        set(keyword_scores.keys())
        | set(semantic_scores.keys())
    )

    for chunk_id in all_chunk_ids:

        keyword_score = keyword_scores.get(
            chunk_id,
            0.0,
        )

        semantic_score = semantic_scores.get(
            chunk_id,
            0.0,
        )

        # Combine keyword and semantic relevance
        combined_scores[chunk_id] = (
            keyword_score
            + semantic_score * 8.0
        )

    # --------------------------------------------------
    # STEP 6: DETERMINE RETRIEVAL MODE
    # --------------------------------------------------

    if keyword_scores and semantic_scores:
        mode = "hybrid"

    elif semantic_scores:
        mode = "semantic"

    elif keyword_scores:
        mode = "keyword"

    else:
        mode = "fallback-first-chunks"

    # --------------------------------------------------
    # STEP 7: RANK RESULTS
    # --------------------------------------------------

    ranked_ids = sorted(
        combined_scores,
        key=lambda chunk_id: combined_scores[chunk_id],
        reverse=True,
    )[:limit]

    rows_by_id = {
        row["id"]: row
        for row in rows
    }

    results: list[dict[str, Any]] = []

    for chunk_id in ranked_ids:

        row = rows_by_id.get(chunk_id)

        if not row:
            continue

        results.append(
            {
                "id": row["id"],
                "path": row["file_path"],
                "start_line": row["start_line"],
                "end_line": row["end_line"],
                "content": row["content"],
                "language": row["language"],
                "score": combined_scores[chunk_id],
            }
        )

    # --------------------------------------------------
    # STEP 8: FINAL FALLBACK
    # --------------------------------------------------

    if not results:

        for row in rows[:limit]:

            results.append(
                {
                    "id": row["id"],
                    "path": row["file_path"],
                    "start_line": row["start_line"],
                    "end_line": row["end_line"],
                    "content": row["content"],
                    "language": row["language"],
                    "score": 0.0,
                }
            )

    return results, mode