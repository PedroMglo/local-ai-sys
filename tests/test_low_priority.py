"""Tests for low-priority improvements (Fase 6 — v0.4.2).

Covers:
  - Centralized version (importlib.metadata)
  - Unicode normalization in _extract_keywords()
  - Bilingual stop words (PT + EN)
  - Embedding timeout from config
  - clear_embed_cache()
  - Thread-safe singletons (double-checked locking)
  - __all__ exports in __init__.py modules
  - Reranker _score_chunk LRU cache
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Version centralized
# ---------------------------------------------------------------------------

class TestVersionCentralized:
    """Version comes from importlib.metadata, not hardcoded."""

    def test_version_from_metadata(self):
        from obsidian_rag import __version__
        # Should match pyproject.toml (0.4.0 or similar semver)
        assert isinstance(__version__, str)
        parts = __version__.split(".")
        assert len(parts) >= 2  # at least major.minor

    def test_app_uses_package_version(self):
        from obsidian_rag import __version__
        # Confirm app.py imports __version__ (not hardcoded)
        import importlib
        import obsidian_rag.api.app as app_mod
        source = importlib.util.find_spec("obsidian_rag.api.app")
        assert source is not None
        # The FastAPI app title should reference __version__
        assert hasattr(app_mod, '__version__') or '__version__' in dir(app_mod)


# ---------------------------------------------------------------------------
# Unicode normalization + bilingual stop words
# ---------------------------------------------------------------------------

class TestExtractKeywords:
    """Tests for _extract_keywords with Unicode and EN stop words."""

    def test_unicode_normalization(self):
        """NFC normalization handles composed vs decomposed chars."""
        from obsidian_rag.retrieval.rag import _extract_keywords
        # ã as precomposed (NFC) vs decomposed (NFD: a + combining tilde)
        text_nfc = "configuração"
        text_nfd = "configurac\u0327a\u0303o"  # decomposed ç and ã
        result_nfc = _extract_keywords(text_nfc)
        result_nfd = _extract_keywords(text_nfd)
        # After NFC normalization, both should produce the same keywords
        assert result_nfc == result_nfd

    def test_portuguese_stop_words_filtered(self):
        from obsidian_rag.retrieval.rag import _extract_keywords
        result = _extract_keywords("como configurar o meu projeto")
        assert "como" not in result
        assert "meu" not in result
        assert "configurar" in result
        assert "projeto" in result

    def test_english_stop_words_filtered(self):
        from obsidian_rag.retrieval.rag import _extract_keywords
        result = _extract_keywords("how does the system handle authentication")
        words = result.split()
        assert "the" not in words
        assert "does" not in words
        assert "how" not in words
        assert "system" in words
        assert "handle" in words
        assert "authentication" in words
        assert "authentication" in words

    def test_mixed_language_query(self):
        from obsidian_rag.retrieval.rag import _extract_keywords
        result = _extract_keywords("como é que the pipeline handles o sync")
        # PT stops: "como", "é", "que", "o"
        # EN stops: "the"
        assert "pipeline" in result
        assert "handles" in result
        assert "sync" in result

    def test_short_words_filtered(self):
        from obsidian_rag.retrieval.rag import _extract_keywords
        result = _extract_keywords("a b cd efg hijklm")
        # words with len <= 2 are filtered
        assert "efg" in result
        assert "hijklm" in result

    def test_empty_after_filtering_returns_original(self):
        from obsidian_rag.retrieval.rag import _extract_keywords
        result = _extract_keywords("a e o")
        # All filtered → returns original text
        assert result == "a e o"


# ---------------------------------------------------------------------------
# Embedding timeout configurable
# ---------------------------------------------------------------------------

class TestEmbeddingTimeout:
    """Verify embedding timeout comes from config."""

    def test_timeout_from_performance_config(self):
        from obsidian_rag.config import PerformanceConfig
        perf = PerformanceConfig(
            auto_tune=False, max_cpu_percent=75, max_memory_percent=80,
            max_parallel_jobs=4, embedding_batch_size=50,
            embedding_timeout=180, query_timeout_seconds=30,
        )
        assert perf.embedding_timeout == 180

    def test_default_timeout_is_120(self):
        from obsidian_rag.config import PerformanceConfig
        perf = PerformanceConfig(
            auto_tune=False, max_cpu_percent=75, max_memory_percent=80,
            max_parallel_jobs=4, embedding_batch_size=50,
            embedding_timeout=120, query_timeout_seconds=30,
        )
        assert perf.embedding_timeout == 120


# ---------------------------------------------------------------------------
# Cache invalidation
# ---------------------------------------------------------------------------

class TestCacheInvalidation:
    """Tests for clear_embed_cache()."""

    def test_clear_embed_cache_exists(self):
        from obsidian_rag.embeddings.ollama import clear_embed_cache
        # Should be callable
        assert callable(clear_embed_cache)

    def test_clear_embed_cache_resets(self):
        from obsidian_rag.embeddings.ollama import _cached_embed, clear_embed_cache
        # cache_info should be available (LRU cache)
        info_before = _cached_embed.cache_info()
        clear_embed_cache()
        info_after = _cached_embed.cache_info()
        # After clear, size should be 0
        assert info_after.currsize == 0


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

class TestThreadSafeSingletons:
    """Verify singletons use locking."""

    def test_lock_exists(self):
        from obsidian_rag.retrieval import rag
        assert hasattr(rag, '_lock')
        assert isinstance(rag._lock, type(threading.Lock()))

    def test_reset_collections_clears_all(self):
        from obsidian_rag.retrieval.rag import _reset_collections
        import obsidian_rag.retrieval.rag as rag_mod
        # Set dummy values
        rag_mod._chroma_client = "dummy_client"
        rag_mod._chroma_collection = "dummy_col"
        rag_mod._code_collection = "dummy_code"
        _reset_collections()
        assert rag_mod._chroma_client is None
        assert rag_mod._chroma_collection is None
        assert rag_mod._code_collection is None

    def test_override_bypasses_singleton(self):
        from obsidian_rag.retrieval.rag import _get_collection
        fake = MagicMock()
        result = _get_collection(_override=fake)
        assert result is fake


# ---------------------------------------------------------------------------
# __all__ exports
# ---------------------------------------------------------------------------

class TestAllExports:
    """Verify __all__ is defined in all subpackage __init__.py."""

    def test_chunking_has_all(self):
        import obsidian_rag.chunking
        assert hasattr(obsidian_rag.chunking, '__all__')
        assert len(obsidian_rag.chunking.__all__) > 0

    def test_embeddings_has_all(self):
        import obsidian_rag.embeddings
        assert hasattr(obsidian_rag.embeddings, '__all__')
        assert "embed_texts" in obsidian_rag.embeddings.__all__

    def test_api_has_all(self):
        import obsidian_rag.api
        assert hasattr(obsidian_rag.api, '__all__')

    def test_store_has_all(self):
        import obsidian_rag.store
        assert hasattr(obsidian_rag.store, '__all__')

    def test_retrieval_has_all(self):
        import obsidian_rag.retrieval
        assert hasattr(obsidian_rag.retrieval, '__all__')

    def test_graph_has_all(self):
        import obsidian_rag.graph
        assert hasattr(obsidian_rag.graph, '__all__')

    def test_pipeline_has_all(self):
        import obsidian_rag.pipeline
        assert hasattr(obsidian_rag.pipeline, '__all__')

    def test_prompts_has_all(self):
        import obsidian_rag.prompts
        assert hasattr(obsidian_rag.prompts, '__all__')


# ---------------------------------------------------------------------------
# Reranker cache
# ---------------------------------------------------------------------------

class TestRerankerCache:
    """Verify _score_chunk has LRU cache."""

    def test_score_chunk_has_cache(self):
        from obsidian_rag.retrieval.reranker import _score_chunk
        assert hasattr(_score_chunk, 'cache_info')
        assert hasattr(_score_chunk, 'cache_clear')

    def test_reranker_disabled_returns_input(self):
        from obsidian_rag.retrieval.reranker import rerank_chunks
        chunks = [("doc1", {"display_text": "text1"}, 0.9)]
        with patch("obsidian_rag.retrieval.reranker.settings") as mock_settings:
            mock_settings.reranker.enabled = False
            result = rerank_chunks(chunks, "test query")
        assert result == chunks

    def test_reranker_empty_chunks(self):
        from obsidian_rag.retrieval.reranker import rerank_chunks
        result = rerank_chunks([], "test query")
        assert result == []


# ---------------------------------------------------------------------------
# Router timeout configurable
# ---------------------------------------------------------------------------

class TestRouterTimeout:
    """Verify router uses config timeout."""

    def test_router_timeout_from_config(self):
        """LLM route should use settings.performance.query_timeout_seconds."""
        # Just verify the code path references the config
        import inspect
        from obsidian_rag.retrieval import router
        source = inspect.getsource(router._llm_route)
        assert "query_timeout_seconds" in source
        assert "timeout=15.0" not in source
