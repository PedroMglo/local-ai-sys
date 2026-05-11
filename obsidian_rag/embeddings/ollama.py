"""Geração de embeddings via Ollama API."""

import logging
import time
from functools import lru_cache

import httpx

from obsidian_rag.config import settings

log = logging.getLogger(__name__)

_MAX_RETRIES = 2
_RETRY_BACKOFF = (1.0, 3.0)  # seconds between retries


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Gera embeddings via Ollama API (batch) com retry para erros transientes."""
    last_exc: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = httpx.post(
                f"{settings.ollama.base_url}/api/embed",
                json={"model": settings.ollama.embedding_model, "input": texts},
                timeout=float(settings.performance.embedding_timeout),
            )
            response.raise_for_status()
            result: list[list[float]] = response.json()["embeddings"]
            return result
        except (httpx.HTTPStatusError, httpx.TimeoutException, httpx.ConnectError) as exc:
            last_exc = exc
            if attempt < _MAX_RETRIES:
                wait = _RETRY_BACKOFF[min(attempt, len(_RETRY_BACKOFF) - 1)]
                log.warning(
                    "Embedding retry %d/%d após erro: %s — aguardando %.0fs",
                    attempt + 1, _MAX_RETRIES, exc, wait,
                )
                time.sleep(wait)
            else:
                log.error("Embedding falhou após %d tentativas: %s", _MAX_RETRIES + 1, exc)
    raise last_exc  # type: ignore[misc]


# LRU cache for single-query embeddings (avoids repeated Ollama calls)
@lru_cache(maxsize=settings.retrieval.embedding_cache_size)
def _cached_embed(text: str) -> tuple[float, ...]:
    """Cache embedding vectors for repeated queries."""
    return tuple(embed_texts([text])[0])


def get_query_embedding(text: str) -> list[float]:
    """Get embedding for a single query text (cached)."""
    return list(_cached_embed(text))


def clear_embed_cache() -> None:
    """Invalidate the embedding LRU cache."""
    _cached_embed.cache_clear()
