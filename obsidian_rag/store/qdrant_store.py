"""Qdrant implementation of the VectorStore protocol.

Connects to a Qdrant server at ``url`` (e.g. Docker container).
Uses 1024-dimensional cosine distance to match bge-m3 embeddings.
"""

from __future__ import annotations

import logging
import time

from obsidian_rag.store.base import QueryResult

log = logging.getLogger(__name__)

_VECTOR_DIM = 1024  # bge-m3
_MAX_RETRIES = 3
_RETRY_BACKOFF = 0.5  # seconds — doubles each retry


def _import_qdrant():
    """Lazy import — qdrant-client is an optional dependency."""
    try:
        from qdrant_client import QdrantClient, models
        return QdrantClient, models
    except ImportError:
        raise ImportError(
            "qdrant-client is required for the Qdrant backend.  "
            "Install it with:  pip install 'qdrant-client>=1.9'"
        ) from None


def _retry(fn, *, max_retries: int = _MAX_RETRIES, backoff: float = _RETRY_BACKOFF):
    """Execute *fn* with exponential-backoff retry on transient errors.

    Only retries connection/timeout errors — not logic errors.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            exc_name = type(exc).__name__
            # Only retry on transient network / timeout errors
            is_transient = any(kw in exc_name.lower() for kw in (
                "connection", "timeout", "unavailable", "transport",
            )) or any(kw in str(exc).lower() for kw in (
                "connection", "timed out", "unavailable", "refused",
            ))
            if not is_transient or attempt == max_retries:
                raise
            last_exc = exc
            wait = backoff * (2 ** attempt)
            log.warning("Qdrant: %s (attempt %d/%d) — retry in %.1fs",
                        exc, attempt + 1, max_retries, wait)
            time.sleep(wait)
    raise last_exc  # type: ignore[misc]  # unreachable but keeps mypy happy


class QdrantVectorStore:
    """VectorStore backed by a Qdrant server.

    Args:
        url: Qdrant server URL (e.g. ``http://localhost:6333``). Required.
        api_key: Optional API key for Qdrant Cloud.
    """

    def __init__(
        self,
        *,
        url: str,
        api_key: str | None = None,
    ) -> None:
        if not url:
            raise ValueError(
                "QdrantVectorStore requires a server URL. "
                "Start the Qdrant container with 'make qdrant' and set "
                "qdrant_url in rag.toml."
            )
        QdrantClient, self._models = _import_qdrant()
        self._client = QdrantClient(url=url, api_key=api_key)
        log.info("Qdrant: server mode → %s", url)

        self._ensured: set[str] = set()

    # -- internal helpers --

    def _ensure_collection(self, name: str) -> None:
        """Create collection if it doesn't exist yet (dense + sparse)."""
        if name in self._ensured:
            return

        models = self._models
        collections = [c.name for c in self._client.get_collections().collections]
        if name not in collections:
            self._client.create_collection(
                collection_name=name,
                vectors_config=models.VectorParams(
                    size=_VECTOR_DIM,
                    distance=models.Distance.COSINE,
                ),
                sparse_vectors_config={
                    "bm25": models.SparseVectorParams(),
                },
            )
            log.info("Qdrant: created collection %r (%dd cosine + bm25 sparse)", name, _VECTOR_DIM)
        else:
            # Existing collection — ensure sparse index exists
            try:
                info = self._client.get_collection(name)
                has_sparse = (
                    info.config
                    and info.config.params
                    and getattr(info.config.params, "sparse_vectors", None)
                    and "bm25" in info.config.params.sparse_vectors
                )
                if not has_sparse:
                    self._client.update_collection(
                        collection_name=name,
                        sparse_vectors_config={
                            "bm25": models.SparseVectorParams(),
                        },
                    )
                    log.info("Qdrant: added bm25 sparse index to %r", name)
            except Exception as exc:
                log.debug("Qdrant: could not check/add sparse index to %r: %s", name, exc)
        self._ensured.add(name)

    # -- VectorStore protocol --

    def upsert_batch(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
        *,
        collection: str = "obsidian_vault",
        sparse_vectors: list[dict] | None = None,
    ) -> None:
        models = self._models
        self._ensure_collection(collection)

        points = []
        for i, (rid, emb, doc, meta) in enumerate(zip(ids, embeddings, documents, metadatas)):
            vector: dict | list = emb
            if sparse_vectors and i < len(sparse_vectors):
                sv = sparse_vectors[i]
                if sv.get("indices"):
                    vector = {
                        "": emb,  # default (dense) vector
                        "bm25": models.SparseVector(
                            indices=sv["indices"],
                            values=sv["values"],
                        ),
                    }
            points.append(
                models.PointStruct(
                    id=_str_to_uint(rid),
                    vector=vector,
                    payload={
                        "_id": rid,
                        "_document": doc,
                        **meta,
                    },
                )
            )

        # Qdrant recommends batches ≤ 100
        for i in range(0, len(points), 100):
            batch = points[i : i + 100]
            _retry(lambda b=batch: self._client.upsert(
                collection_name=collection,
                points=b,
            ))

    def delete_ids(
        self,
        ids: list[str],
        *,
        collection: str = "obsidian_vault",
    ) -> int:
        if not ids:
            return 0
        models = self._models
        self._ensure_collection(collection)

        # Delete by matching the stored _id field
        selector = models.FilterSelector(
            filter=models.Filter(
                should=[
                    models.FieldCondition(
                        key="_id",
                        match=models.MatchValue(value=rid),
                    )
                    for rid in ids
                ],
            ),
        )
        _retry(lambda: self._client.delete(
            collection_name=collection,
            points_selector=selector,
        ))
        return len(ids)

    def get_existing_ids(
        self,
        *,
        collection: str = "obsidian_vault",
    ) -> set[str]:
        self._ensure_collection(collection)
        result: set[str] = set()
        offset = None

        while True:
            scroll_kwargs: dict = {
                "collection_name": collection,
                "limit": 1000,
                "with_payload": ["_id"],
                "with_vectors": False,
            }
            if offset is not None:
                scroll_kwargs["offset"] = offset

            points, next_offset = _retry(lambda kw=dict(scroll_kwargs): self._client.scroll(**kw))
            for p in points:
                _id = p.payload.get("_id") if p.payload else None
                if _id:
                    result.add(_id)

            if next_offset is None:
                break
            offset = next_offset

        return result

    def query(
        self,
        embedding: list[float],
        n: int = 10,
        *,
        collection: str = "obsidian_vault",
        filters: dict | None = None,
        sparse_query: dict | None = None,
    ) -> list[QueryResult]:
        self._ensure_collection(collection)

        models = self._models
        query_filter = None
        if filters:
            conditions = [
                models.FieldCondition(key=k, match=models.MatchValue(value=v))
                for k, v in filters.items()
            ]
            query_filter = models.Filter(must=conditions)

        # Hybrid search: dense prefetch + sparse, fused with RRF
        if sparse_query and sparse_query.get("indices"):
            response = _retry(lambda: self._client.query_points(
                collection_name=collection,
                prefetch=[
                    models.Prefetch(
                        query=embedding,
                        using="",  # default dense vector
                        limit=n * 2,
                        filter=query_filter,
                    ),
                    models.Prefetch(
                        query=models.SparseVector(
                            indices=sparse_query["indices"],
                            values=sparse_query["values"],
                        ),
                        using="bm25",
                        limit=n * 2,
                        filter=query_filter,
                    ),
                ],
                query=models.FusionQuery(fusion=models.Fusion.RRF),
                limit=n,
                with_payload=True,
            ))
        else:
            response = _retry(lambda: self._client.query_points(
                collection_name=collection,
                query=embedding,
                limit=n,
                with_payload=True,
                query_filter=query_filter,
            ))
        results = []
        for hit in response.points:
            payload = dict(hit.payload) if hit.payload else {}
            rid = payload.pop("_id", str(hit.id))
            doc = payload.pop("_document", "")
            results.append(QueryResult(
                id=rid,
                document=doc,
                metadata=payload,
                score=hit.score,
            ))
        return results

    def count(self, *, collection: str = "obsidian_vault") -> int:
        self._ensure_collection(collection)
        info = _retry(lambda: self._client.get_collection(collection))
        return info.points_count or 0

    def health(self) -> bool:
        """Return *True* if Qdrant backend is reachable."""
        try:
            self._client.get_collections()
            return True
        except Exception:
            return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _str_to_uint(s: str) -> int:
    """Deterministic string → unsigned 64-bit int for Qdrant point IDs.

    Qdrant requires numeric or UUID point IDs.  We hash the string ID
    to a stable uint64.
    """
    import hashlib
    h = hashlib.sha256(s.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") & 0x7FFFFFFFFFFFFFFF
