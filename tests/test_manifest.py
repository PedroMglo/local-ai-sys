"""Tests for the SQLite ingest manifest — crash recovery and incremental tracking."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from obsidian_rag.pipeline.manifest import IngestManifest


@pytest.fixture
def manifest(tmp_path: Path) -> IngestManifest:
    """Create a fresh manifest in a temp directory."""
    m = IngestManifest(tmp_path / "test_manifest.db")
    yield m
    m.close()


class TestRunLifecycle:
    def test_start_and_finish_run(self, manifest: IngestManifest) -> None:
        run_id = manifest.start_run()
        assert run_id
        assert len(run_id) == 12
        manifest.finish_run(run_id, status="completed")

    def test_incomplete_run_detected(self, manifest: IngestManifest) -> None:
        run_id = manifest.start_run()
        # Do NOT finish the run — simulate crash
        assert manifest.get_last_incomplete_run() == run_id

    def test_completed_run_not_incomplete(self, manifest: IngestManifest) -> None:
        run_id = manifest.start_run()
        manifest.finish_run(run_id, status="completed")
        assert manifest.get_last_incomplete_run() is None

    def test_finish_run_with_error(self, manifest: IngestManifest) -> None:
        run_id = manifest.start_run()
        manifest.finish_run(run_id, status="failed", error="OOM")
        assert manifest.get_last_incomplete_run() is None


class TestFileTracking:
    def test_new_file_needs_reindex(self, manifest: IngestManifest) -> None:
        assert manifest.needs_reindex("src/main.py", 1000.0, 512, "abc123") is True

    def test_unchanged_file_skipped(self, manifest: IngestManifest) -> None:
        manifest.record_file("src/main.py", "myrepo", 1000.0, 512, "abc123", 5)
        assert manifest.needs_reindex("src/main.py", 1000.0, 512, "abc123") is False

    def test_changed_mtime_needs_reindex(self, manifest: IngestManifest) -> None:
        manifest.record_file("src/main.py", "myrepo", 1000.0, 512, "abc123", 5)
        assert manifest.needs_reindex("src/main.py", 2000.0, 512, "abc123") is True

    def test_changed_size_needs_reindex(self, manifest: IngestManifest) -> None:
        manifest.record_file("src/main.py", "myrepo", 1000.0, 512, "abc123", 5)
        assert manifest.needs_reindex("src/main.py", 1000.0, 1024, "abc123") is True

    def test_changed_sha_needs_reindex(self, manifest: IngestManifest) -> None:
        manifest.record_file("src/main.py", "myrepo", 1000.0, 512, "abc123", 5)
        assert manifest.needs_reindex("src/main.py", 1000.0, 512, "def456") is True

    def test_get_indexed_files(self, manifest: IngestManifest) -> None:
        manifest.record_file("a.py", "repo1", 1.0, 100, "h1", 3)
        manifest.record_file("b.py", "repo1", 2.0, 200, "h2", 5)
        manifest.record_file("c.py", "repo2", 3.0, 300, "h3", 2)
        assert manifest.get_indexed_files("repo1") == {"a.py", "b.py"}
        assert manifest.get_indexed_files("repo2") == {"c.py"}

    def test_record_file_upsert(self, manifest: IngestManifest) -> None:
        manifest.record_file("a.py", "repo1", 1.0, 100, "h1", 3)
        manifest.record_file("a.py", "repo1", 2.0, 200, "h2", 5)
        # Should have only one file, not two
        files = manifest.get_indexed_files("repo1")
        assert files == {"a.py"}
        # Should reflect the update
        assert manifest.needs_reindex("a.py", 2.0, 200, "h2") is False


class TestChunkTracking:
    def test_record_and_retrieve_chunks(self, manifest: IngestManifest) -> None:
        manifest.record_file("a.py", "repo1", 1.0, 100, "h1", 2)
        manifest.record_chunks(
            chunk_ids=["c1", "c2"],
            file_path="a.py",
            repo="repo1",
            chunk_hashes=["ch1", "ch2"],
        )
        assert manifest.get_chunk_ids_for_repo("repo1") == {"c1", "c2"}

    def test_mark_chunks_embedded(self, manifest: IngestManifest) -> None:
        manifest.record_file("a.py", "repo1", 1.0, 100, "h1", 2)
        manifest.record_chunks(["c1", "c2"], "a.py", "repo1", ["ch1", "ch2"])
        manifest.mark_chunks_embedded(["c1"])
        stats = manifest.stats()
        assert stats["embedded"] == 1

    def test_record_chunks_replaces_old(self, manifest: IngestManifest) -> None:
        manifest.record_file("a.py", "repo1", 1.0, 100, "h1", 2)
        manifest.record_chunks(["c1", "c2"], "a.py", "repo1", ["ch1", "ch2"])
        # Re-record with different chunks (file changed)
        manifest.record_chunks(["c3"], "a.py", "repo1", ["ch3"])
        ids = manifest.get_chunk_ids_for_repo("repo1")
        assert ids == {"c3"}

    def test_get_stale_chunks(self, manifest: IngestManifest) -> None:
        manifest.record_file("a.py", "repo1", 1.0, 100, "h1", 2)
        manifest.record_chunks(["c1", "c2", "c3"], "a.py", "repo1", ["h1", "h2", "h3"])
        stale = manifest.get_stale_chunks("repo1", {"c1", "c2"})
        assert stale == {"c3"}

    def test_delete_chunks(self, manifest: IngestManifest) -> None:
        manifest.record_file("a.py", "repo1", 1.0, 100, "h1", 2)
        manifest.record_chunks(["c1", "c2"], "a.py", "repo1", ["h1", "h2"])
        manifest.delete_chunks(["c1"])
        assert manifest.get_chunk_ids_for_repo("repo1") == {"c2"}

    def test_mark_empty_list_no_error(self, manifest: IngestManifest) -> None:
        manifest.mark_chunks_embedded([])  # should not raise

    def test_delete_empty_list_no_error(self, manifest: IngestManifest) -> None:
        manifest.delete_chunks([])  # should not raise


class TestStaleFileCleanup:
    def test_delete_stale_files(self, manifest: IngestManifest) -> None:
        manifest.record_file("a.py", "repo1", 1.0, 100, "h1", 2)
        manifest.record_file("b.py", "repo1", 2.0, 200, "h2", 1)
        manifest.record_chunks(["c1", "c2"], "a.py", "repo1", ["h1", "h2"])
        manifest.record_chunks(["c3"], "b.py", "repo1", ["h3"])

        # b.py was deleted from the repo
        deleted_ids = manifest.delete_stale_files("repo1", {"a.py"})
        assert set(deleted_ids) == {"c3"}
        assert manifest.get_indexed_files("repo1") == {"a.py"}
        assert manifest.get_chunk_ids_for_repo("repo1") == {"c1", "c2"}


class TestCrashRecovery:
    def test_resume_after_crash(self, manifest: IngestManifest) -> None:
        """Simulate crash: start run, record some files, don't finish. Verify state."""
        run_id = manifest.start_run()
        manifest.record_file("a.py", "repo1", 1.0, 100, "h1", 2)
        manifest.record_chunks(["c1", "c2"], "a.py", "repo1", ["h1", "h2"])
        manifest.mark_chunks_embedded(["c1", "c2"])

        # Simulate crash — don't finish run
        # Reopen manifest (simulates restart)
        manifest.close()
        manifest2 = IngestManifest(manifest._db_path)
        try:
            assert manifest2.get_last_incomplete_run() == run_id
            # a.py was already processed — should NOT need reindex
            assert manifest2.needs_reindex("a.py", 1.0, 100, "h1") is False
            # b.py was never processed — should need reindex
            assert manifest2.needs_reindex("b.py", 2.0, 200, "h2") is True
        finally:
            manifest2.close()


