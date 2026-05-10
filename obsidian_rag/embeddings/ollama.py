"""Geração de embeddings via Ollama API."""

from functools import lru_cache

import httpx

from obsidian_rag.config import settings


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Gera embeddings via Ollama API (batch)."""
    response = httpx.post(
        f"{settings.ollama.base_url}/api/embed",
        json={"model": settings.ollama.embedding_model, "input": texts},
        timeout=120.0,
    )
    response.raise_for_status()
    return response.json()["embeddings"]


# LRU cache for single-query embeddings (avoids repeated Ollama calls)
@lru_cache(maxsize=settings.retrieval.embedding_cache_size)
def _cached_embed(text: str) -> tuple[float, ...]:
    """Cache embedding vectors for repeated queries."""
    return tuple(embed_texts([text])[0])


def get_query_embedding(text: str) -> list[float]:
    """Get embedding for a single query text (cached)."""
    return list(_cached_embed(text))
