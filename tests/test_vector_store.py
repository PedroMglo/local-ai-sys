"""Parametrized tests for the VectorStore protocol.

Tests run against QdrantVectorStore in embedded mode by default.
Set QDRANT_TEST_URL=http://localhost:6333 to run against a live server.
"""

from __future__ import annotations

import os

import pytest

from obsidian_rag.store.base import QueryResult, VectorStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_QDRANT_TEST_URL = os.environ.get("QDRANT_TEST_URL", "")


def _make_qdrant(tmp_path):
    try:
        from obsidian_rag.store.qdrant_store import QdrantVectorStore
    except ImportError:
        pytest.skip("qdrant-client not installed")
    try:
        if _QDRANT_TEST_URL:
            return QdrantVectorStore(url=_QDRANT_TEST_URL)
        return QdrantVectorStore(data_dir=tmp_path / "qdrant_data")
    except ImportError:
        pytest.skip("qdrant-client not installed")


@pytest.fixture
def store(tmp_path) -> VectorStore:
    return _make_qdrant(tmp_path)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DIM = 1024

def _vec(seed: float = 0.1) -> list[float]:
    """Create a deterministic 1024d vector."""
    import math
    return [math.sin(seed * (i + 1)) for i in range(_DIM)]


def _sample_batch(n: int = 5, prefix: str = "doc") -> tuple[list[str], list[list[float]], list[str], list[dict]]:
    """Generate a sample batch of n items."""
    ids = [f"{prefix}-{i}" for i in range(n)]
    embeddings = [_vec(0.1 * (i + 1)) for i in range(n)]
    documents = [f"Document {prefix} number {i} with some content for testing." for i in range(n)]
    metadatas = [{"source": prefix, "index": str(i)} for i in range(n)]
    return ids, embeddings, documents, metadatas


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------

class TestProtocolCompliance:

    def test_qdrant_implements_protocol(self, tmp_path):
        try:
            store = _make_qdrant(tmp_path)
        except pytest.skip.Exception:
            pytest.skip("qdrant-client not installed")
        assert isinstance(store, VectorStore)


# ---------------------------------------------------------------------------
# Core operations (parametrized across backends)
# ---------------------------------------------------------------------------

class TestUpsertAndCount:

    def test_empty_store_count_zero(self, store):
        assert store.count(collection="test_col") == 0

    def test_upsert_increases_count(self, store):
        ids, embs, docs, metas = _sample_batch(3, "upsert")
        store.upsert_batch(ids, embs, docs, metas, collection="test_col")
        assert store.count(collection="test_col") == 3

    def test_upsert_is_idempotent(self, store):
        ids, embs, docs, metas = _sample_batch(3, "idem")
        store.upsert_batch(ids, embs, docs, metas, collection="test_col")
        store.upsert_batch(ids, embs, docs, metas, collection="test_col")
        assert store.count(collection="test_col") == 3

    def test_upsert_empty_batch_is_noop(self, store):
        store.upsert_batch([], [], [], [], collection="test_col")
        assert store.count(collection="test_col") == 0


class TestGetExistingIds:

    def test_empty_returns_empty_set(self, store):
        assert store.get_existing_ids(collection="test_ids") == set()

    def test_returns_all_ids(self, store):
        ids, embs, docs, metas = _sample_batch(5, "ids")
        store.upsert_batch(ids, embs, docs, metas, collection="test_ids")
        existing = store.get_existing_ids(collection="test_ids")
        assert existing == set(ids)


class TestDeleteIds:

    def test_delete_reduces_count(self, store):
        ids, embs, docs, metas = _sample_batch(5, "del")
        store.upsert_batch(ids, embs, docs, metas, collection="test_del")
        deleted = store.delete_ids(ids[:2], collection="test_del")
        assert deleted == 2
        assert store.count(collection="test_del") == 3

    def test_delete_empty_list_returns_zero(self, store):
        assert store.delete_ids([], collection="test_del") == 0

    def test_deleted_ids_not_in_existing(self, store):
        ids, embs, docs, metas = _sample_batch(5, "delex")
        store.upsert_batch(ids, embs, docs, metas, collection="test_delex")
        store.delete_ids(ids[:2], collection="test_delex")
        remaining = store.get_existing_ids(collection="test_delex")
        assert remaining == set(ids[2:])


class TestQuery:

    def test_query_returns_results(self, store):
        ids, embs, docs, metas = _sample_batch(5, "query")
        store.upsert_batch(ids, embs, docs, metas, collection="test_query")
        results = store.query(_vec(0.1), n=3, collection="test_query")
        assert len(results) <= 3
        assert all(isinstance(r, QueryResult) for r in results)

    def test_query_results_have_required_fields(self, store):
        ids, embs, docs, metas = _sample_batch(3, "fields")
        store.upsert_batch(ids, embs, docs, metas, collection="test_fields")
        results = store.query(_vec(0.1), n=3, collection="test_fields")
        assert len(results) > 0
        r = results[0]
        assert isinstance(r.id, str)
        assert isinstance(r.document, str)
        assert isinstance(r.metadata, dict)
        assert isinstance(r.score, float)

    def test_query_empty_collection_returns_empty(self, store):
        results = store.query(_vec(0.1), n=5, collection="test_empty_q")
        assert results == []

    def test_nearest_neighbor_is_self(self, store):
        """Inserting a vector and querying with itself should return it first."""
        ids = ["self-0"]
        embs = [_vec(0.42)]
        docs = ["The target document for self-query test."]
        metas = [{"target": "true"}]
        store.upsert_batch(ids, embs, docs, metas, collection="test_self")

        # Add some noise
        noise_ids, noise_embs, noise_docs, noise_metas = _sample_batch(5, "noise")
        store.upsert_batch(noise_ids, noise_embs, noise_docs, noise_metas, collection="test_self")

        results = store.query(_vec(0.42), n=1, collection="test_self")
        assert len(results) >= 1
        assert results[0].id == "self-0"

    def test_query_with_filter_narrows_results(self, store):
        """filters= should restrict results to matching metadata."""
        ids = [f"filt-{i}" for i in range(4)]
        embs = [_vec(0.1 * (i + 1)) for i in range(4)]
        docs = [f"Doc {i}" for i in range(4)]
        metas = [
            {"repo_name": "alpha", "lang": "py"},
            {"repo_name": "beta", "lang": "py"},
            {"repo_name": "alpha", "lang": "rs"},
            {"repo_name": "beta", "lang": "rs"},
        ]
        store.upsert_batch(ids, embs, docs, metas, collection="test_filter")

        results = store.query(_vec(0.1), n=10, collection="test_filter", filters={"repo_name": "alpha"})
        assert all(r.metadata.get("repo_name") == "alpha" for r in results)
        assert len(results) == 2

    def test_query_filters_none_returns_all(self, store):
        """filters=None should return all results (no restriction)."""
        ids, embs, docs, metas = _sample_batch(3, "nofilt")
        store.upsert_batch(ids, embs, docs, metas, collection="test_nofilt")
        results = store.query(_vec(0.1), n=10, collection="test_nofilt", filters=None)
        assert len(results) == 3


