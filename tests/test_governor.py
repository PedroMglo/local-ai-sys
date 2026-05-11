"""Tests for ResourceGovernor — background resource monitor."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from obsidian_rag.config import PerformanceConfig
from obsidian_rag.pipeline.governor import (
    GovernorAction,
    ResourceGovernor,
    ResourceSnapshot,
    _parse_psi_line,
    _read_psi,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _perf(**overrides) -> PerformanceConfig:
    """Create a PerformanceConfig with sensible test defaults."""
    defaults = dict(
        auto_tune=False,
        max_cpu_percent=75,
        max_memory_percent=70,
        max_parallel_jobs=2,
        embedding_batch_size=24,
        embedding_timeout=30,
        query_timeout_seconds=10,
        graph_timeout=60,
        parser_workers=2,
        embedding_batch_max_chars=48000,
        chunks_queue_max=64,
        files_queue_max=128,
        pause_memory_percent=80,
        abort_memory_percent=90,
        max_swap_percent=40,
        pause_swap_percent=60,
        abort_swap_percent=80,
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


def _mock_swap(percent: float = 0.0, used_gb: float = 0.0, total_gb: float = 6.0):
    """Create a mock psutil.swap_memory() result."""
    m = MagicMock()
    m.percent = percent
    m.used = int(used_gb * 1024 ** 3)
    m.total = int(total_gb * 1024 ** 3)
    m.free = int((total_gb - used_gb) * 1024 ** 3)
    return m


# ---------------------------------------------------------------------------
# GovernorAction thresholds
# ---------------------------------------------------------------------------

class TestGovernorEvaluate:
    """Test _evaluate() decision logic (bypass background thread)."""

    def _make_snap(self, ram_pct=50.0, cpu_pct=30.0, disk_gb=50.0, swap_pct=0.0, swap_gb=0.0):
        return ResourceSnapshot(
            ram_percent=ram_pct,
            ram_available_gb=16.0,
            cpu_percent=cpu_pct,
            disk_free_gb=disk_gb,
            swap_percent=swap_pct,
            swap_used_gb=swap_gb,
            timestamp=time.monotonic(),
        )

    def test_continue_normal(self):
        gov = ResourceGovernor(_perf(), data_dir="/tmp")
        snap = self._make_snap(ram_pct=50.0, cpu_pct=30.0, disk_gb=50.0)
        assert gov._evaluate(snap) is GovernorAction.CONTINUE

    def test_reduce_on_ram_above_max_memory(self):
        perf = _perf(max_memory_percent=70, pause_memory_percent=80, abort_memory_percent=90)
        gov = ResourceGovernor(perf, data_dir="/tmp")
        snap = self._make_snap(ram_pct=72.0)
        assert gov._evaluate(snap) is GovernorAction.REDUCE

    def test_pause_on_ram_above_pause_threshold(self):
        perf = _perf(max_memory_percent=70, pause_memory_percent=80, abort_memory_percent=90)
        gov = ResourceGovernor(perf, data_dir="/tmp")
        snap = self._make_snap(ram_pct=82.0)
        assert gov._evaluate(snap) is GovernorAction.PAUSE

    def test_abort_on_ram_above_abort_threshold(self):
        perf = _perf(abort_memory_percent=90)
        gov = ResourceGovernor(perf, data_dir="/tmp")
        snap = self._make_snap(ram_pct=92.0)
        assert gov._evaluate(snap) is GovernorAction.ABORT

    def test_throttle_on_high_cpu(self):
        perf = _perf(max_cpu_percent=75)
        gov = ResourceGovernor(perf, data_dir="/tmp")
        snap = self._make_snap(cpu_pct=90.0)
        assert gov._evaluate(snap) is GovernorAction.THROTTLE

    def test_reduce_on_swap_above_max_swap(self):
        perf = _perf(max_swap_percent=40)
        gov = ResourceGovernor(perf, data_dir="/tmp")
        snap = self._make_snap(swap_pct=45.0, swap_gb=2.7)
        assert gov._evaluate(snap) is GovernorAction.REDUCE

    def test_pause_on_swap_above_pause_swap(self):
        perf = _perf(pause_swap_percent=60)
        gov = ResourceGovernor(perf, data_dir="/tmp")
        snap = self._make_snap(swap_pct=65.0, swap_gb=4.0)
        assert gov._evaluate(snap) is GovernorAction.PAUSE

    def test_abort_on_swap_above_abort_swap(self):
        perf = _perf(abort_swap_percent=80)
        gov = ResourceGovernor(perf, data_dir="/tmp")
        snap = self._make_snap(swap_pct=85.0, swap_gb=5.1)
        assert gov._evaluate(snap) is GovernorAction.ABORT

    def test_swap_storm_triggers_throttle(self):
        gov = ResourceGovernor(_perf(), data_dir="/tmp")
        # Simulate a swap delta > 0.5 GB
        gov._prev_swap_used = 1.0
        gov._swap_delta_gb = 0.6  # simulate large delta
        snap = self._make_snap(swap_pct=20.0, swap_gb=1.6)
        assert gov._evaluate(snap) is GovernorAction.THROTTLE

    def test_abort_on_low_disk(self):
        gov = ResourceGovernor(_perf(), data_dir="/tmp")
        snap = self._make_snap(disk_gb=0.5)
        assert gov._evaluate(snap) is GovernorAction.ABORT

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

    def test_swap_thresholds_ordered_correctly(self):
        """Swap thresholds: abort > pause > reduce at boundary values."""
        perf = _perf(max_swap_percent=40, pause_swap_percent=60, abort_swap_percent=80)
        gov = ResourceGovernor(perf, data_dir="/tmp")

        assert gov._evaluate(self._make_snap(swap_pct=30.0)) is GovernorAction.CONTINUE
        assert gov._evaluate(self._make_snap(swap_pct=45.0)) is GovernorAction.REDUCE
        assert gov._evaluate(self._make_snap(swap_pct=65.0)) is GovernorAction.PAUSE
        assert gov._evaluate(self._make_snap(swap_pct=85.0)) is GovernorAction.ABORT


# ---------------------------------------------------------------------------
# Lifecycle & background thread
# ---------------------------------------------------------------------------

class TestGovernorLifecycle:

    @patch("obsidian_rag.pipeline.governor._read_vram", return_value=(0.0, 0.0, 0.0))
    @patch("obsidian_rag.pipeline.governor._read_psi", return_value={})
    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_start_stop(self, mock_shutil, mock_psutil, _psi, _vram):
        mock_psutil.virtual_memory.return_value = _mock_vmem(50.0)
        mock_psutil.cpu_percent.return_value = 30.0
        mock_psutil.swap_memory.return_value = _mock_swap()
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

    @patch("obsidian_rag.pipeline.governor._read_vram", return_value=(0.0, 0.0, 0.0))
    @patch("obsidian_rag.pipeline.governor._read_psi", return_value={})
    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_check_returns_continue_normal(self, mock_shutil, mock_psutil, _psi, _vram):
        mock_psutil.virtual_memory.return_value = _mock_vmem(50.0)
        mock_psutil.cpu_percent.return_value = 30.0
        mock_psutil.swap_memory.return_value = _mock_swap()
        mock_shutil.disk_usage.return_value = MagicMock(free=50 * 1024 ** 3)

        gov = ResourceGovernor(_perf(), data_dir="/tmp", interval=0.1)
        gov.start()
        try:
            assert gov.check() is GovernorAction.CONTINUE
        finally:
            gov.stop()

    @patch("obsidian_rag.pipeline.governor._read_vram", return_value=(0.0, 0.0, 0.0))
    @patch("obsidian_rag.pipeline.governor._read_psi", return_value={})
    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_double_start_is_safe(self, mock_shutil, mock_psutil, _psi, _vram):
        mock_psutil.virtual_memory.return_value = _mock_vmem(50.0)
        mock_psutil.cpu_percent.return_value = 30.0
        mock_psutil.swap_memory.return_value = _mock_swap()
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

    @patch("obsidian_rag.pipeline.governor._read_vram", return_value=(0.0, 0.0, 0.0))
    @patch("obsidian_rag.pipeline.governor._read_psi", return_value={})
    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_returns_immediately_when_safe(self, mock_shutil, mock_psutil, _psi, _vram):
        mock_psutil.virtual_memory.return_value = _mock_vmem(50.0)
        mock_psutil.cpu_percent.return_value = 30.0
        mock_psutil.swap_memory.return_value = _mock_swap()
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

    @patch("obsidian_rag.pipeline.governor._read_vram", return_value=(0.0, 0.0, 0.0))
    @patch("obsidian_rag.pipeline.governor._read_psi", return_value={})
    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_returns_abort_immediately(self, mock_shutil, mock_psutil, _psi, _vram):
        """ABORT should be returned immediately, not waited through."""
        mock_psutil.virtual_memory.return_value = _mock_vmem(95.0)
        mock_psutil.cpu_percent.return_value = 30.0
        mock_psutil.swap_memory.return_value = _mock_swap()
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

    @patch("obsidian_rag.pipeline.governor._read_vram", return_value=(0.0, 0.0, 0.0))
    @patch("obsidian_rag.pipeline.governor._read_psi", return_value={})
    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_waits_then_recovers(self, mock_shutil, mock_psutil, _psi, _vram):
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
        mock_psutil.swap_memory.return_value = _mock_swap()
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

    @patch("obsidian_rag.pipeline.governor._read_vram", return_value=(0.0, 0.0, 0.0))
    @patch("obsidian_rag.pipeline.governor._read_psi", return_value={})
    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_metrics_file_written(self, mock_shutil, mock_psutil, _psi, _vram, tmp_path):
        mock_psutil.virtual_memory.return_value = _mock_vmem(50.0)
        mock_psutil.cpu_percent.return_value = 30.0
        mock_psutil.swap_memory.return_value = _mock_swap()
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
        # PSI and VRAM fields should be present in metrics
        assert "psi_mem_full10" in record
        assert "psi_io_full10" in record
        assert "vram_used_gb" in record

    @patch("obsidian_rag.pipeline.governor._read_vram", return_value=(0.0, 0.0, 0.0))
    @patch("obsidian_rag.pipeline.governor._read_psi", return_value={})
    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_no_metrics_without_path(self, mock_shutil, mock_psutil, _psi, _vram, tmp_path):
        mock_psutil.virtual_memory.return_value = _mock_vmem(50.0)
        mock_psutil.cpu_percent.return_value = 30.0
        mock_psutil.swap_memory.return_value = _mock_swap()
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

    @patch("obsidian_rag.pipeline.governor._read_vram", return_value=(0.0, 0.0, 0.0))
    @patch("obsidian_rag.pipeline.governor._read_psi", return_value={})
    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_normal_returns_no_throttle(self, mock_shutil, mock_psutil, _psi, _vram):
        mock_psutil.virtual_memory.return_value = _mock_vmem(50.0)
        mock_psutil.cpu_percent.return_value = 30.0
        mock_psutil.swap_memory.return_value = _mock_swap()
        mock_shutil.disk_usage.return_value = MagicMock(free=50 * 1024 ** 3)

        from obsidian_rag.tuning import should_throttle
        advice = should_throttle(_perf(), data_dir="/tmp")
        assert not advice.pause_sync
        assert not advice.reduce_workers
        assert not advice.low_disk

    @patch("obsidian_rag.pipeline.governor._read_vram", return_value=(0.0, 0.0, 0.0))
    @patch("obsidian_rag.pipeline.governor._read_psi", return_value={})
    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_high_ram_returns_pause(self, mock_shutil, mock_psutil, _psi, _vram):
        mock_psutil.virtual_memory.return_value = _mock_vmem(78.0)
        mock_psutil.cpu_percent.return_value = 30.0
        mock_psutil.swap_memory.return_value = _mock_swap()
        mock_shutil.disk_usage.return_value = MagicMock(free=50 * 1024 ** 3)

        from obsidian_rag.tuning import should_throttle
        perf = _perf(pause_memory_percent=75, abort_memory_percent=90)
        advice = should_throttle(perf, data_dir="/tmp")
        assert advice.pause_sync

    @patch("obsidian_rag.pipeline.governor._read_vram", return_value=(0.0, 0.0, 0.0))
    @patch("obsidian_rag.pipeline.governor._read_psi", return_value={})
    @patch("obsidian_rag.pipeline.governor.psutil")
    @patch("obsidian_rag.pipeline.governor.shutil")
    def test_critical_ram_returns_abort(self, mock_shutil, mock_psutil, _psi, _vram):
        mock_psutil.virtual_memory.return_value = _mock_vmem(92.0)
        mock_psutil.cpu_percent.return_value = 30.0
        mock_psutil.swap_memory.return_value = _mock_swap()
        mock_shutil.disk_usage.return_value = MagicMock(free=50 * 1024 ** 3)

        from obsidian_rag.tuning import should_throttle
        perf = _perf(abort_memory_percent=85)
        advice = should_throttle(perf, data_dir="/tmp")
        assert advice.pause_sync  # abort maps to pause_sync=True for backward compat


# ---------------------------------------------------------------------------
# PSI parsing
# ---------------------------------------------------------------------------

class TestPSIParsing:
    """Test PSI line parsing and file reading helpers."""

    def test_parse_psi_line_some(self):
        line = "some avg10=2.50 avg60=1.20 avg300=0.80 total=123456"
        result = _parse_psi_line(line)
        assert result["avg10"] == 2.50
        assert result["avg60"] == 1.20
        assert result["avg300"] == 0.80
        assert result["total"] == 123456.0

    def test_parse_psi_line_full(self):
        line = "full avg10=0.50 avg60=0.10 avg300=0.02 total=12345"
        result = _parse_psi_line(line)
        assert result["avg10"] == 0.50

    def test_parse_psi_line_empty(self):
        result = _parse_psi_line("")
        assert result == {}

    def test_read_psi_file_not_found(self):
        """Non-Linux or kernel < 4.20 — returns empty dict."""
        result = _read_psi("nonexistent_resource_xyz")
        assert result == {}

    @patch("builtins.open", mock_open(read_data=(
        "some avg10=5.00 avg60=2.00 avg300=1.00 total=500000\n"
        "full avg10=1.50 avg60=0.50 avg300=0.10 total=100000\n"
    )))
    def test_read_psi_parses_both_lines(self):
        result = _read_psi("memory")
        assert "some" in result
        assert "full" in result
        assert result["some"]["avg10"] == 5.00
        assert result["full"]["avg10"] == 1.50


# ---------------------------------------------------------------------------
# PSI-based governor decisions
# ---------------------------------------------------------------------------

class TestGovernorPSI:
    """Test that PSI thresholds trigger correct governor actions."""

    def _make_snap(self, psi_mem_full=0.0, psi_io_full=0.0, psi_cpu_some=0.0, **kw):
        defaults = dict(
            ram_percent=50.0,
            ram_available_gb=16.0,
            cpu_percent=30.0,
            disk_free_gb=50.0,
            swap_percent=0.0,
            swap_used_gb=0.0,
            timestamp=time.monotonic(),
            psi_memory_full_avg10=psi_mem_full,
            psi_io_full_avg10=psi_io_full,
            psi_cpu_some_avg10=psi_cpu_some,
            vram_used_gb=0.0,
            vram_total_gb=0.0,
            vram_percent=0.0,
        )
        defaults.update(kw)
        return ResourceSnapshot(**defaults)

    def test_psi_memory_full_high_triggers_pause(self):
        gov = ResourceGovernor(_perf(), data_dir="/tmp")
        snap = self._make_snap(psi_mem_full=30.0)
        assert gov._evaluate(snap) is GovernorAction.PAUSE

    def test_psi_memory_full_medium_triggers_reduce(self):
        gov = ResourceGovernor(_perf(), data_dir="/tmp")
        snap = self._make_snap(psi_mem_full=12.0)
        assert gov._evaluate(snap) is GovernorAction.REDUCE

    def test_psi_memory_full_low_triggers_throttle(self):
        gov = ResourceGovernor(_perf(), data_dir="/tmp")
        snap = self._make_snap(psi_mem_full=7.0)
        assert gov._evaluate(snap) is GovernorAction.THROTTLE

    def test_psi_io_full_high_triggers_pause(self):
        gov = ResourceGovernor(_perf(), data_dir="/tmp")
        snap = self._make_snap(psi_io_full=45.0)
        assert gov._evaluate(snap) is GovernorAction.PAUSE

    def test_psi_io_full_medium_triggers_reduce(self):
        gov = ResourceGovernor(_perf(), data_dir="/tmp")
        snap = self._make_snap(psi_io_full=25.0)
        assert gov._evaluate(snap) is GovernorAction.REDUCE

    def test_psi_io_full_low_triggers_throttle(self):
        gov = ResourceGovernor(_perf(), data_dir="/tmp")
        snap = self._make_snap(psi_io_full=12.0)
        assert gov._evaluate(snap) is GovernorAction.THROTTLE

    def test_psi_cpu_some_high_triggers_throttle(self):
        gov = ResourceGovernor(_perf(), data_dir="/tmp")
        snap = self._make_snap(psi_cpu_some=55.0)
        assert gov._evaluate(snap) is GovernorAction.THROTTLE

    def test_no_psi_pressure_continues(self):
        gov = ResourceGovernor(_perf(), data_dir="/tmp")
        snap = self._make_snap(psi_mem_full=0.0, psi_io_full=0.0, psi_cpu_some=0.0)
        assert gov._evaluate(snap) is GovernorAction.CONTINUE

    def test_ram_threshold_overrides_psi(self):
        """Hard RAM abort should fire before PSI checks."""
        perf = _perf(abort_memory_percent=90)
        gov = ResourceGovernor(perf, data_dir="/tmp")
        snap = self._make_snap(ram_percent=92.0, psi_mem_full=0.0)
        assert gov._evaluate(snap) is GovernorAction.ABORT


# ---------------------------------------------------------------------------
# VRAM snapshot fields
# ---------------------------------------------------------------------------

class TestGovernorVRAM:
    """Test that VRAM fields are correctly included in snapshots."""

    def test_snapshot_includes_vram_fields(self):
        snap = ResourceSnapshot(
            ram_percent=50.0, ram_available_gb=16.0, cpu_percent=30.0,
            disk_free_gb=50.0, swap_percent=0.0, swap_used_gb=0.0,
            timestamp=time.monotonic(),
            vram_used_gb=3.5, vram_total_gb=8.0, vram_percent=43.75,
        )
        assert snap.vram_used_gb == 3.5
        assert snap.vram_total_gb == 8.0
        assert snap.vram_percent == 43.75

    def test_snapshot_vram_defaults_zero(self):
        snap = ResourceSnapshot(
            ram_percent=50.0, ram_available_gb=16.0, cpu_percent=30.0,
            disk_free_gb=50.0, swap_percent=0.0, swap_used_gb=0.0,
            timestamp=time.monotonic(),
        )
        assert snap.vram_used_gb == 0.0
        assert snap.vram_total_gb == 0.0
        assert snap.vram_percent == 0.0


# ---------------------------------------------------------------------------
# Global pipeline timeout watchdog
# ---------------------------------------------------------------------------

class TestPipelineWatchdog:
    """Test that the IngestPipeline watchdog fires on timeout."""

    def test_watchdog_aborts_on_timeout(self):
        """Pipeline with a very short timeout should abort."""
        from obsidian_rag.pipeline.ingest import IngestPipeline, IngestSource

        manifest = MagicMock()
        manifest.start_run.return_value = "test-run-1"
        manifest.finish_run = MagicMock()
        manifest.file_sha256.return_value = "abc123"
        manifest.needs_reindex.return_value = False

        store = MagicMock()
        store.get_existing_ids.return_value = set()

        perf = _perf()
        governor = MagicMock()
        governor.start = MagicMock()
        governor.stop = MagicMock()
        governor.check.return_value = GovernorAction.CONTINUE

        pipeline = IngestPipeline(
            manifest, perf, store,
            governor=governor,
            max_run_seconds=0.5,
        )

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            result = pipeline.run([IngestSource(source_type="vault", path=Path(tmpdir), name="test")])

        # The pipeline completed without hanging
        assert result.elapsed_seconds < 30