class TestFileSha256:
    def test_sha256_returns_short_hash(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        h = IngestManifest.file_sha256(f)
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)

    def test_sha256_consistent(self, tmp_path: Path) -> None:
        f = tmp_path / "test.txt"
        f.write_text("hello world")
        h1 = IngestManifest.file_sha256(f)
        h2 = IngestManifest.file_sha256(f)
        assert h1 == h2

    def test_sha256_different_content(self, tmp_path: Path) -> None:
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("hello")
        f2.write_text("world")
        assert IngestManifest.file_sha256(f1) != IngestManifest.file_sha256(f2)


class TestStats:
    def test_empty_stats(self, manifest: IngestManifest) -> None:
        stats = manifest.stats()
        assert stats == {"files": 0, "chunks": 0, "embedded": 0, "runs": 0}

    def test_stats_with_data(self, manifest: IngestManifest) -> None:
        manifest.start_run()
        manifest.record_file("a.py", "repo1", 1.0, 100, "h1", 2)
        manifest.record_chunks(["c1", "c2"], "a.py", "repo1", ["h1", "h2"])
        manifest.mark_chunks_embedded(["c1"])
        stats = manifest.stats()
        assert stats["files"] == 1
        assert stats["chunks"] == 2
        assert stats["embedded"] == 1
        assert stats["runs"] == 1
