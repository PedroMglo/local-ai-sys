"""Tests for performance auto-tuning, throttling, and retrocompatibility."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# PerformanceConfig defaults & parsing
# ---------------------------------------------------------------------------


class TestPerformanceConfigDefaults:
    """PerformanceConfig with no [performance] section → safe defaults."""

    def test_defaults_without_section(self, tmp_path):
        """rag.toml without [performance] loads with defaults."""
        toml_content = b"""
[paths]
source_dir = "source"
data_dir = "data/chroma"
vault_dir = "/tmp/vault"

[ollama]
base_url = "http://localhost:11434"
embedding_model = "bge-m3"
"""
        toml_file = tmp_path / "rag.toml"
        toml_file.write_bytes(toml_content)

        with (
            patch("obsidian_rag.config.PROJECT_ROOT", tmp_path),
            patch("obsidian_rag.config._find_project_root", return_value=tmp_path),
            patch("obsidian_rag.tuning.detect_resources") as mock_detect,
        ):
            # Mock detect_resources to avoid real system calls
            mock_detect.return_value = MagicMock(
                ram_total_gb=32.0, ram_available_gb=20.0, ram_percent=37.0,
                cpu_cores=24, cpu_percent=10.0, disk_free_gb=100.0, gpu_nvidia=True,
                gpu_vram_total_gb=8.0, gpu_vram_free_gb=6.5,
            )

            from obsidian_rag.config import load_settings
            s = load_settings()

            assert s.performance.auto_tune is True
            assert s.performance.max_cpu_percent == 75
            assert s.performance.max_memory_percent == 70
            assert s.performance.query_timeout_seconds == 30

    def test_explicit_values_parsed(self, tmp_path):
        """rag.toml with [performance] section uses those values."""
        toml_content = b"""
[paths]
source_dir = "source"
data_dir = "data/chroma"
vault_dir = "/tmp/vault"

[ollama]
base_url = "http://localhost:11434"
embedding_model = "bge-m3"

