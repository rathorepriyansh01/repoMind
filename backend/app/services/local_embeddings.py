from __future__ import annotations

import logging
from functools import lru_cache

from sentence_transformers import SentenceTransformer

from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    """
    Load the embedding model once and reuse it for all requests.
    """

    settings = get_settings()

    model_name = (
        getattr(settings, "embedding_model", None)
        or "BAAI/bge-small-en-v1.5"
    )

    logger.info("Loading local embedding model: %s", model_name)

    return SentenceTransformer(
        model_name,
        device="cpu",
    )


def embed_documents(texts: list[str]) -> list[list[float]]:
    """
    Create normalized embeddings for repository code chunks.
    """

    if not texts:
        return []

    cleaned_texts = [
        text.strip()
        for text in texts
        if text and text.strip()
    ]

    if not cleaned_texts:
        return []

    model = get_embedding_model()

    vectors = model.encode(
        cleaned_texts,
        normalize_embeddings=True,
        show_progress_bar=False,
        batch_size=16,
    )

    return vectors.tolist()


def embed_query(query: str) -> list[float] | None:
    """
    Create a normalized embedding for a user's search question.
    """

    if not query or not query.strip():
        return None

    model = get_embedding_model()

    vector = model.encode(
        query.strip(),
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    return vector.tolist()