"""Qdrant implementation of the VectorStore protocol.

Supports two modes:

* **embedded** — ``qdrant-client`` in-process (no server needed).
  Data persisted to ``data_dir/qdrant``.
* **server** — connects to a Qdrant server at ``url`` (e.g. Docker).

Both use 1024-dimensional cosine distance to match bge-m3 embeddings.
"""

from __future__ import annotations

import logging
from pathlib import Path

from obsidian_rag.store.base import QueryResult

log = logging.getLogger(__name__)

_VECTOR_DIM = 1024  # bge-m3


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


class QdrantVectorStore:
    """VectorStore backed by Qdrant (embedded or server mode).

    Args:
        url: Qdrant server URL (e.g. ``http://localhost:6333``).
             If *None*, uses embedded mode with ``data_dir``.
        data_dir: Directory for embedded Qdrant storage.
                  Ignored when ``url`` is set.
        api_key: Optional API key for Qdrant Cloud.
    """

    def __init__(
        self,
        *,
        url: str | None = None,
        data_dir: str | Path | None = None,
        api_key: str | None = None,
    ) -> None:
        QdrantClient, self._models = _import_qdrant()

        if url:
            self._client = QdrantClient(url=url, api_key=api_key)
            log.info("Qdrant: server mode → %s", url)
        else:
            if data_dir is None:
                from obsidian_rag.config import settings
                data_dir = settings.paths.data_dir
            qdrant_path = Path(data_dir) / "qdrant"
            qdrant_path.mkdir(parents=True, exist_ok=True)
            self._client = QdrantClient(path=str(qdrant_path))
            log.info("Qdrant: embedded mode → %s", qdrant_path)

        self._ensured: set[str] = set()

    # -- internal helpers --

    def _ensure_collection(self, name: str) -> None:
        """Create collection if it doesn't exist yet."""
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
            )
            log.info("Qdrant: created collection %r (%dd cosine)", name, _VECTOR_DIM)
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
    ) -> None:
        models = self._models
        self._ensure_collection(collection)

        points = [
            models.PointStruct(
                id=_str_to_uint(rid),
                vector=emb,
                payload={
                    "_id": rid,       # preserve original string ID
                    "_document": doc,
                    **meta,
                },
            )
            for rid, emb, doc, meta in zip(ids, embeddings, documents, metadatas)
        ]

        # Qdrant recommends batches ≤ 100
        for i in range(0, len(points), 100):
            self._client.upsert(
                collection_name=collection,
                points=points[i : i + 100],
            )

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
        self._client.delete(
            collection_name=collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    should=[
                        models.FieldCondition(
                            key="_id",
                            match=models.MatchValue(value=rid),
                        )
                        for rid in ids
                    ],
                ),
            ),
        )
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

            points, next_offset = self._client.scroll(**scroll_kwargs)
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
    ) -> list[QueryResult]:
        self._ensure_collection(collection)

        hits = self._client.search(
            collection_name=collection,
            query_vector=embedding,
            limit=n,
            with_payload=True,
        )
        results = []
        for hit in hits:
            payload = hit.payload or {}
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
        info = self._client.get_collection(collection)
        return info.points_count or 0


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
