"""Qdrant implementation of the VectorStore protocol.

Supports two modes:

* **embedded** — ``qdrant-client`` in-process (no server needed).
  Data persisted to ``data_dir/qdrant``.
* **server** — connects to a Qdrant server at ``url`` (e.g. Docker).

Both use 1024-dimensional cosine distance to match bge-m3 embeddings.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
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
            self._qdrant_path: Path | None = None
        else:
            if data_dir is None:
                from obsidian_rag.config import settings
                data_dir = settings.paths.data_dir
            qdrant_path = Path(data_dir) / "qdrant"
            qdrant_path.mkdir(parents=True, exist_ok=True)
            _recover_meta_if_corrupt(qdrant_path)
            self._client = QdrantClient(path=str(qdrant_path))
            self._qdrant_path = qdrant_path
            _backup_meta(qdrant_path)
            log.info("Qdrant: embedded mode → %s", qdrant_path)

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
            response = self._client.query_points(
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
            )
        else:
            response = self._client.query_points(
                collection_name=collection,
                query=embedding,
                limit=n,
                with_payload=True,
                query_filter=query_filter,
            )
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
        info = self._client.get_collection(collection)
        return info.points_count or 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_META_FILENAME = "meta.json"
_META_BACKUP   = "meta.json.bak"


def _is_meta_valid(qdrant_path: Path) -> bool:
    """Return True if meta.json exists and contains valid JSON."""
    meta = qdrant_path / _META_FILENAME
    if not meta.exists() or meta.stat().st_size == 0:
        return False
    try:
        with meta.open() as f:
            json.load(f)
        return True
    except (json.JSONDecodeError, OSError):
        return False


def _backup_meta(qdrant_path: Path) -> None:
    """Copy meta.json → meta.json.bak using an atomic rename."""
    meta = qdrant_path / _META_FILENAME
    backup = qdrant_path / _META_BACKUP
    if not meta.exists() or meta.stat().st_size == 0:
        return
    try:
        fd, tmp = tempfile.mkstemp(dir=qdrant_path, prefix=".meta_bak_")
        try:
            os.close(fd)
            shutil.copy2(meta, tmp)
            os.replace(tmp, backup)          # atomic on POSIX
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception as exc:
        log.warning("Qdrant: não foi possível actualizar o backup do meta.json: %s", exc)


def _recover_meta_if_corrupt(qdrant_path: Path) -> None:
    """If meta.json is missing/empty/corrupt, restore from backup or seed empty."""
    if _is_meta_valid(qdrant_path):
        return

    meta   = qdrant_path / _META_FILENAME
    backup = qdrant_path / _META_BACKUP

    if backup.exists() and backup.stat().st_size > 0:
        try:
            with backup.open() as f:
                json.load(f)                 # validate backup before using it
            shutil.copy2(backup, meta)
            log.warning(
                "Qdrant: meta.json corrompido/vazio — restaurado de %s", backup
            )
            return
        except (json.JSONDecodeError, OSError) as exc:
            log.warning("Qdrant: backup também inválido (%s) — a criar meta.json vazio", exc)

    # Last resort: seed an empty-but-valid meta so QdrantLocal doesn't crash.
    # Collections will be re-created on first upsert via _ensure_collection().
    try:
        fd, tmp = tempfile.mkstemp(dir=qdrant_path, prefix=".meta_seed_")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump({"collections": {}, "aliases": {}}, f)
            os.replace(tmp, meta)
            log.warning(
                "Qdrant: meta.json corrompido/vazio e sem backup válido — "
                "reiniciado com colecções vazias. "
                "Os dados SQLite existentes serão re-indexados no próximo sync."
            )
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception as exc:
        log.error("Qdrant: não foi possível semear meta.json: %s", exc)


def _str_to_uint(s: str) -> int:
    """Deterministic string → unsigned 64-bit int for Qdrant point IDs.

    Qdrant requires numeric or UUID point IDs.  We hash the string ID
    to a stable uint64.
    """
    import hashlib
    h = hashlib.sha256(s.encode("utf-8")).digest()
    return int.from_bytes(h[:8], "big") & 0x7FFFFFFFFFFFFFFF
