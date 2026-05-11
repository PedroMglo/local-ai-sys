"""ChromaDB implementation of the VectorStore protocol."""

from __future__ import annotations

import logging
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings

from obsidian_rag.store.base import QueryResult

log = logging.getLogger(__name__)


class ChromaVectorStore:
    """VectorStore backed by ChromaDB PersistentClient.

    Wraps the existing ChromaDB logic behind the ``VectorStore`` protocol
    so that the rest of the codebase can be backend-agnostic.
    """

    def __init__(
        self,
        *,
        data_dir: str | Path | None = None,
        client: chromadb.ClientAPI | None = None,
    ) -> None:
        if client is not None:
            self._client = client
        else:
            if data_dir is None:
                from obsidian_rag.config import settings
                data_dir = settings.paths.data_dir
            data_dir = Path(data_dir)
            data_dir.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(data_dir),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
        self._collections: dict[str, chromadb.Collection] = {}

    # -- internal helpers --

    def _col(self, name: str) -> chromadb.Collection:
        if name not in self._collections:
            self._collections[name] = self._client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._collections[name]

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
        if not ids:
            return
        col = self._col(collection)
        col.upsert(
            ids=ids,
            embeddings=embeddings,  # type: ignore[arg-type]
            documents=documents,
            metadatas=metadatas,  # type: ignore[arg-type]
        )

    def delete_ids(
        self,
        ids: list[str],
        *,
        collection: str = "obsidian_vault",
    ) -> int:
        if not ids:
            return 0
        col = self._col(collection)
        for i in range(0, len(ids), 500):
            col.delete(ids=ids[i : i + 500])
        return len(ids)

    def get_existing_ids(
        self,
        *,
        collection: str = "obsidian_vault",
    ) -> set[str]:
        col = self._col(collection)
        result = col.get(include=[])
        return set(result["ids"]) if result["ids"] else set()

    def query(
        self,
        embedding: list[float],
        n: int = 10,
        *,
        collection: str = "obsidian_vault",
        filters: dict | None = None,
    ) -> list[QueryResult]:
        col = self._col(collection)

        where = None
        if filters:
            if len(filters) == 1:
                k, v = next(iter(filters.items()))
                where = {k: {"$eq": v}}
            else:
                where = {"$and": [{k: {"$eq": v}} for k, v in filters.items()]}

        results = col.query(
            query_embeddings=[embedding],  # type: ignore[arg-type]
            n_results=n,
            include=["documents", "metadatas", "distances"],
            where=where,
        )
        if not results["ids"] or not results["ids"][0]:
            return []
        assert results["documents"] is not None
        assert results["metadatas"] is not None
        assert results["distances"] is not None
        return [
            QueryResult(
                id=rid,
                document=doc,
                metadata=dict(meta),
                score=1.0 - dist,  # cosine distance → similarity
            )
            for rid, doc, meta, dist in zip(
                results["ids"][0],
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
            )
        ]

    def count(self, *, collection: str = "obsidian_vault") -> int:
        return self._col(collection).count()
