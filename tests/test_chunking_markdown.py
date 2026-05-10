"""Tests for obsidian_rag.chunking.markdown."""

from __future__ import annotations

from pathlib import Path

from obsidian_rag.chunking.markdown import (
    _compute_hash,
    _is_navigation_content,
    _split_by_headers,
    _split_long_text,
    _strip_frontmatter,
    chunk_note,
)


class TestComputeHash:
    def test_deterministic(self):
        assert _compute_hash("hello") == _compute_hash("hello")

    def test_different_inputs(self):
        assert _compute_hash("hello") != _compute_hash("world")

    def test_length_16(self):
        assert len(_compute_hash("any text")) == 16


class TestStripFrontmatter:
    def test_removes_yaml_frontmatter(self):
        text = "---\ntitle: Test\ntags: [a]\n---\n\n# Hello"
        assert _strip_frontmatter(text) == "# Hello"

    def test_no_frontmatter(self):
        text = "# Just a header\n\nSome content."
        assert _strip_frontmatter(text) == text

    def test_empty_after_strip(self):
        text = "---\ntitle: Only meta\n---\n"
        assert _strip_frontmatter(text) == ""


class TestIsNavigationContent:
    def test_pure_wikilinks(self):
        text = "- [[Note A]]\n- [[Note B]]\n- [[Note C]]"
        assert _is_navigation_content(text) is True

    def test_mostly_wikilinks(self):
        text = "Index page\n- [[A]]\n- [[B]]\n- [[C]]\n- [[D]]"
        assert _is_navigation_content(text) is True  # 4/5 > 0.7

    def test_regular_content(self):
        text = "This is a paragraph about machine learning.\nIt has real content."
        assert _is_navigation_content(text) is False

    def test_empty_text(self):
        assert _is_navigation_content("") is True

    def test_mixed_below_threshold(self):
        text = "Intro paragraph.\nMore text.\nDetails here.\n- [[Link]]"
        assert _is_navigation_content(text) is False  # 1/4 = 0.25


class TestSplitByHeaders:
    def test_single_header(self):
        text = "# Title\n\nContent here."
        sections = _split_by_headers(text)
        assert len(sections) == 1
        assert sections[0][0] == "Title"
        assert "Content here." in sections[0][1]

    def test_multiple_headers(self):
        text = "# Title\n\nIntro.\n\n## Section A\n\nContent A.\n\n## Section B\n\nContent B."
        sections = _split_by_headers(text)
        headers = [s[0] for s in sections]
        assert "Title" in headers
        assert "Section A" in headers
        assert "Section B" in headers

    def test_no_headers(self):
        text = "Just plain text without any headers."
        sections = _split_by_headers(text)
        assert len(sections) == 1
        assert sections[0][0] == ""
        assert sections[0][1] == text

    def test_preamble_before_first_header(self):
        text = "Some preamble.\n\n# Title\n\nBody."
        sections = _split_by_headers(text)
        assert sections[0][0] == ""
        assert "preamble" in sections[0][1]

    def test_nested_headers(self):
        text = "## H2\n\nH2 body.\n\n### H3\n\nH3 body."
        sections = _split_by_headers(text)
        assert len(sections) == 2


class TestSplitLongText:
    def test_short_text_no_split(self):
        text = "Short text."
        result = _split_long_text(text, max_chars=100, overlap=20)
        assert result == ["Short text."]

    def test_long_text_splits(self):
        text = "A" * 500
        result = _split_long_text(text, max_chars=200, overlap=50)
        assert len(result) > 1
        # Each chunk should be <= max_chars
        for chunk in result:
            assert len(chunk) <= 200

    def test_splits_on_paragraph_boundary(self):
        text = "First paragraph.\n\nSecond paragraph.\n\nThird paragraph."
        result = _split_long_text(text, max_chars=30, overlap=5)
        assert len(result) >= 2

    def test_empty_chunks_filtered(self):
        result = _split_long_text("Hello", max_chars=1000, overlap=10)
        assert all(c.strip() for c in result)


class TestChunkNote:
    def test_produces_chunks(self, sample_markdown_note, tmp_source_dir):
        chunks = chunk_note(sample_markdown_note, tmp_source_dir)
        assert len(chunks) > 0

    def test_chunks_have_metadata(self, sample_markdown_note, tmp_source_dir):
        chunks = chunk_note(sample_markdown_note, tmp_source_dir)
        for chunk in chunks:
            assert chunk.id
            assert chunk.text
            assert "source_path" in chunk.metadata
            assert "note_title" in chunk.metadata

    def test_frontmatter_stripped(self, sample_markdown_note, tmp_source_dir):
        chunks = chunk_note(sample_markdown_note, tmp_source_dir)
        for chunk in chunks:
            assert "---" not in chunk.text.split("\n")[0] or "Nota:" in chunk.text.split("\n")[0]

    def test_navigation_note_produces_few_chunks(self, navigation_note, tmp_source_dir):
        chunks = chunk_note(navigation_note, tmp_source_dir)
        # Navigation-heavy content should be filtered out
        assert len(chunks) == 0 or all(
            not _is_navigation_content(c.metadata.get("display_text", c.text))
            for c in chunks
        )

    def test_nonexistent_file_returns_empty(self, tmp_source_dir):
        fake = tmp_source_dir / "nonexistent.md"
        chunks = chunk_note(fake, tmp_source_dir)
        assert chunks == []

    def test_empty_file_returns_empty(self, tmp_source_dir):
        empty = tmp_source_dir / "empty.md"
        empty.write_text("", encoding="utf-8")
        chunks = chunk_note(empty, tmp_source_dir)
        assert chunks == []

    def test_contextual_prefix_present(self, sample_markdown_note, tmp_source_dir):
        chunks = chunk_note(sample_markdown_note, tmp_source_dir)
        # With contextual_prefix=true (default), chunks should have "Nota:" prefix
        assert any("Nota:" in c.text for c in chunks)