[performance]
auto_tune = false
max_cpu_percent = 90
max_memory_percent = 85
max_parallel_jobs = 8
embedding_batch_size = 200
query_timeout_seconds = 60
"""
        toml_file = tmp_path / "rag.toml"
        toml_file.write_bytes(toml_content)

        with (
            patch("obsidian_rag.config.PROJECT_ROOT", tmp_path),
            patch("obsidian_rag.config._find_project_root", return_value=tmp_path),
        ):
            from obsidian_rag.config import load_settings
            s = load_settings()

            # auto_tune=false → values used as-is
            assert s.performance.auto_tune is False
            assert s.performance.max_cpu_percent == 90
            assert s.performance.max_memory_percent == 85
            assert s.performance.max_parallel_jobs == 8
            assert s.performance.embedding_batch_size == 200
            assert s.performance.query_timeout_seconds == 60


# ---------------------------------------------------------------------------
# Auto-tune logic
# ---------------------------------------------------------------------------


class TestAutoTune:
    """Tests for the auto_tune() function in tuning.py."""

    def test_high_ram_machine(self):
        """32GB RAM, 24 cores → conservative batch and workers."""
        from obsidian_rag.config import PerformanceConfig
        from obsidian_rag.tuning import auto_tune

        perf = PerformanceConfig(
            auto_tune=True, max_cpu_percent=75, max_memory_percent=80,
            max_parallel_jobs=4, embedding_batch_size=50, embedding_timeout=120, query_timeout_seconds=30,
        )

        with patch("obsidian_rag.tuning.detect_resources") as mock:
            mock.return_value = MagicMock(
                ram_total_gb=32.0, ram_available_gb=20.0, ram_percent=37.0,
                cpu_cores=24, cpu_percent=10.0, disk_free_gb=100.0, gpu_nvidia=True,
                gpu_vram_total_gb=8.0, gpu_vram_free_gb=6.5,
            )
            result = auto_tune(perf)

        assert result.embedding_batch_size == 50   # ≥6GB VRAM → GPU boost to 50
        assert result.max_parallel_jobs == 4       # 24 // 6 = 4

    def test_low_ram_machine(self):
        """4GB RAM → small batch, fewer workers."""
        from obsidian_rag.config import PerformanceConfig
        from obsidian_rag.tuning import auto_tune

        perf = PerformanceConfig(
            auto_tune=True, max_cpu_percent=75, max_memory_percent=80,
            max_parallel_jobs=4, embedding_batch_size=50, embedding_timeout=120, query_timeout_seconds=30,
        )

        with patch("obsidian_rag.tuning.detect_resources") as mock:
            mock.return_value = MagicMock(
                ram_total_gb=4.0, ram_available_gb=1.5, ram_percent=62.0,
                cpu_cores=4, cpu_percent=30.0, disk_free_gb=20.0, gpu_nvidia=False,
                gpu_vram_total_gb=0.0, gpu_vram_free_gb=0.0,
            )
            result = auto_tune(perf)

        assert result.embedding_batch_size <= 15   # <8GB → 15, then halved for <4GB avail
        assert result.max_parallel_jobs == 1       # 4 // 6 = 0, capped to 1

    def test_detection_failure_returns_original(self):
        """If psutil fails, auto_tune returns the original config."""
        from obsidian_rag.config import PerformanceConfig
        from obsidian_rag.tuning import auto_tune

        perf = PerformanceConfig(
            auto_tune=True, max_cpu_percent=75, max_memory_percent=80,
            max_parallel_jobs=4, embedding_batch_size=50, embedding_timeout=120, query_timeout_seconds=30,
        )

        with patch("obsidian_rag.tuning.detect_resources", side_effect=RuntimeError("fail")):
            result = auto_tune(perf)

        assert result is perf  # unchanged


# ---------------------------------------------------------------------------
# Throttle advisory
# ---------------------------------------------------------------------------


class TestShouldThrottle:
    """Tests for should_throttle() in tuning.py (now delegates to ResourceGovernor)."""

    def _mock_vmem(self, percent=50.0, available_gb=16.0, total_gb=32.0):
        m = MagicMock()
        m.percent = percent
        m.available = int(available_gb * 1024 ** 3)
        m.total = int(total_gb * 1024 ** 3)
        return m

    def test_normal_conditions_no_throttle(self):
        """Under normal conditions, no throttling."""
        from obsidian_rag.config import PerformanceConfig
        from obsidian_rag.tuning import should_throttle

        perf = PerformanceConfig(
            auto_tune=True, max_cpu_percent=75, max_memory_percent=80,
            max_parallel_jobs=4, embedding_batch_size=50, embedding_timeout=120, query_timeout_seconds=30,
        )

        with patch("obsidian_rag.pipeline.governor.psutil") as mock_psutil, \
             patch("obsidian_rag.pipeline.governor.shutil") as mock_shutil:
            mock_psutil.virtual_memory.return_value = self._mock_vmem(37.0, 20.0)
            mock_psutil.cpu_percent.return_value = 30.0
            mock_psutil.swap_memory.return_value = MagicMock(percent=0.0, used=0, total=6*1024**3, free=6*1024**3)
            mock_shutil.disk_usage.return_value = MagicMock(free=100 * 1024 ** 3)
            advice = should_throttle(perf, data_dir="/tmp")

        assert not advice.pause_sync
        assert not advice.reduce_workers
        assert not advice.low_disk

    def test_high_ram_triggers_pause(self):
        """RAM above pause_memory_percent triggers pause."""
        from obsidian_rag.config import PerformanceConfig
        from obsidian_rag.tuning import should_throttle

        perf = PerformanceConfig(
            auto_tune=True, max_cpu_percent=75, max_memory_percent=80,
            max_parallel_jobs=4, embedding_batch_size=50, embedding_timeout=120, query_timeout_seconds=30,
            pause_memory_percent=75, abort_memory_percent=90,
        )

        with patch("obsidian_rag.pipeline.governor.psutil") as mock_psutil, \
             patch("obsidian_rag.pipeline.governor.shutil") as mock_shutil:
            mock_psutil.virtual_memory.return_value = self._mock_vmem(78.0, 2.0)
            mock_psutil.cpu_percent.return_value = 30.0
            mock_psutil.swap_memory.return_value = MagicMock(percent=0.0, used=0, total=6*1024**3, free=6*1024**3)
            mock_shutil.disk_usage.return_value = MagicMock(free=50 * 1024 ** 3)
            advice = should_throttle(perf, data_dir="/tmp")

        assert advice.pause_sync is True
        assert "RAM" in advice.reason

    def test_moderate_ram_triggers_reduce(self):
        """RAM above max_memory_percent but below pause triggers reduce_workers."""
        from obsidian_rag.config import PerformanceConfig
        from obsidian_rag.tuning import should_throttle

        perf = PerformanceConfig(
            auto_tune=True, max_cpu_percent=75, max_memory_percent=70,
            max_parallel_jobs=4, embedding_batch_size=50, embedding_timeout=120, query_timeout_seconds=30,
            pause_memory_percent=80, abort_memory_percent=90,
        )

        with patch("obsidian_rag.pipeline.governor.psutil") as mock_psutil, \
             patch("obsidian_rag.pipeline.governor.shutil") as mock_shutil:
            mock_psutil.virtual_memory.return_value = self._mock_vmem(72.0, 5.0)
            mock_psutil.cpu_percent.return_value = 30.0
            mock_psutil.swap_memory.return_value = MagicMock(percent=0.0, used=0, total=6*1024**3, free=6*1024**3)
            mock_shutil.disk_usage.return_value = MagicMock(free=50 * 1024 ** 3)
            advice = should_throttle(perf, data_dir="/tmp")

        assert advice.reduce_workers is True
        assert not advice.pause_sync

    def test_low_disk_triggers_flag(self):
        """Disk < 1GB triggers abort (mapped to low_disk + pause_sync)."""
        from obsidian_rag.config import PerformanceConfig
        from obsidian_rag.tuning import should_throttle

        perf = PerformanceConfig(
            auto_tune=True, max_cpu_percent=75, max_memory_percent=80,
            max_parallel_jobs=4, embedding_batch_size=50, embedding_timeout=120, query_timeout_seconds=30,
        )

        with patch("obsidian_rag.pipeline.governor.psutil") as mock_psutil, \
             patch("obsidian_rag.pipeline.governor.shutil") as mock_shutil:
            mock_psutil.virtual_memory.return_value = self._mock_vmem(37.0, 20.0)
            mock_psutil.cpu_percent.return_value = 30.0
            mock_psutil.swap_memory.return_value = MagicMock(percent=0.0, used=0, total=6*1024**3, free=6*1024**3)
            mock_shutil.disk_usage.return_value = MagicMock(free=int(0.5 * 1024 ** 3))
            advice = should_throttle(perf, data_dir="/tmp")

        assert advice.low_disk is True


# ---------------------------------------------------------------------------
# Workers capping
# ---------------------------------------------------------------------------


class TestWorkersCapping:
    """Auto-tune caps pipeline.max_workers via performance.max_parallel_jobs."""

    def test_workers_capped_by_auto_tune(self, tmp_path):
        """pipeline.max_workers=8 capped by auto_tune to cpu_cores//4."""
        toml_content = b"""
[paths]
source_dir = "source"
data_dir = "data/chroma"
vault_dir = "/tmp/vault"

[ollama]
base_url = "http://localhost:11434"
embedding_model = "bge-m3"

[pipeline]
max_workers = 8

[performance]
auto_tune = true
"""
        toml_file = tmp_path / "rag.toml"
        toml_file.write_bytes(toml_content)

        with (
            patch("obsidian_rag.config.PROJECT_ROOT", tmp_path),
            patch("obsidian_rag.config._find_project_root", return_value=tmp_path),
            patch("obsidian_rag.tuning.detect_resources") as mock,
        ):
            mock.return_value = MagicMock(
                ram_total_gb=16.0, ram_available_gb=8.0, ram_percent=50.0,
                cpu_cores=4, cpu_percent=20.0, disk_free_gb=50.0, gpu_nvidia=False,
                gpu_vram_total_gb=0.0, gpu_vram_free_gb=0.0,
            )

            from obsidian_rag.config import load_settings
            s = load_settings()

        # auto_tune: 4 cores // 4 = 1 → caps pipeline.max_workers from 8 to 1
        assert s.pipeline.max_workers == 1
