"""VectorStore protocol — backend-agnostic interface for vector storage.

Every vector store backend (Chroma, Qdrant, …) implements ``VectorStore``
so that the rest of the codebase never imports a concrete backend directly.

Usage::

    from obsidian_rag.store.base import VectorStore, create_store

    store: VectorStore = create_store()          # reads [store] from config
    store.upsert_batch(ids, embeddings, docs, metas)
    results = store.query(embedding, n=10)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Query result
# ---------------------------------------------------------------------------

@dataclass
class QueryResult:
    """A single result from a vector query."""
    id: str
    document: str
    metadata: dict
    score: float          # similarity score (higher = more similar)


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class VectorStore(Protocol):
    """Backend-agnostic vector store interface.

    Implementations must support two collections: ``obsidian_vault`` (notes)
    and ``code_repos`` (code).  The ``collection`` parameter selects which.
    """

    def upsert_batch(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
        *,
        collection: str = "obsidian_vault",
    ) -> None:
        """Insert or update a batch of vectors."""
        ...

    def delete_ids(
        self,
        ids: list[str],
        *,
        collection: str = "obsidian_vault",
    ) -> int:
        """Delete vectors by ID.  Returns count deleted."""
        ...

    def get_existing_ids(
        self,
        *,
        collection: str = "obsidian_vault",
    ) -> set[str]:
        """Return all IDs currently stored in the collection."""
        ...

    def query(
        self,
        embedding: list[float],
        n: int = 10,
        *,
        collection: str = "obsidian_vault",
    ) -> list[QueryResult]:
        """Return the *n* nearest neighbours for *embedding*."""
        ...

    def count(self, *, collection: str = "obsidian_vault") -> int:
        """Return the number of vectors in the collection."""
        ...


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def create_store(backend: str | None = None, **kwargs) -> VectorStore:
    """Instantiate the configured vector store backend.

    Args:
        backend: ``"chroma"`` or ``"qdrant"``.  If *None*, reads from
                 ``settings.store.backend``.
        **kwargs: forwarded to the backend constructor.
    """
    if backend is None:
        from obsidian_rag.config import settings
        backend = settings.store.backend

    backend = backend.lower().strip()

    if backend == "chroma":
        from obsidian_rag.store.chroma_store import ChromaVectorStore
        return ChromaVectorStore(**kwargs)

    if backend == "qdrant":
        from obsidian_rag.store.qdrant_store import QdrantVectorStore
        return QdrantVectorStore(**kwargs)

    raise ValueError(f"Unknown vector store backend: {backend!r}  (expected 'chroma' or 'qdrant')")
