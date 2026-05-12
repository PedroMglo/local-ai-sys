"""Integration tests — API endpoints with QdrantVectorStore in-memory.

Tests the actual /query, /query/code, /stats endpoints using
a real Qdrant in-memory instance, bypassing Ollama by mocking
embeddings.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EMBED_DIM = 1024  # bge-m3 dimension


def _fake_embedding(seed: int = 0) -> list[float]:
    """Deterministic fake embedding vector."""
    import hashlib
    h = hashlib.sha256(str(seed).encode()).digest()
    vec = [((b % 200) - 100) / 100.0 for b in h]
    # Pad to _EMBED_DIM
    return (vec * (_EMBED_DIM // len(vec) + 1))[:_EMBED_DIM]


def _make_qdrant_store(tmp_path):
    """Create a QdrantVectorStore backed by an in-memory Qdrant client.

    Bypasses QdrantVectorStore.__init__ (which requires a server URL) and
    injects a QdrantClient(":memory:") directly — no server required.
    """
    from obsidian_rag.store.qdrant_store import QdrantVectorStore
    from qdrant_client import QdrantClient, models as qdrant_models

    store = object.__new__(QdrantVectorStore)
    store._client = QdrantClient(":memory:")
    store._models = qdrant_models
    store._ensured = set()
    return store


def _populate_store(store, collection: str, docs: list[dict]):
    """Populate a QdrantVectorStore collection with test docs."""
    if docs:
        store.upsert_batch(
            ids=[d["id"] for d in docs],
            embeddings=[d["embedding"] for d in docs],
            documents=[d["text"] for d in docs],
            metadatas=[d.get("metadata", {}) for d in docs],
            collection=collection,
        )


@pytest.fixture()
def integration_client(tmp_path):
    """TestClient with QdrantVectorStore in-memory collections injected."""
    store = _make_qdrant_store(tmp_path)

    notes_docs = [
        {
            "id": "note-1",
            "text": "Como configurar aliases no zsh para terminal Linux",
            "embedding": _fake_embedding(1),
            "metadata": {
                "source_path": "notes/linux-tips.md",
                "note_title": "Linux Tips",
                "section_header": "Aliases",
                "source_type": "markdown",
                "display_text": "Como configurar aliases no zsh para terminal Linux",
            },
        },
        {
            "id": "note-2",
            "text": "Obsidian vault sync with git and automation scripts",
            "embedding": _fake_embedding(2),
            "metadata": {
                "source_path": "notes/obsidian-setup.md",
                "note_title": "Obsidian Setup",
                "section_header": "Sync",
                "source_type": "markdown",
                "display_text": "Obsidian vault sync with git and automation scripts",
            },
        },
    ]

    code_docs = [
        {
            "id": "code-1",
            "text": "def sync_repos():\n    '''Sync all configured repos.'''",
            "embedding": _fake_embedding(10),
            "metadata": {
                "source_path": "obsidian_rag/pipeline/sync.py",
                "note_title": "sync.py",
                "section_header": "sync_repos",
                "source_type": "python",
                "repo_name": "obsidian-rag",
                "symbol_type": "function",
                "display_text": "def sync_repos():\n    '''Sync all configured repos.'''",
            },
        },
        {
            "id": "code-2",
            "text": "class SparkJob:\n    '''Apache Spark job wrapper.'''",
            "embedding": _fake_embedding(11),
            "metadata": {
                "source_path": "src/spark_job.py",
                "note_title": "spark_job.py",
                "section_header": "SparkJob",
                "source_type": "python",
                "repo_name": "ApacheSpark-CD",
                "symbol_type": "class",
                "display_text": "class SparkJob:\n    '''Apache Spark job wrapper.'''",
            },
        },
    ]

    _populate_store(store, "obsidian_vault", notes_docs)
    _populate_store(store, "code_repos", code_docs)

    fake_query_embed = _fake_embedding(1)  # will match note-1 closely

    with (
        patch("obsidian_rag.api.app._get_store", return_value=store),
        patch("obsidian_rag.api.app.get_query_embedding", return_value=fake_query_embed),
        patch("obsidian_rag.api.app.settings") as mock_settings,
    ):
        mock_settings.api.api_key = ""
        mock_settings.api.rate_limit = 0
        mock_settings.api.chat_rate_limit = 0
        mock_settings.api.query_top_k = 10
        mock_settings.repos.paths = ["/fake/repo"]
        mock_settings.repos.collection_name = "code_repos"
        mock_settings.paths.data_dir = str(tmp_path / "qdrant_test")
        mock_settings.store.backend = "qdrant"

        from obsidian_rag.api.app import app
        yield TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStatsEndpoint:
    def test_returns_chunk_counts(self, integration_client):
        resp = integration_client.get("/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_chunks"] == 2
        assert data["code_chunks"] == 2
        assert data["collection_name"] == "obsidian_vault"

    def test_stats_has_code_collection_name(self, integration_client):
        resp = integration_client.get("/stats")
        data = resp.json()
        assert data["code_collection_name"] == "code_repos"


class TestQueryEndpoint:
    def test_query_returns_results(self, integration_client):
        resp = integration_client.post("/query", json={"query": "aliases zsh"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "aliases zsh"
        assert len(data["results"]) > 0
        assert data["elapsed_ms"] >= 0

    def test_query_result_has_fields(self, integration_client):
        resp = integration_client.post("/query", json={"query": "aliases zsh"})
        results = resp.json()["results"]
        first = results[0]
        assert "text" in first
        assert "score" in first
        assert "source_path" in first
        assert "note_title" in first
        assert "section_header" in first
        assert "source_type" in first

    def test_query_with_top_k(self, integration_client):
        resp = integration_client.post("/query", json={"query": "test", "top_k": 1})
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) <= 1

    def test_query_with_min_score(self, integration_client):
        resp = integration_client.post("/query", json={"query": "test", "min_score": 0.99})
        assert resp.status_code == 200
        # High min_score should filter most results
        results = resp.json()["results"]
        for r in results:
            assert r["score"] >= 0.99

    def test_empty_query_400(self, integration_client):
        resp = integration_client.post("/query", json={"query": ""})
        assert resp.status_code == 422  # Pydantic min_length=1

    def test_query_too_long_422(self, integration_client):
        resp = integration_client.post("/query", json={"query": "x" * 10001})
        assert resp.status_code == 422  # max_length=10000


class TestCodeQueryEndpoint:
    def test_code_query_returns_results(self, integration_client):
        resp = integration_client.post("/query/code", json={"query": "sync repos"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["results"]) > 0

    def test_code_result_has_repo_name(self, integration_client):
        resp = integration_client.post("/query/code", json={"query": "sync repos"})
        results = resp.json()["results"]
        for r in results:
            assert r["repo_name"] is not None

    def test_filter_by_repo(self, integration_client):
        resp = integration_client.post(
            "/query/code",
            json={"query": "spark", "repo": "ApacheSpark-CD"},
        )
        assert resp.status_code == 200
        for r in resp.json()["results"]:
            assert r["repo_name"] == "ApacheSpark-CD"

    def test_filter_by_symbol_type(self, integration_client):
        resp = integration_client.post(
            "/query/code",
            json={"query": "class", "symbol_type": "class"},
        )
        assert resp.status_code == 200
        for r in resp.json()["results"]:
            assert r["symbol_type"] == "class"

    def test_empty_code_query_422(self, integration_client):
        resp = integration_client.post("/query/code", json={"query": ""})
        assert resp.status_code == 422


class TestInputValidation:
    """Test Pydantic input validation (§5.3 / §10.7)."""

    def test_query_max_length(self, integration_client):
        resp = integration_client.post("/query", json={"query": "a" * 10001})
        assert resp.status_code == 422

    def test_top_k_bounds(self, integration_client):
        resp = integration_client.post("/query", json={"query": "test", "top_k": 0})
        assert resp.status_code == 422
        resp = integration_client.post("/query", json={"query": "test", "top_k": 51})
        assert resp.status_code == 422

    def test_min_score_bounds(self, integration_client):
        resp = integration_client.post("/query", json={"query": "test", "min_score": -0.1})
        assert resp.status_code == 422
        resp = integration_client.post("/query", json={"query": "test", "min_score": 1.1})
        assert resp.status_code == 422