class TestCollectionIsolation:

    def test_different_collections_are_isolated(self, store):
        ids_a, embs_a, docs_a, metas_a = _sample_batch(3, "col_a")
        ids_b, embs_b, docs_b, metas_b = _sample_batch(4, "col_b")

        store.upsert_batch(ids_a, embs_a, docs_a, metas_a, collection="alpha")
        store.upsert_batch(ids_b, embs_b, docs_b, metas_b, collection="beta")

        assert store.count(collection="alpha") == 3
        assert store.count(collection="beta") == 4

        assert store.get_existing_ids(collection="alpha") == set(ids_a)
        assert store.get_existing_ids(collection="beta") == set(ids_b)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class TestFactory:

    def test_create_store_qdrant(self, tmp_path):
        """create_store(backend='qdrant') returns QdrantVectorStore."""
        pytest.importorskip("qdrant_client", reason="qdrant-client not installed")
        from obsidian_rag.store.base import create_store
        from obsidian_rag.store.qdrant_store import QdrantVectorStore

        store = create_store(backend="qdrant", data_dir=tmp_path / "factory_qdrant")
        assert isinstance(store, QdrantVectorStore)

    def test_create_store_unknown_raises(self):
        from obsidian_rag.store.base import create_store
        with pytest.raises(ValueError, match="Unknown vector store"):
            create_store(backend="nonexistent")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class TestHealth:

    def test_health_returns_true(self, store):
        """health() returns True when the backend is reachable."""
        assert store.health() is True


# ---------------------------------------------------------------------------
# Hybrid search (dense + BM25 sparse)
# ---------------------------------------------------------------------------

class TestHybridSearch:

    def test_upsert_with_sparse_vectors(self, store):
        """upsert_batch accepts sparse_vectors without error."""
        ids, embs, docs, metas = _sample_batch(3, "sparse")
        sparse = [
            {"indices": [0, 5, 10], "values": [1.2, 0.8, 0.5]},
            {"indices": [1, 5], "values": [1.0, 0.6]},
            {"indices": [0, 3, 10], "values": [0.9, 1.1, 0.3]},
        ]
        store.upsert_batch(ids, embs, docs, metas, collection="test_sparse", sparse_vectors=sparse)
        assert store.count(collection="test_sparse") == 3

    def test_upsert_sparse_none_works(self, store):
        """sparse_vectors=None falls back to dense-only (backward compat)."""
        ids, embs, docs, metas = _sample_batch(2, "nosparse")
        store.upsert_batch(ids, embs, docs, metas, collection="test_nosparse", sparse_vectors=None)
        assert store.count(collection="test_nosparse") == 2

    def test_query_with_sparse_returns_results(self, store):
        """Hybrid query (dense + sparse) returns results."""
        ids, embs, docs, metas = _sample_batch(5, "hybrid")
        sparse = [
            {"indices": [0, 1], "values": [1.0, 0.5]},
            {"indices": [1, 2], "values": [0.8, 1.2]},
            {"indices": [0, 2], "values": [0.6, 0.9]},
            {"indices": [0], "values": [1.5]},
            {"indices": [1], "values": [0.7]},
        ]
        store.upsert_batch(ids, embs, docs, metas, collection="test_hybrid", sparse_vectors=sparse)
        results = store.query(
            _vec(0.1),
            n=3,
            collection="test_hybrid",
            sparse_query={"indices": [0, 1], "values": [1.0, 0.5]},
        )
        assert len(results) > 0
        assert all(isinstance(r, QueryResult) for r in results)

    def test_query_sparse_none_dense_only(self, store):
        """sparse_query=None falls back to dense-only query."""
        ids, embs, docs, metas = _sample_batch(3, "denseonly")
        store.upsert_batch(ids, embs, docs, metas, collection="test_denseonly")
        results = store.query(_vec(0.1), n=3, collection="test_denseonly", sparse_query=None)
        assert len(results) > 0

    def test_query_sparse_empty_dense_only(self, store):
        """sparse_query with empty indices falls back to dense-only."""
        ids, embs, docs, metas = _sample_batch(3, "emptysp")
        store.upsert_batch(ids, embs, docs, metas, collection="test_emptysp")
        results = store.query(
            _vec(0.1), n=3, collection="test_emptysp",
            sparse_query={"indices": [], "values": []},
        )
        assert len(results) > 0
