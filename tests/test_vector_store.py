"""Parametrized tests for the VectorStore protocol.

Tests run against ChromaVectorStore (always) and QdrantVectorStore
(only when qdrant-client is installed).
"""

from __future__ import annotations

import pytest

from obsidian_rag.store.base import QueryResult, VectorStore
from obsidian_rag.store.chroma_store import ChromaVectorStore


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_chroma(tmp_path):
    return ChromaVectorStore(data_dir=tmp_path / "chroma")


def _make_qdrant(tmp_path):
    try:
        from obsidian_rag.store.qdrant_store import QdrantVectorStore
    except ImportError:
        pytest.skip("qdrant-client not installed")
    try:
        return QdrantVectorStore(data_dir=tmp_path / "qdrant_data")
    except ImportError:
        pytest.skip("qdrant-client not installed")


@pytest.fixture(params=["chroma", "qdrant"], ids=["chroma", "qdrant"])
def store(request, tmp_path) -> VectorStore:
    if request.param == "chroma":
        return _make_chroma(tmp_path)
    return _make_qdrant(tmp_path)


@pytest.fixture
def chroma_store(tmp_path) -> ChromaVectorStore:
    return _make_chroma(tmp_path)


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

    def test_chroma_implements_protocol(self, tmp_path):
        store = _make_chroma(tmp_path)
        assert isinstance(store, VectorStore)

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
# ChromaVectorStore-specific (non-parametrized)
# ---------------------------------------------------------------------------

class TestChromaSpecific:

    def test_create_with_data_dir(self, tmp_path):
        store = ChromaVectorStore(data_dir=tmp_path / "specific_chroma")
        assert store.count(collection="test") == 0

    def test_score_is_cosine_similarity(self, chroma_store):
        """ChromaDB cosine distance is converted to similarity (1 - dist)."""
        ids = ["cos-0"]
        embs = [_vec(0.5)]
        docs = ["cosine test"]
        metas = [{"type": "test"}]
        chroma_store.upsert_batch(ids, embs, docs, metas, collection="test_cos")

        results = chroma_store.query(_vec(0.5), n=1, collection="test_cos")
        assert len(results) == 1
        # Self-query should have score very close to 1.0
        assert results[0].score > 0.99


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class TestFactory:

    def test_create_store_chroma(self, tmp_path, monkeypatch):
        """create_store(backend='chroma') returns ChromaVectorStore."""
        # Monkeypatch settings to avoid needing rag.toml
        import obsidian_rag.store.base as base_mod
        from obsidian_rag.store.base import create_store

        store = create_store(backend="chroma", data_dir=tmp_path / "factory_chroma")
        assert isinstance(store, ChromaVectorStore)

    def test_create_store_unknown_raises(self):
        from obsidian_rag.store.base import create_store
        with pytest.raises(ValueError, match="Unknown vector store"):
            create_store(backend="nonexistent")
