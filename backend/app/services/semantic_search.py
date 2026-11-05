import numpy as np

from app.services.local_embeddings import embed_texts


def search_chunks(
    question: str,
    chunks: list[dict],
    top_k: int = 6,
) -> list[dict]:
    """Return the most semantically relevant repository chunks."""

    if not chunks:
        return []

    query_embedding = np.array(
        embed_texts([question])[0]
    )

    results = []

    for chunk in chunks:
        vector = chunk.get("embedding")

        if not vector:
            continue

        score = float(
            np.dot(query_embedding, np.array(vector))
        )

        results.append({
            **chunk,
            "score": score,
        })

    results.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return results[:top_k]