"""Shared fixtures for obsidian-rag tests."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest


@pytest.fixture
def tmp_source_dir(tmp_path: Path) -> Path:
    """Create a temporary source directory with sample markdown files."""
    source = tmp_path / "source"
    source.mkdir()
    return source


@pytest.fixture
def sample_markdown_note(tmp_source_dir: Path) -> Path:
    """Create a sample markdown note with headers and content."""
    note = tmp_source_dir / "sample.md"
    note.write_text(textwrap.dedent("""\
        ---
        title: Sample Note
        tags: [test, sample]
        ---

        # Sample Note

        This is the introduction paragraph with enough text to pass the minimum
        character threshold for chunking in the RAG pipeline.

        ## First Section

        Content of the first section. This section contains information about
        the first topic and has multiple sentences to ensure it meets the
        minimum chunk size requirements for the system.

        ## Second Section

        Content of the second section. More detailed analysis of the second
        topic including several paragraphs of useful context and detail.

        ### Subsection 2.1

        A deeper subsection with its own content, providing granularity in
        the chunking process and testing nested header handling.
    """), encoding="utf-8")
    return note


@pytest.fixture
def navigation_note(tmp_source_dir: Path) -> Path:
    """Create a note that is mostly wikilinks (navigation content)."""
    note = tmp_source_dir / "nav.md"
    note.write_text(textwrap.dedent("""\
        # Index

        - [[Note A]]
        - [[Note B]]
        - [[Note C]]
        - [[Note D]]
        - [[Note E]]
    """), encoding="utf-8")
    return note


@pytest.fixture
def sample_python_source() -> str:
    """Sample Python source code for AST chunking tests."""
    return textwrap.dedent('''\
        """Module docstring for testing."""

        import os
        import sys

        CONSTANT = 42


        def hello(name: str) -> str:
            """Say hello."""
            return f"Hello, {name}!"


        def compute(x: int, y: int) -> int:
            """Compute the sum."""
            result = x + y
            return result


        class Calculator:
            """A simple calculator class."""

            def add(self, a: int, b: int) -> int:
                return a + b

            def subtract(self, a: int, b: int) -> int:
                return a - b
    ''')
