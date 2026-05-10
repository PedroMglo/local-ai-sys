"""Tests for the Dask engine abstraction layer (pipeline/dask_engine.py)."""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from unittest.mock import MagicMock, patch

import pytest

from obsidian_rag.pipeline.dask_engine import create_parser_pool


# ---------------------------------------------------------------------------
# create_parser_pool — local engine
# ---------------------------------------------------------------------------

class TestCreateParserPoolLocal:
    """Tests for create_parser_pool with engine='local'."""

    def test_returns_process_pool_executor(self) -> None:
        pool = create_parser_pool(engine="local", n_workers=2)
        try:
            assert isinstance(pool, ProcessPoolExecutor)
        finally:
            pool.shutdown(wait=False)

    def test_submit_and_result(self) -> None:
        pool = create_parser_pool(engine="local", n_workers=1)
        try:
            future = pool.submit(pow, 2, 10)
            assert future.result(timeout=10) == 1024
        finally:
            pool.shutdown(wait=True)

    def test_unknown_engine_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown pipeline engine"):
            create_parser_pool(engine="spark")


# ---------------------------------------------------------------------------
# create_parser_pool — dask engine (without dask installed)
# ---------------------------------------------------------------------------

class TestCreateParserPoolDaskMissing:
    """Verify clear error when dask is not installed."""

    def test_import_error_when_dask_missing(self) -> None:
        with patch.dict("sys.modules", {"dask": None, "dask.distributed": None}):
            with pytest.raises(ImportError, match="dask\\[distributed\\]"):
                create_parser_pool(engine="dask", n_workers=2)


# ---------------------------------------------------------------------------
# DaskParserPool — with dask installed (skipped if missing)
# ---------------------------------------------------------------------------

def _has_dask() -> bool:
    try:
        import dask.distributed  # noqa: F401
        return True
    except ImportError:
        return False


@pytest.mark.skipif(not _has_dask(), reason="dask[distributed] not installed")
class TestDaskParserPool:
    """Integration tests for DaskParserPool — require dask[distributed]."""

    def test_local_cluster_submit(self) -> None:
        pool = create_parser_pool(engine="dask", n_workers=1)
        try:
            future = pool.submit(pow, 2, 10)
            assert future.result(timeout=30) == 1024
        finally:
            pool.shutdown(wait=True)

    def test_context_manager(self) -> None:
        with create_parser_pool(engine="dask", n_workers=1) as pool:
            future = pool.submit(sum, [1, 2, 3])
            assert future.result(timeout=30) == 6

    def test_shutdown_cancel_futures(self) -> None:
        pool = create_parser_pool(engine="dask", n_workers=1)
        pool.shutdown(wait=False, cancel_futures=True)
        # No exception = success


# ---------------------------------------------------------------------------
# IngestPipeline — engine integration (always uses local in tests)
# ---------------------------------------------------------------------------

class TestIngestPipelineEngineConfig:
    """Verify IngestPipeline uses the engine config from PipelineConfig."""

    def test_default_engine_is_local(self, tmp_path) -> None:
        """When pipeline_config is None, engine defaults to 'local'."""
        from obsidian_rag.config import PerformanceConfig
        from obsidian_rag.pipeline.ingest import IngestPipeline, IngestSource
        from obsidian_rag.pipeline.manifest import IngestManifest

        manifest = IngestManifest(tmp_path / "test.db")
        perf = PerformanceConfig(
            auto_tune=False, max_cpu_percent=90, max_memory_percent=90,
            max_parallel_jobs=2, embedding_batch_size=3, embedding_timeout=30,
            query_timeout_seconds=10, parser_workers=1,
            embedding_batch_max_chars=5000, chunks_queue_max=10,
            files_queue_max=10, pause_memory_percent=85, abort_memory_percent=95,
        )
        store = MagicMock()
        store.upsert_batch = MagicMock()
        store.delete_ids = MagicMock(return_value=0)
        store.get_existing_ids = MagicMock(return_value=set())

        def _noop_embed(texts):
            return [[0.1] * 1024 for _ in texts]

        from obsidian_rag.pipeline.governor import GovernorAction
        gov = MagicMock()
        gov.check = MagicMock(return_value=GovernorAction.CONTINUE)
        gov.wait_until_safe = MagicMock(return_value=GovernorAction.CONTINUE)
        gov.start = MagicMock()
        gov.stop = MagicMock()

        pipeline = IngestPipeline(
            manifest, perf, store,
            embed_fn=_noop_embed,
            governor=gov,
            pipeline_config=None,  # default = local
        )
        result = pipeline.run([])  # no sources — just verify it initialises
        manifest.close()

        assert result.files_scanned == 0
        assert result.errors == []

    def test_explicit_local_engine(self, tmp_path) -> None:
        """Verify engine='local' works when set explicitly in PipelineConfig."""
        from obsidian_rag.config import PipelineConfig, PerformanceConfig
        from obsidian_rag.pipeline.ingest import IngestPipeline, IngestSource
        from obsidian_rag.pipeline.manifest import IngestManifest

        manifest = IngestManifest(tmp_path / "test.db")
        perf = PerformanceConfig(
            auto_tune=False, max_cpu_percent=90, max_memory_percent=90,
            max_parallel_jobs=2, embedding_batch_size=3, embedding_timeout=30,
            query_timeout_seconds=10, parser_workers=1,
            embedding_batch_max_chars=5000, chunks_queue_max=10,
            files_queue_max=10, pause_memory_percent=85, abort_memory_percent=95,
        )
        store = MagicMock()
        store.upsert_batch = MagicMock()
        store.delete_ids = MagicMock(return_value=0)
        store.get_existing_ids = MagicMock(return_value=set())

        def _noop_embed(texts):
            return [[0.1] * 1024 for _ in texts]

        from obsidian_rag.pipeline.governor import GovernorAction
        gov = MagicMock()
        gov.check = MagicMock(return_value=GovernorAction.CONTINUE)
        gov.wait_until_safe = MagicMock(return_value=GovernorAction.CONTINUE)
        gov.start = MagicMock()
        gov.stop = MagicMock()

        pc = PipelineConfig(max_workers=2, engine="local", dask_scheduler="")

        pipeline = IngestPipeline(
            manifest, perf, store,
            embed_fn=_noop_embed,
            governor=gov,
            pipeline_config=pc,
        )
        result = pipeline.run([])
        manifest.close()

        assert result.errors == []
