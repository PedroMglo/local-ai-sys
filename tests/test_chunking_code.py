"""Tests for obsidian_rag.chunking.code."""

from __future__ import annotations

from dataclasses import dataclass

from obsidian_rag.chunking.code import (
    _build_chunk,
    _chunk_python_source,
    _chunk_text_fallback,
    _split_if_long,
)


@dataclass
class _FakeCfg:
    """Minimal config object for code chunking tests."""
    max_chars: int = 2000
    overlap_chars: int = 200
    min_chars: int = 50
    contextual_prefix: bool = True


class TestSplitIfLong:
    def test_short_text_no_split(self):
        result = _split_if_long("short", max_chars=100, overlap_chars=20)
        assert result == ["short"]

    def test_long_text_splits(self):
        lines = "\n".join(f"line {i}: {'x' * 40}" for i in range(50))
        result = _split_if_long(lines, max_chars=200, overlap_chars=50)
        assert len(result) > 1

    def test_preserves_lines(self):
        text = "line1\nline2\nline3\nline4\nline5"
        result = _split_if_long(text, max_chars=15, overlap_chars=5)
        for chunk in result:
            # No line should be cut mid-way
            for line in chunk.splitlines():
                assert line in text

    def test_empty_chunks_filtered(self):
        result = _split_if_long("hello", max_chars=1000, overlap_chars=10)
        assert all(c.strip() for c in result)


class TestBuildChunk:
    def test_basic_chunk(self):
        chunk = _build_chunk(
            text="def foo(): pass",
            rel_path="src/main.py",
            repo_name="myrepo",
            note_title="main.py",
            section_header="foo",
            symbol_type="function",
            chunk_index=0,
            contextual_prefix=True,
        )
        assert chunk is not None
        assert chunk.metadata["symbol_type"] == "function"
        assert chunk.metadata["repo_name"] == "myrepo"
        assert "Repo: myrepo" in chunk.text

    def test_empty_text_returns_none(self):
        chunk = _build_chunk(
            text="   ",
            rel_path="src/main.py",
            repo_name="myrepo",
            note_title="main.py",
            section_header="empty",
            symbol_type="function",
            chunk_index=0,
            contextual_prefix=False,
        )
        assert chunk is None

    def test_no_prefix(self):
        chunk = _build_chunk(
            text="def bar(): pass",
            rel_path="src/main.py",
            repo_name="myrepo",
            note_title="main.py",
            section_header="bar",
            symbol_type="function",
            chunk_index=0,
            contextual_prefix=False,
        )
        assert chunk is not None
        assert "Repo:" not in chunk.text


class TestChunkPythonSource:
    def test_produces_chunks(self, sample_python_source):
        cfg = _FakeCfg()
        chunks = _chunk_python_source(sample_python_source, "src/main.py", "testrepo", cfg)
        assert len(chunks) > 0

    def test_finds_functions(self, sample_python_source):
        cfg = _FakeCfg()
        chunks = _chunk_python_source(sample_python_source, "src/main.py", "testrepo", cfg)
        symbol_types = {c.metadata["symbol_type"] for c in chunks}
        assert "function" in symbol_types

    def test_finds_classes(self, sample_python_source):
        cfg = _FakeCfg()
        chunks = _chunk_python_source(sample_python_source, "src/main.py", "testrepo", cfg)
        symbol_types = {c.metadata["symbol_type"] for c in chunks}
        assert "class" in symbol_types or "method" in symbol_types

    def test_finds_module_level(self, sample_python_source):
        cfg = _FakeCfg()
        chunks = _chunk_python_source(sample_python_source, "src/main.py", "testrepo", cfg)
        symbol_types = {c.metadata["symbol_type"] for c in chunks}
        assert "module" in symbol_types

    def test_syntax_error_falls_back(self):
        cfg = _FakeCfg(min_chars=5)
        bad_source = "def broken(\n    # invalid syntax without closing paren"
        chunks = _chunk_python_source(bad_source, "bad.py", "repo", cfg)
        # Should not crash, uses text fallback
        assert isinstance(chunks, list)

    def test_metadata_has_repo_name(self, sample_python_source):
        cfg = _FakeCfg()
        chunks = _chunk_python_source(sample_python_source, "src/main.py", "testrepo", cfg)
        for chunk in chunks:
            assert chunk.metadata["repo_name"] == "testrepo"


class TestChunkTextFallback:
    def test_basic_fallback(self):
        cfg = _FakeCfg(min_chars=5)
        text = "This is some code that failed to parse.\nLine 2.\nLine 3 with more content."
        chunks = _chunk_text_fallback(text, "file.py", "repo", "file.py", cfg)
        assert len(chunks) > 0

    def test_short_text_filtered(self):
        cfg = _FakeCfg(min_chars=100)
        text = "short"
        chunks = _chunk_text_fallback(text, "file.py", "repo", "file.py", cfg)
        assert len(chunks) == 0

    def test_symbol_type_is_text(self):
        cfg = _FakeCfg(min_chars=5)
        text = "Some fallback content with enough characters to pass the minimum."
        chunks = _chunk_text_fallback(text, "file.py", "repo", "file.py", cfg)
        for chunk in chunks:
            assert chunk.metadata["symbol_type"] == "text"
