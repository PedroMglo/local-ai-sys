"""Tests for new medium-priority features: backup, observe, sync parallelism."""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from obsidian_rag.pipeline.backup import backup_store, MAX_BACKUPS
from obsidian_rag.retrieval.observe import _JsonFormatter


class TestBackupChroma:
    def test_creates_backup(self, tmp_path: Path):
        chroma_dir = tmp_path / "chroma"
        chroma_dir.mkdir()
        (chroma_dir / "test.db").write_text("data")
        dest = tmp_path / "backups"

        with patch("obsidian_rag.pipeline.backup.settings") as mock_settings:
            mock_settings.paths.data_dir = chroma_dir
            result = backup_store(dest)

        assert result.exists()
        assert (result / "test.db").read_text() == "data"

    def test_rotates_old_backups(self, tmp_path: Path):
        chroma_dir = tmp_path / "chroma"
        chroma_dir.mkdir()
        (chroma_dir / "test.db").write_text("data")
        dest = tmp_path / "backups"
        dest.mkdir()

        # Create MAX_BACKUPS + 1 existing backups
        for i in range(MAX_BACKUPS + 1):
            (dest / f"store_backup_2024010{i}_000000").mkdir()

        with patch("obsidian_rag.pipeline.backup.settings") as mock_settings:
            mock_settings.paths.data_dir = chroma_dir
            backup_store(dest)

        backups = list(dest.glob("store_backup_*"))
        assert len(backups) <= MAX_BACKUPS

    def test_raises_on_missing_dir(self, tmp_path: Path):
        with patch("obsidian_rag.pipeline.backup.settings") as mock_settings:
            mock_settings.paths.data_dir = tmp_path / "nonexistent"
            with pytest.raises(FileNotFoundError):
                backup_store()


class TestJsonFormatter:
    def test_formats_as_json(self):
        fmt = _JsonFormatter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="hello %s", args=("world",), exc_info=None,
        )
        output = fmt.format(record)
        parsed = json.loads(output)
        assert parsed["msg"] == "hello world"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test"
        assert "ts" in parsed


class TestPipelineConfig:
    def test_max_workers_loaded(self):
        from obsidian_rag.config import settings
        assert hasattr(settings, "pipeline")
        assert settings.pipeline.max_workers >= 1

    def test_log_format_loaded(self):
        from obsidian_rag.config import settings
        assert settings.debug.log_format in ("text", "json")
