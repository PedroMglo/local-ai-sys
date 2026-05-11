"""Concurrency tests for the VectorStore layer.

Validates that multiple threads can read/write to the store
simultaneously without deadlocks, data corruption, or errors.

Set QDRANT_TEST_URL=http://localhost:6333 to run against a live server.
Without it, tests run against embedded Qdrant (may have lock limitations).
"""

from __future__ import annotations

import math
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_QDRANT_TEST_URL = os.environ.get("QDRANT_TEST_URL", "")
_DIM = 1024


def _vec(seed: float = 0.1) -> list[float]:
    return [math.sin(seed * (i + 1)) for i in range(_DIM)]


def _make_store(tmp_path):
    try:
        from obsidian_rag.store.qdrant_store import QdrantVectorStore
    except ImportError:
        pytest.skip("qdrant-client not installed")
    if _QDRANT_TEST_URL:
        return QdrantVectorStore(url=_QDRANT_TEST_URL)
    return QdrantVectorStore(data_dir=tmp_path / "conc_qdrant")


@pytest.fixture
def store(tmp_path):
    return _make_store(tmp_path)


# ---------------------------------------------------------------------------
# Parallel queries
# ---------------------------------------------------------------------------

class TestParallelQueries:

    def test_parallel_queries_return_valid_results(self, store):
        """10 threads querying simultaneously all get valid results."""
        col = "conc_parallel_q"
        # Seed data
        ids = [f"pq-{i}" for i in range(20)]
        embs = [_vec(0.1 * (i + 1)) for i in range(20)]
        docs = [f"Document {i}" for i in range(20)]
        metas = [{"idx": str(i)} for i in range(20)]
        store.upsert_batch(ids, embs, docs, metas, collection=col)

        errors: list[Exception] = []
        results_count: list[int] = []

        def _query(seed: float):
            try:
                res = store.query(_vec(seed), n=5, collection=col)
                results_count.append(len(res))
            except Exception as exc:
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(_query, 0.1 * (i + 1)) for i in range(10)]
            for f in as_completed(futures):
                f.result()  # propagate exceptions

        assert not errors, f"Errors during parallel queries: {errors}"
        assert len(results_count) == 10
        assert all(c > 0 for c in results_count)


# ---------------------------------------------------------------------------
# Query during upsert
# ---------------------------------------------------------------------------

class TestQueryDuringUpsert:

    @pytest.mark.skipif(
        not _QDRANT_TEST_URL,
        reason="Embedded Qdrant has numpy race condition during concurrent reads/writes; requires live server",
    )
    def test_reads_dont_block_during_writes(self, store):
        """A reader thread can query while a writer thread upserts."""
        col = "conc_rw"
        # Seed some initial data
        ids = [f"rw-init-{i}" for i in range(10)]
        embs = [_vec(0.2 * (i + 1)) for i in range(10)]
        docs = [f"Init doc {i}" for i in range(10)]
        metas = [{"phase": "init"} for _ in range(10)]
        store.upsert_batch(ids, embs, docs, metas, collection=col)

        write_done = threading.Event()
        read_errors: list[Exception] = []
        read_results: list[int] = []

        def _writer():
            for batch in range(5):
                b_ids = [f"rw-w-{batch}-{i}" for i in range(10)]
                b_embs = [_vec(0.3 * (batch + i + 1)) for i in range(10)]
                b_docs = [f"Write batch {batch} doc {i}" for i in range(10)]
                b_metas = [{"phase": "write", "batch": str(batch)} for _ in range(10)]
                store.upsert_batch(b_ids, b_embs, b_docs, b_metas, collection=col)
            write_done.set()

        def _reader():
            attempts = 0
            while not write_done.is_set() and attempts < 50:
                try:
                    res = store.query(_vec(0.5), n=3, collection=col)
                    read_results.append(len(res))
                except Exception as exc:
                    read_errors.append(exc)
                attempts += 1

        t_write = threading.Thread(target=_writer)
        t_read = threading.Thread(target=_reader)
        t_write.start()
        t_read.start()
        t_write.join(timeout=60)
        t_read.join(timeout=60)

        assert not read_errors, f"Read errors during write: {read_errors}"
        assert len(read_results) > 0, "Reader got no results at all"


# ---------------------------------------------------------------------------
# Multiple upsert streams to different collections
# ---------------------------------------------------------------------------

class TestMultiCollectionUpsert:

    def test_parallel_upserts_to_different_collections(self, store):
        """3 threads upserting to separate collections — counts correct."""
        errors: list[Exception] = []

        def _upsert_col(col_name: str, n: int):
            try:
                ids = [f"{col_name}-{i}" for i in range(n)]
                embs = [_vec(0.1 * (i + 1)) for i in range(n)]
                docs = [f"Doc {col_name} {i}" for i in range(n)]
                metas = [{"col": col_name} for _ in range(n)]
                store.upsert_batch(ids, embs, docs, metas, collection=col_name)
            except Exception as exc:
                errors.append(exc)

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [
                pool.submit(_upsert_col, f"conc_mc_{i}", 15)
                for i in range(3)
            ]
            for f in as_completed(futures):
                f.result()

        assert not errors, f"Errors during parallel upserts: {errors}"
        for i in range(3):
            assert store.count(collection=f"conc_mc_{i}") == 15


# ---------------------------------------------------------------------------
# Health check under load
# ---------------------------------------------------------------------------

class TestHealthUnderLoad:

    def test_health_during_operations(self, store):
        """health() returns True while queries and upserts happen."""
        col = "conc_health"
        ids = [f"h-{i}" for i in range(10)]
        embs = [_vec(0.1 * (i + 1)) for i in range(10)]
        docs = [f"Health doc {i}" for i in range(10)]
        metas = [{"t": "health"} for _ in range(10)]
        store.upsert_batch(ids, embs, docs, metas, collection=col)

        health_results: list[bool] = []

        def _check_health():
            for _ in range(5):
                health_results.append(store.health())

        def _do_queries():
            for _ in range(5):
                store.query(_vec(0.3), n=3, collection=col)

        t1 = threading.Thread(target=_check_health)
        t2 = threading.Thread(target=_do_queries)
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        assert all(health_results), "health() returned False during operations"
