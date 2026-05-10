"""Tests for obsidian_rag.retrieval.budget."""

from __future__ import annotations

from obsidian_rag.retrieval.budget import (
    allocate_budget,
    estimate_tokens,
    truncate_chunks,
    truncate_text,
)


class TestEstimateTokens:
    def test_single_word(self):
        assert estimate_tokens("hello") == 1  # 1 word * 1.3 → 1

    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_sentence(self):
        text = "The quick brown fox jumps over the lazy dog"
        # 9 words * 1.3 = 11.7 → 11
        assert estimate_tokens(text) == 11

    def test_code_tokens(self):
        text = "def hello_world(x, y):"
        # Regex splits: def, hello_world, x, y → 4 words + parens/colon → ~7 tokens
        result = estimate_tokens(text)
        assert result > 0

    def test_punctuation_counted(self):
        text = "Hello, world!"
        # "Hello", ",", "world", "!" → 4 * 1.3 = 5
        assert estimate_tokens(text) == 5


class TestAllocateBudget:
    def test_no_sources(self):
        result = allocate_budget(1000, has_notes=False, has_code=False, has_graph=False)
        assert result == {"notes": 0, "code": 0, "graph": 0}

    def test_notes_only(self):
        result = allocate_budget(1000, has_notes=True, has_code=False, has_graph=False)
        assert result == {"notes": 1000, "code": 0, "graph": 0}

    def test_code_only(self):
        result = allocate_budget(1000, has_notes=False, has_code=True, has_graph=False)
        assert result == {"notes": 0, "code": 1000, "graph": 0}

    def test_graph_only(self):
        result = allocate_budget(1000, has_notes=False, has_code=False, has_graph=True)
        assert result == {"notes": 0, "code": 0, "graph": 1000}

    def test_notes_and_code(self):
        result = allocate_budget(1000, has_notes=True, has_code=True, has_graph=False)
        assert result["notes"] == 500
        assert result["code"] == 500
        assert result["graph"] == 0

    def test_all_sources(self):
        result = allocate_budget(1000, has_notes=True, has_code=True, has_graph=True)
        assert result["notes"] == 400
        assert result["code"] == 400
        assert result["graph"] == 200

    def test_notes_and_graph(self):
        result = allocate_budget(1000, has_notes=True, has_code=False, has_graph=True)
        assert result["notes"] == 600
        assert result["code"] == 0
        assert result["graph"] == 400

    def test_code_and_graph(self):
        result = allocate_budget(1000, has_notes=False, has_code=True, has_graph=True)
        assert result["notes"] == 0
        assert result["code"] == 600
        assert result["graph"] == 400

    def test_budget_sum_does_not_exceed_total(self):
        result = allocate_budget(1000, has_notes=True, has_code=True, has_graph=True)
        assert sum(result.values()) <= 1000


class TestTruncateChunks:
    def _make_chunk(self, text: str, score: float = 0.9):
        return (text, {"display_text": text}, score)

    def _words(self, n: int) -> str:
        return " ".join(f"word{i}" for i in range(n))

    def test_within_budget(self):
        chunks = [self._make_chunk(self._words(10))]  # ~13 tokens
        result = truncate_chunks(chunks, budget=100)
        assert len(result) == 1

    def test_exceeds_budget(self):
        chunks = [
            self._make_chunk(self._words(80), 0.9),  # ~104 tokens
            self._make_chunk(self._words(80), 0.8),
            self._make_chunk(self._words(80), 0.7),
        ]
        result = truncate_chunks(chunks, budget=150)
        assert len(result) < 3

    def test_empty_chunks(self):
        result = truncate_chunks([], budget=100)
        assert result == []

    def test_first_chunk_always_included(self):
        chunks = [self._make_chunk(self._words(500), 0.9)]  # ~650 tokens
        result = truncate_chunks(chunks, budget=10)
        # First chunk is always included even if it exceeds budget
        assert len(result) == 1


class TestTruncateText:
    def test_short_text_unchanged(self):
        text = "Hello world"
        assert truncate_text(text, budget=100) == text

    def test_truncates_by_lines(self):
        lines = [f"Line {i}: {'x' * 40}" for i in range(20)]
        text = "\n".join(lines)
        result = truncate_text(text, budget=50)
        assert len(result) < len(text)
        # Result should end at a complete line
        assert not result.endswith("\n")

    def test_empty_text(self):
        assert truncate_text("", budget=100) == ""
