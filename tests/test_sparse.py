"""Tests for BM25Vectorizer (sparse.py)."""

from __future__ import annotations

import json
import math

import pytest

from obsidian_rag.retrieval.sparse import BM25Vectorizer, tokenize


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

class TestTokenize:
    def test_basic(self):
        assert tokenize("Hello World") == ["hello", "world"]

    def test_punctuation(self):
        assert tokenize("foo, bar! baz?") == ["foo", "bar", "baz"]

    def test_underscores(self):
        assert tokenize("my_func") == ["my_func"]

    def test_unicode_normalisation(self):
        # Accented chars decompose and are stripped
        tokens = tokenize("café résumé")
        assert "cafe" in tokens
        assert "resume" in tokens

    def test_numbers(self):
        assert tokenize("v1.2 abc123") == ["v1", "2", "abc123"]

    def test_empty(self):
        assert tokenize("") == []
        assert tokenize("   ") == []


# ---------------------------------------------------------------------------
# BM25Vectorizer
# ---------------------------------------------------------------------------

@pytest.fixture
def corpus():
    """Simple corpus for testing."""
    return [
        ["the", "cat", "sat", "on", "the", "mat"],
        ["the", "dog", "sat", "on", "the", "log"],
        ["cats", "and", "dogs"],
        ["the", "quick", "brown", "fox"],
    ]


@pytest.fixture
def fitted_bm25(corpus):
    bm25 = BM25Vectorizer()
    bm25.fit(corpus)
    return bm25


class TestBM25VectorizerFit:
    def test_vocab_built(self, fitted_bm25, corpus):
        # Every unique token should be in vocab
        unique_tokens = set()
        for doc in corpus:
            unique_tokens.update(doc)
        assert fitted_bm25.vocab_size == len(unique_tokens)

    def test_fitted_flag(self, fitted_bm25):
        assert fitted_bm25.fitted is True

    def test_unfitted(self):
        bm25 = BM25Vectorizer()
        assert bm25.fitted is False
        assert bm25.vocab_size == 0

    def test_empty_corpus(self):
        bm25 = BM25Vectorizer()
        bm25.fit([])
        assert bm25.fitted is False

    def test_idf_values(self, fitted_bm25):
        """Tokens appearing in all docs should have lower IDF than rare ones."""
        vocab = fitted_bm25._vocab
        idf = fitted_bm25._idf
        # "the" appears in 3/4 docs, "cats" in 1/4
        if "the" in vocab and "cats" in vocab:
            assert idf[vocab["cats"]] > idf[vocab["the"]]


class TestBM25VectorizerTransform:
    def test_basic_transform(self, fitted_bm25):
        result = fitted_bm25.transform(["cat", "sat"])
        assert "indices" in result
        assert "values" in result
        assert len(result["indices"]) == len(result["values"])
        assert len(result["indices"]) > 0

    def test_unknown_token_ignored(self, fitted_bm25):
        """Tokens not in vocab produce empty sparse vector."""
        result = fitted_bm25.transform(["xyzunknown"])
        assert result["indices"] == []
        assert result["values"] == []

    def test_empty_tokens(self, fitted_bm25):
        result = fitted_bm25.transform([])
        assert result["indices"] == []
        assert result["values"] == []

    def test_unfitted_transform(self):
        bm25 = BM25Vectorizer()
        result = bm25.transform(["hello"])
        assert result == {"indices": [], "values": []}

    def test_values_positive(self, fitted_bm25):
        """All BM25 scores should be positive for terms with positive IDF."""
        result = fitted_bm25.transform(["cat", "sat", "mat"])
        for v in result["values"]:
            assert v > 0

    def test_doc_len_affects_scores(self, fitted_bm25):
        """Longer docs should get lower TF scores (length normalisation)."""
        short = fitted_bm25.transform(["cat"], doc_len=3)
        long = fitted_bm25.transform(["cat"], doc_len=100)
        # Same token, shorter doc → higher BM25 score
        if short["values"] and long["values"]:
            assert short["values"][0] > long["values"][0]

    def test_repeated_tokens(self, fitted_bm25):
        """Repeated tokens should give higher score than single occurrence."""
        single = fitted_bm25.transform(["cat"], doc_len=10)
        repeated = fitted_bm25.transform(["cat", "cat", "cat"], doc_len=10)
        if single["values"] and repeated["values"]:
            assert repeated["values"][0] > single["values"][0]

    def test_indices_sorted(self, fitted_bm25):
        result = fitted_bm25.transform(["cat", "dog", "mat", "fox"])
        assert result["indices"] == sorted(result["indices"])


class TestBM25VectorizerPersistence:
    def test_save_load_roundtrip(self, fitted_bm25, tmp_path):
        path = tmp_path / "bm25.json"
        fitted_bm25.save(path)

        loaded = BM25Vectorizer.load(path)
        assert loaded.vocab_size == fitted_bm25.vocab_size
        assert loaded.fitted is True
        assert loaded.k1 == fitted_bm25.k1
        assert loaded.b == fitted_bm25.b

    def test_transform_same_after_load(self, fitted_bm25, tmp_path):
        path = tmp_path / "bm25.json"
        fitted_bm25.save(path)
        loaded = BM25Vectorizer.load(path)

        query = ["cat", "sat"]
        orig = fitted_bm25.transform(query)
        after = loaded.transform(query)
        assert orig["indices"] == after["indices"]
        assert orig["values"] == pytest.approx(after["values"])

    def test_save_creates_parent_dirs(self, tmp_path):
        bm25 = BM25Vectorizer()
        bm25.fit([["hello", "world"]])
        path = tmp_path / "subdir" / "nested" / "model.json"
        bm25.save(path)
        assert path.exists()

    def test_saved_file_valid_json(self, fitted_bm25, tmp_path):
        path = tmp_path / "bm25.json"
        fitted_bm25.save(path)
        data = json.loads(path.read_text())
        assert "vocab" in data
        assert "idf" in data
        assert "avgdl" in data
        assert "n_docs" in data


class TestBM25CustomParams:
    def test_custom_k1_b(self, corpus):
        bm25 = BM25Vectorizer(k1=2.0, b=0.5)
        bm25.fit(corpus)
        result = bm25.transform(["cat"])
        assert result["values"]  # should produce values with custom params
        assert bm25.k1 == 2.0
        assert bm25.b == 0.5
