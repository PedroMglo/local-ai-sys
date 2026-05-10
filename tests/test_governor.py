"""Tests for ResourceGovernor — background resource monitor."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from obsidian_rag.config import PerformanceConfig
from obsidian_rag.pipeline.governor import (
    GovernorAction,
    ResourceGovernor,
    ResourceSnapshot,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _perf(**overrides) -> PerformanceConfig:
    """Create a PerformanceConfig with sensible test defaults."""
    defaults = dict(
        auto_tune=False,
        max_cpu_percent=75,
        max_memory_percent=80,
        max_parallel_jobs=2,
        embedding_batch_size=24,
        embedding_timeout=30,
        query_timeout_seconds=10,
        graph_timeout=60,
        parser_workers=2,
        embedding_batch_max_chars=48000,
        chunks_queue_max=64,
        files_queue_max=128,
        pause_memory_percent=75,
        abort_memory_percent=85,
    )
    defaults.update(overrides)
    return PerformanceConfig(**defaults)


def _mock_vmem(percent: float = 50.0, available_gb: float = 16.0, total_gb: float = 32.0):
    """Create a mock psutil.virtual_memory() result."""
    m = MagicMock()
    m.percent = percent
    m.available = int(available_gb * 1024 ** 3)
    m.total = int(total_gb * 1024 ** 3)
    return m


# ---------------------------------------------------------------------------
# GovernorAction thresholds
# ---------------------------------------------------------------------------

class TestGovernorEvaluate:
    """Test _evaluate() decision logic (bypass background thread)."""

    def _make_snap(self, ram_pct=50.0, cpu_pct=30.0, disk_gb=50.0):
        return ResourceSnapshot(
            ram_percent=ram_pct,
            ram_available_gb=16.0,
            cpu_percent=cpu_pct,
            disk_free_gb=disk_gb,
            timestamp=time.monotonic(),
        )

    def test_continue_normal(self):
        gov = ResourceGovernor(_perf(), data_dir="/tmp")
        snap = self._make_snap(ram_pct=50.0, cpu_pct=30.0, disk_gb=50.0)
        assert gov._evaluate(snap) is GovernorAction.CONTINUE

    def test_reduce_on_ram_above_max_memory(self):
        perf = _perf(max_memory_percent=80, pause_memory_percent=85, abort_memory_percent=90)
        gov = ResourceGovernor(perf, data_dir="/tmp")
        snap = self._make_snap(ram_pct=82.0)
        assert gov._evaluate(snap) is GovernorAction.REDUCE

    def test_pause_on_ram_above_pause_threshold(self):
        perf = _perf(max_memory_percent=70, pause_memory_percent=75, abort_memory_percent=85)
        gov = ResourceGovernor(perf, data_dir="/tmp")
        snap = self._make_snap(ram_pct=78.0)
        assert gov._evaluate(snap) is GovernorAction.PAUSE

    def test_abort_on_ram_above_abort_threshold(self):
        perf = _perf(abort_memory_percent=85)
        gov = ResourceGovernor(perf, data_dir="/tmp")
        snap = self._make_snap(ram_pct=90.0)
        assert gov._evaluate(snap) is GovernorAction.ABORT

    def test_abort_on_low_disk(self):
        gov = ResourceGovernor(_perf(), data_dir="/tmp")
        snap = self._make_snap(disk_gb=0.5)
        assert gov._evaluate(snap) is GovernorAction.ABORT

    def test_reduce_on_high_cpu(self):
        perf = _perf(max_cpu_percent=75)
        gov = ResourceGovernor(perf, data_dir="/tmp")
        snap = self._make_snap(cpu_pct=90.0)
        assert gov._evaluate(snap) is GovernorAction.REDUCE

    def test_disk_abort_overrides_normal_ram(self):
        """Disk-full should abort even if RAM is fine."""
        gov = ResourceGovernor(_perf(), data_dir="/tmp")
        snap = self._make_snap(ram_pct=30.0, disk_gb=0.3)
        assert gov._evaluate(snap) is GovernorAction.ABORT

    def test_no_data_dir_skips_disk_check(self):
        """Without data_dir, disk check is skipped."""
        gov = ResourceGovernor(_perf(), data_dir=None)
        snap = self._make_snap(ram_pct=30.0, disk_gb=0.3)
        # No data_dir → disk check skipped → CONTINUE
        assert gov._evaluate(snap) is GovernorAction.CONTINUE

    def test_thresholds_ordered_correctly(self):
        """abort > pause > reduce > continue at boundary values."""
        perf = _perf(max_memory_percent=70, pause_memory_percent=80, abort_memory_percent=90)
        gov = ResourceGovernor(perf, data_dir="/tmp")

        assert gov._evaluate(self._make_snap(ram_pct=65.0)) is GovernorAction.CONTINUE
        assert gov._evaluate(self._make_snap(ram_pct=72.0)) is GovernorAction.REDUCE
        assert gov._evaluate(self._make_snap(ram_pct=82.0)) is GovernorAction.PAUSE
        assert gov._evaluate(self._make_snap(ram_pct=92.0)) is GovernorAction.ABORT


# ---------------------------------------------------------------------------
# Lifecycle & background thread
# ---------------------------------------------------------------------------

class TestGovernorLifecycle:

    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_start_stop(self, mock_shutil, mock_psutil):
        mock_psutil.virtual_memory.return_value = _mock_vmem(50.0)
        mock_psutil.cpu_percent.return_value = 30.0
        mock_shutil.disk_usage.return_value = MagicMock(free=50 * 1024 ** 3)

        gov = ResourceGovernor(_perf(), data_dir="/tmp", interval=0.1)
        gov.start()
        assert gov._thread is not None
        assert gov._thread.is_alive()

        # Should have initial snapshot
        snap = gov.snapshot()
        assert snap is not None
        assert snap.ram_percent == 50.0

        gov.stop()
        assert gov._thread is None

    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_check_returns_continue_normal(self, mock_shutil, mock_psutil):
        mock_psutil.virtual_memory.return_value = _mock_vmem(50.0)
        mock_psutil.cpu_percent.return_value = 30.0
        mock_shutil.disk_usage.return_value = MagicMock(free=50 * 1024 ** 3)

        gov = ResourceGovernor(_perf(), data_dir="/tmp", interval=0.1)
        gov.start()
        try:
            assert gov.check() is GovernorAction.CONTINUE
        finally:
            gov.stop()

    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_double_start_is_safe(self, mock_shutil, mock_psutil):
        mock_psutil.virtual_memory.return_value = _mock_vmem(50.0)
        mock_psutil.cpu_percent.return_value = 30.0
        mock_shutil.disk_usage.return_value = MagicMock(free=50 * 1024 ** 3)

        gov = ResourceGovernor(_perf(), data_dir="/tmp", interval=0.1)
        gov.start()
        thread_id = gov._thread.ident
        gov.start()  # should be no-op
        assert gov._thread.ident == thread_id
        gov.stop()

    def test_check_before_start_returns_continue(self):
        """check() before start() should not crash."""
        gov = ResourceGovernor(_perf())
        assert gov.check() is GovernorAction.CONTINUE


# ---------------------------------------------------------------------------
# wait_until_safe
# ---------------------------------------------------------------------------

class TestWaitUntilSafe:

    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_returns_immediately_when_safe(self, mock_shutil, mock_psutil):
        mock_psutil.virtual_memory.return_value = _mock_vmem(50.0)
        mock_psutil.cpu_percent.return_value = 30.0
        mock_shutil.disk_usage.return_value = MagicMock(free=50 * 1024 ** 3)

        gov = ResourceGovernor(_perf(), data_dir="/tmp", interval=0.1)
        gov.start()
        try:
            t0 = time.monotonic()
            result = gov.wait_until_safe(timeout=5)
            elapsed = time.monotonic() - t0
            assert result is GovernorAction.CONTINUE
            assert elapsed < 1.0  # should return nearly instantly
        finally:
            gov.stop()

    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_returns_abort_immediately(self, mock_shutil, mock_psutil):
        """ABORT should be returned immediately, not waited through."""
        mock_psutil.virtual_memory.return_value = _mock_vmem(95.0)
        mock_psutil.cpu_percent.return_value = 30.0
        mock_shutil.disk_usage.return_value = MagicMock(free=50 * 1024 ** 3)

        perf = _perf(abort_memory_percent=85)
        gov = ResourceGovernor(perf, data_dir="/tmp", interval=0.1)
        gov.start()
        try:
            t0 = time.monotonic()
            result = gov.wait_until_safe(timeout=5)
            elapsed = time.monotonic() - t0
            assert result is GovernorAction.ABORT
            assert elapsed < 1.0
        finally:
            gov.stop()

    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_waits_then_recovers(self, mock_shutil, mock_psutil):
        """Simulate pressure that clears after a short wait."""
        call_count = 0
        def changing_vmem():
            nonlocal call_count
            call_count += 1
            # First 3 calls: high pressure; then normal
            if call_count <= 3:
                return _mock_vmem(78.0)
            return _mock_vmem(50.0)

        mock_psutil.virtual_memory = changing_vmem
        mock_psutil.cpu_percent.return_value = 30.0
        mock_shutil.disk_usage.return_value = MagicMock(free=50 * 1024 ** 3)

        perf = _perf(pause_memory_percent=75)
        gov = ResourceGovernor(perf, data_dir="/tmp", interval=0.1)
        gov.start()
        try:
            result = gov.wait_until_safe(timeout=5)
            assert result in (GovernorAction.CONTINUE, GovernorAction.REDUCE)
        finally:
            gov.stop()


# ---------------------------------------------------------------------------
# JSONL metrics
# ---------------------------------------------------------------------------

class TestMetrics:

    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_metrics_file_written(self, mock_shutil, mock_psutil, tmp_path):
        mock_psutil.virtual_memory.return_value = _mock_vmem(50.0)
        mock_psutil.cpu_percent.return_value = 30.0
        mock_shutil.disk_usage.return_value = MagicMock(free=50 * 1024 ** 3)

        metrics_file = tmp_path / "metrics.jsonl"
        gov = ResourceGovernor(
            _perf(), data_dir="/tmp", interval=0.1, metrics_path=metrics_file,
        )
        gov.start()
        time.sleep(0.3)  # let a few samples run
        gov.stop()

        assert metrics_file.exists()
        lines = metrics_file.read_text().strip().splitlines()
        assert len(lines) >= 1

        record = json.loads(lines[0])
        assert "ts" in record
        assert "ram_pct" in record
        assert "cpu_pct" in record
        assert "disk_free_gb" in record
        assert "action" in record
        assert record["action"] == "CONTINUE"

    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_no_metrics_without_path(self, mock_shutil, mock_psutil, tmp_path):
        mock_psutil.virtual_memory.return_value = _mock_vmem(50.0)
        mock_psutil.cpu_percent.return_value = 30.0
        mock_shutil.disk_usage.return_value = MagicMock(free=50 * 1024 ** 3)

        gov = ResourceGovernor(_perf(), data_dir="/tmp", interval=0.1)
        gov.start()
        time.sleep(0.2)
        gov.stop()
        # No crash, no file — just works
        assert gov._metrics_fh is None


# ---------------------------------------------------------------------------
# Integration with tuning.should_throttle
# ---------------------------------------------------------------------------

class TestTuningIntegration:
    """Verify that tuning.should_throttle() delegates to the governor."""

    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_normal_returns_no_throttle(self, mock_shutil, mock_psutil):
        mock_psutil.virtual_memory.return_value = _mock_vmem(50.0)
        mock_psutil.cpu_percent.return_value = 30.0
        mock_shutil.disk_usage.return_value = MagicMock(free=50 * 1024 ** 3)

        from obsidian_rag.tuning import should_throttle
        advice = should_throttle(_perf(), data_dir="/tmp")
        assert not advice.pause_sync
        assert not advice.reduce_workers
        assert not advice.low_disk

    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_high_ram_returns_pause(self, mock_shutil, mock_psutil):
        mock_psutil.virtual_memory.return_value = _mock_vmem(78.0)
        mock_psutil.cpu_percent.return_value = 30.0
        mock_shutil.disk_usage.return_value = MagicMock(free=50 * 1024 ** 3)

        from obsidian_rag.tuning import should_throttle
        perf = _perf(pause_memory_percent=75, abort_memory_percent=90)
        advice = should_throttle(perf, data_dir="/tmp")
        assert advice.pause_sync

    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_critical_ram_returns_abort(self, mock_shutil, mock_psutil):
        mock_psutil.virtual_memory.return_value = _mock_vmem(92.0)
        mock_psutil.cpu_percent.return_value = 30.0
        mock_shutil.disk_usage.return_value = MagicMock(free=50 * 1024 ** 3)

        from obsidian_rag.tuning import should_throttle
        perf = _perf(abort_memory_percent=85)
        advice = should_throttle(perf, data_dir="/tmp")
        assert advice.pause_sync  # abort maps to pause_sync=True for backward compat
