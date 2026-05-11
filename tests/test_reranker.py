"""Tests for the parallel reranker (retrieval/reranker.py)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chunks(n: int = 5) -> list[tuple[str, dict, float]]:
    """Generate n sample chunks with decreasing scores."""
    return [
        (f"Document {i} content about topic.", {"display_text": f"Doc {i} text"}, 0.9 - i * 0.1)
        for i in range(n)
    ]


def _mock_settings(*, enabled: bool = True, top_k: int = 10, min_score: float = 0.3, model: str = "test-model"):
    """Create a mock settings object for reranker config."""
    mock = MagicMock()
    mock.reranker.enabled = enabled
    mock.reranker.top_k_candidates = top_k
    mock.reranker.min_score = min_score
    mock.reranker.model = model
    mock.ollama.base_url = "http://localhost:11434"
    return mock


# ---------------------------------------------------------------------------
# Disabled / empty
# ---------------------------------------------------------------------------

class TestRerankerDisabled:

    def test_disabled_returns_input_unchanged(self):
        from obsidian_rag.retrieval.reranker import rerank_chunks
        chunks = _make_chunks(3)
        with patch("obsidian_rag.retrieval.reranker.settings", _mock_settings(enabled=False)):
            result = rerank_chunks(chunks, "test query")
        assert result == chunks

    def test_empty_chunks_returns_empty(self):
        from obsidian_rag.retrieval.reranker import rerank_chunks
        result = rerank_chunks([], "test query")
        assert result == []


# ---------------------------------------------------------------------------
# Parallel scoring
# ---------------------------------------------------------------------------

class TestRerankerParallel:

    def test_all_chunks_scored(self):
        """Every candidate gets scored via _score_chunk."""
        from obsidian_rag.retrieval.reranker import rerank_chunks, _score_chunk
        _score_chunk.cache_clear()

        chunks = _make_chunks(4)
        with patch("obsidian_rag.retrieval.reranker.settings", _mock_settings(min_score=0.0)):
            with patch("obsidian_rag.retrieval.reranker._score_chunk", return_value=0.8) as mock_score:
                result = rerank_chunks(chunks, "my query")
        assert mock_score.call_count == 4
        assert len(result) == 4

    def test_results_sorted_by_combined_score(self):
        """Output should be sorted descending by combined score."""
        from obsidian_rag.retrieval.reranker import rerank_chunks, _score_chunk
        _score_chunk.cache_clear()

        chunks = _make_chunks(3)
        # Return different scores to test sorting
        scores = iter([0.3, 0.9, 0.6])
        with patch("obsidian_rag.retrieval.reranker.settings", _mock_settings(min_score=0.0)):
            with patch("obsidian_rag.retrieval.reranker._score_chunk", side_effect=lambda *a: next(scores)):
                result = rerank_chunks(chunks, "query")
        # Scores should be descending
        result_scores = [s for _, _, s in result]
        assert result_scores == sorted(result_scores, reverse=True)

    def test_chunks_below_min_score_filtered(self):
        """Chunks scoring below min_score are dropped."""
        from obsidian_rag.retrieval.reranker import rerank_chunks, _score_chunk
        _score_chunk.cache_clear()

        chunks = _make_chunks(3)
        # Score 0.2 → below min_score 0.5
        with patch("obsidian_rag.retrieval.reranker.settings", _mock_settings(min_score=0.5)):
            with patch("obsidian_rag.retrieval.reranker._score_chunk", return_value=0.2):
                result = rerank_chunks(chunks, "query")
        assert len(result) == 0

    def test_score_none_keeps_original(self):
        """If _score_chunk returns None, chunk keeps its original vec_score."""
        from obsidian_rag.retrieval.reranker import rerank_chunks, _score_chunk
        _score_chunk.cache_clear()

        chunks = _make_chunks(2)
        with patch("obsidian_rag.retrieval.reranker.settings", _mock_settings(min_score=0.0)):
            with patch("obsidian_rag.retrieval.reranker._score_chunk", return_value=None):
                result = rerank_chunks(chunks, "query")
        assert len(result) == 2
        # Original vec_scores preserved
        assert result[0][2] == chunks[0][2]
        assert result[1][2] == chunks[1][2]

    def test_top_k_candidates_respected(self):
        """Only top_k_candidates are evaluated."""
        from obsidian_rag.retrieval.reranker import rerank_chunks, _score_chunk
        _score_chunk.cache_clear()

        chunks = _make_chunks(10)
        with patch("obsidian_rag.retrieval.reranker.settings", _mock_settings(top_k=3, min_score=0.0)):
            with patch("obsidian_rag.retrieval.reranker._score_chunk", return_value=0.7) as mock_score:
                result = rerank_chunks(chunks, "query")
        assert mock_score.call_count == 3


# ---------------------------------------------------------------------------
# _score_chunk
# ---------------------------------------------------------------------------

class TestScoreChunk:

    def test_valid_response_parsed(self):
        from obsidian_rag.retrieval.reranker import _score_chunk
        _score_chunk.cache_clear()

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"response": "7"}

        with patch("obsidian_rag.retrieval.reranker.settings") as mock_settings:
            mock_settings.ollama.base_url = "http://localhost:11434"
            with patch("obsidian_rag.retrieval.reranker.httpx.post", return_value=mock_resp):
                score = _score_chunk("query", "chunk text", "model")
        assert score == 0.7

    def test_think_tags_stripped(self):
        from obsidian_rag.retrieval.reranker import _score_chunk
        _score_chunk.cache_clear()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "<think>reasoning</think>8"}

        with patch("obsidian_rag.retrieval.reranker.settings") as mock_settings:
            mock_settings.ollama.base_url = "http://localhost:11434"
            with patch("obsidian_rag.retrieval.reranker.httpx.post", return_value=mock_resp):
                score = _score_chunk("query", "text", "model")
        assert score == 0.8

    def test_http_error_returns_none(self):
        from obsidian_rag.retrieval.reranker import _score_chunk
        _score_chunk.cache_clear()

        with patch("obsidian_rag.retrieval.reranker.settings") as mock_settings:
            mock_settings.ollama.base_url = "http://localhost:11434"
            with patch("obsidian_rag.retrieval.reranker.httpx.post", side_effect=Exception("timeout")):
                score = _score_chunk("query", "text", "model")
        assert score is None

    def test_score_capped_at_10(self):
        from obsidian_rag.retrieval.reranker import _score_chunk
        _score_chunk.cache_clear()

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"response": "15"}

        with patch("obsidian_rag.retrieval.reranker.settings") as mock_settings:
            mock_settings.ollama.base_url = "http://localhost:11434"
            with patch("obsidian_rag.retrieval.reranker.httpx.post", return_value=mock_resp):
                score = _score_chunk("query", "text", "model")
        assert score == 1.0

    def test_lru_cache_active(self):
        from obsidian_rag.retrieval.reranker import _score_chunk
        assert hasattr(_score_chunk, "cache_info")
        assert hasattr(_score_chunk, "cache_clear")
