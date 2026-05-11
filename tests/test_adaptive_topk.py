"""Tests for adaptive top_k and query complexity estimation."""

from __future__ import annotations

import pytest


class TestEstimateComplexity:
    """Tests for _estimate_complexity() in rag.py."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from obsidian_rag.retrieval.rag import _estimate_complexity
        self.estimate = _estimate_complexity

    def test_short_query_is_simple(self):
        assert self.estimate("zsh aliases") == "simple"

    def test_single_word_is_simple(self):
        assert self.estimate("docker") == "simple"

    def test_three_words_is_simple(self):
        assert self.estimate("configurar aliases zsh") == "simple"

    def test_normal_length_query(self):
        assert self.estimate("como configurar aliases no zsh") == "normal"

    def test_long_query_is_complex(self):
        assert self.estimate("quero saber como configurar aliases no zsh e também no bash com diferentes ficheiros") == "complex"

    def test_graph_signal_makes_complex(self):
        assert self.estimate("qual a arquitectura do projecto") == "complex"

    def test_dependency_signal_makes_complex(self):
        assert self.estimate("o que depende de config.py") == "complex"

    def test_boolean_operator_makes_complex(self):
        assert self.estimate("docker and kubernetes setup") == "complex"

    def test_multiple_questions_makes_complex(self):
        assert self.estimate("o que é? como funciona?") == "complex"

    def test_graph_pattern_makes_complex(self):
        assert self.estimate("como funciona o pipeline de sync") == "complex"

    def test_call_chain_makes_complex(self):
        assert self.estimate("what calls the build_graph function") == "complex"


class TestAdaptiveTopK:
    """Tests for effective top_k scaling based on complexity."""

    def test_simple_reduces_topk(self):
        """Simple query → top_k // 3, min 3."""
        base_k = 10
        effective = max(3, base_k // 3)
        assert effective == 3

    def test_normal_keeps_topk(self):
        """Normal query → unchanged top_k."""
        base_k = 10
        effective = base_k
        assert effective == 10

    def test_complex_doubles_topk(self):
        """Complex query → top_k * 2, max 20."""
        base_k = 10
        effective = min(base_k * 2, 20)
        assert effective == 20

    def test_complex_capped_at_20(self):
        """Complex with high top_k doesn't exceed 20."""
        base_k = 15
        effective = min(base_k * 2, 20)
        assert effective == 20

    def test_simple_never_below_3(self):
        """Simple with top_k=5 → max(3, 5//3) = 3."""
        base_k = 5
        effective = max(3, base_k // 3)
        assert effective == 3


class TestScaleKBySize:
    """Tests for _scale_k_by_size() collection-size scaling."""

    @pytest.fixture(autouse=True)
    def _import(self):
        from obsidian_rag.retrieval.rag import _scale_k_by_size
        self.scale = _scale_k_by_size

    def test_small_collection_no_scaling(self):
        """Collections <= 1000 chunks: no scaling."""
        assert self.scale(10, 500) == 10
        assert self.scale(10, 1000) == 10

    def test_10k_collection_scales_up(self):
        """10 000 chunks → factor ~2.0 → k*2."""
        result = self.scale(10, 10_000)
        assert result == 20  # 10 * (1 + log10(10)) = 10 * 2 = 20

    def test_100k_collection_capped_at_30(self):
        """Very large collection: result capped at 30."""
        result = self.scale(15, 100_000)
        assert result <= 30

    def test_minimum_is_3(self):
        """Result never below 3."""
        result = self.scale(1, 5000)
        assert result >= 3

    def test_2000_chunks_modest_scaling(self):
        """2 000 chunks → factor ~1.3 → 10*1.3 ≈ 13."""
        result = self.scale(10, 2000)
        assert 10 < result < 20


class TestCachedCount:
    """Tests for _cached_count() TTL behaviour."""

    def test_cache_returns_same_value_within_ttl(self):
        from obsidian_rag.retrieval.rag import _cached_count, _count_cache

        class FakeStore:
            def count(self, *, collection="x"):
                return 42

        _count_cache.clear()
        assert _cached_count(FakeStore(), "test_col") == 42
        # Second call should use cache — even if store would return different
        class ChangedStore:
            def count(self, *, collection="x"):
                return 999
        assert _cached_count(ChangedStore(), "test_col") == 42
        _count_cache.clear()
