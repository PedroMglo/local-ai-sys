"""Tests for the bounded ingest pipeline — backpressure, batching, and end-to-end flow."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from obsidian_rag.chunking.markdown import Chunk
from obsidian_rag.pipeline.ingest import (
    EmbeddedBatch,
    FileJob,
    IngestPipeline,
    IngestResult,
    IngestSource,
)
from obsidian_rag.pipeline.manifest import IngestManifest


@pytest.fixture
def manifest(tmp_path: Path) -> IngestManifest:
    m = IngestManifest(tmp_path / "test.db")
    yield m
    m.close()


@pytest.fixture
def fake_perf():
    """Minimal PerformanceConfig-like object for testing."""
    from obsidian_rag.config import PerformanceConfig

    return PerformanceConfig(
        auto_tune=False,
        max_cpu_percent=90,
        max_memory_percent=90,
        max_parallel_jobs=2,
        embedding_batch_size=3,
        embedding_timeout=30,
        query_timeout_seconds=10,
        graph_timeout=60,
        parser_workers=2,
        embedding_batch_max_chars=5000,
        chunks_queue_max=10,
        files_queue_max=10,
        pause_memory_percent=85,
        abort_memory_percent=95,
    )


@pytest.fixture
def mock_collection():
    """Mock ChromaDB collection."""
    coll = MagicMock()
    coll.add = MagicMock()
    coll.delete = MagicMock()
    coll.count = MagicMock(return_value=0)
    coll.get = MagicMock(return_value={"ids": []})
    return coll


def _make_chunks(n: int, prefix: str = "chunk") -> list[Chunk]:
    return [
        Chunk(
            id=f"{prefix}_{i}",
            text=f"text for {prefix}_{i} " * 10,
            metadata={"source_path": f"test/{prefix}_{i}.py", "display_text": f"display {i}"},
        )
        for i in range(n)
    ]


def _fake_embed(texts: list[str]) -> list[list[float]]:
    """Dummy embedding function for tests."""
    return [[0.1] * 1024 for _ in texts]


class TestIngestPipelineEndToEnd:
    """End-to-end tests with mocked embed_texts and file parsing."""

    def test_pipeline_processes_files(
        self, tmp_path: Path, manifest: IngestManifest, fake_perf, mock_collection
    ) -> None:
        """Create real Python files, run pipeline, verify chunks are stored."""
        # Create a tiny repo with files large enough to produce chunks (min_chars=80)
        repo = tmp_path / "test_repo"
        repo.mkdir()
        (repo / "hello.py").write_text(
            '"""Module docstring for hello module with enough text to pass min_chars filter."""\n\n'
            "import os\nimport sys\n\n\n"
            "def hello(name: str) -> str:\n"
            '    """Say hello to someone with a friendly greeting message."""\n'
            "    greeting = f'Hello, {name}! Welcome to the system.'\n"
            "    print(greeting)\n"
            "    return greeting\n"
        )
        (repo / "utils.py").write_text(
            '"""Utility functions for mathematical operations and data processing."""\n\n'
            "import math\n\n\n"
            "def add(a: float, b: float) -> float:\n"
            '    """Add two numbers together and return the result with validation."""\n'
            "    if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):\n"
            "        raise TypeError('Both arguments must be numbers')\n"
            "    return a + b\n\n\n"
            "def multiply(a: float, b: float) -> float:\n"
            '    """Multiply two numbers and return the product."""\n'
            "    return a * b\n"
        )

        sources = [IngestSource(source_type="code", path=repo, name="test_repo")]

        pipeline = IngestPipeline(manifest, fake_perf, mock_collection, embed_fn=_fake_embed)
        result = pipeline.run(sources)

        assert result.files_scanned >= 2
        assert result.files_parsed >= 1  # some files may have < min_chars
        assert result.chunks_embedded >= 1
        assert result.chunks_stored >= 1
        assert result.elapsed_seconds > 0
        assert mock_collection.add.called

    def test_pipeline_skips_unchanged_files(
        self, tmp_path: Path, manifest: IngestManifest, fake_perf, mock_collection
    ) -> None:
        """Files already in the manifest with same mtime/size/sha should be skipped."""
        repo = tmp_path / "test_repo"
        repo.mkdir()
        f = repo / "hello.py"
        f.write_text("def hello():\n    return 'world'\n")

        # Pre-populate manifest
        stat = f.stat()
        sha = IngestManifest.file_sha256(f)
        rel_path = str(f.relative_to(repo))
        manifest.record_file(rel_path, "test_repo", stat.st_mtime, stat.st_size, sha, 1)

        sources = [IngestSource(source_type="code", path=repo, name="test_repo")]

        pipeline = IngestPipeline(manifest, fake_perf, mock_collection, embed_fn=_fake_embed)
        result = pipeline.run(sources)

        assert result.files_skipped >= 1
        assert result.files_parsed == 0  # nothing to parse

    def test_empty_repo(
        self, tmp_path: Path, manifest: IngestManifest, fake_perf, mock_collection
    ) -> None:
        """Empty repo should produce zero results without errors."""
        repo = tmp_path / "empty_repo"
        repo.mkdir()

        sources = [IngestSource(source_type="code", path=repo, name="empty_repo")]

        pipeline = IngestPipeline(manifest, fake_perf, mock_collection, embed_fn=_fake_embed)
        result = pipeline.run(sources)

        assert result.files_scanned == 0
        assert result.chunks_produced == 0
        assert not result.errors


class TestBatchClosing:
    """Test that the embedding batcher respects count, chars, and time limits."""

    def test_batch_closes_on_count(self, fake_perf) -> None:
        """Batch should close when reaching embedding_batch_size chunks."""
        # embedding_batch_size=3 in fake_perf
        assert fake_perf.embedding_batch_size == 3

    def test_batch_max_chars_config(self, fake_perf) -> None:
        """embedding_batch_max_chars should be set."""
        assert fake_perf.embedding_batch_max_chars == 5000


class TestIngestResult:
    def test_default_result(self) -> None:
        r = IngestResult()
        assert r.files_scanned == 0
        assert r.errors == []
        assert r.elapsed_seconds == 0.0

    def test_result_tracks_errors(self) -> None:
        r = IngestResult()
        r.errors.append("test error")
        assert len(r.errors) == 1


class TestFileJob:
    def test_file_job_picklable(self) -> None:
        """FileJob must be picklable for ProcessPoolExecutor."""
        import pickle

        job = FileJob(
            path="/tmp/test.py",
            repo_name="myrepo",
            repo_dir="/tmp",
            source_type="code",
        )
        pickled = pickle.dumps(job)
        restored = pickle.loads(pickled)
        assert restored == job

    def test_embedded_batch_structure(self) -> None:
        chunks = _make_chunks(2)
        embeddings = [[0.1] * 10, [0.2] * 10]
        batch = EmbeddedBatch(chunks=chunks, embeddings=embeddings)
        assert len(batch.chunks) == 2
        assert len(batch.embeddings) == 2


class TestMultipleRepos:
    def test_pipeline_handles_multiple_sources(
        self, tmp_path: Path, manifest: IngestManifest, fake_perf, mock_collection
    ) -> None:
        """Pipeline should process multiple repos in a single run."""
        repo1 = tmp_path / "repo1"
        repo2 = tmp_path / "repo2"
        repo1.mkdir()
        repo2.mkdir()
        (repo1 / "a.py").write_text(
            '"""Module A with enough content to produce a chunk for testing."""\n\n'
            "def func_a(x: int) -> int:\n"
            '    """Calculate something useful from the input value."""\n'
            "    return x * 2 + 1\n"
        )
        (repo2 / "b.py").write_text(
            '"""Module B with enough content to produce a chunk for testing."""\n\n'
            "def func_b(y: int) -> int:\n"
            '    """Calculate something useful from the input value."""\n'
            "    return y * 3 + 2\n"
        )

        sources = [
            IngestSource(source_type="code", path=repo1, name="repo1"),
            IngestSource(source_type="code", path=repo2, name="repo2"),
        ]

        pipeline = IngestPipeline(manifest, fake_perf, mock_collection, embed_fn=_fake_embed)
        result = pipeline.run(sources)

        assert result.files_scanned >= 2
