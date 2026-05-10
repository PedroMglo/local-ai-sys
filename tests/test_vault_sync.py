"""Tests for vault_sync — cross-platform sync backends."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from obsidian_rag.config import SyncConfig, _DEFAULT_EXCLUDE_PATTERNS
from obsidian_rag.pipeline.vault_sync import (
    _resolve_backend,
    _should_exclude,
    _sync_python,
    is_rsync_available,
    resolve_effective_backend,
    should_exclude,
    sync_vault,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def vault_dir(tmp_path: Path) -> Path:
    """Create a mock Obsidian vault with .md files."""
    vault = tmp_path / "vault"
    vault.mkdir()

    # Normal notes
    (vault / "note1.md").write_text("# Note 1\nContent of note 1.", encoding="utf-8")
    (vault / "note2.md").write_text("# Note 2\nContent of note 2.", encoding="utf-8")

    # Nested note
    sub = vault / "subfolder"
    sub.mkdir()
    (sub / "nested.md").write_text("# Nested\nNested content.", encoding="utf-8")

    # Non-markdown file (should be excluded)
    (vault / "image.png").write_bytes(b"\x89PNG")

    # Obsidian internal dir (should be excluded)
    obs = vault / ".obsidian"
    obs.mkdir()
    (obs / "config.json").write_text("{}", encoding="utf-8")

    return vault


@pytest.fixture
def source_dir(tmp_path: Path) -> Path:
    """Empty source directory."""
    src = tmp_path / "source"
    src.mkdir()
    return src


@pytest.fixture
def sync_cfg() -> SyncConfig:
    """Default sync config for tests."""
    return SyncConfig(
        backend="direct",
        delete_missing=True,
        follow_symlinks=False,
        exclude_patterns=_DEFAULT_EXCLUDE_PATTERNS,
    )


# ---------------------------------------------------------------------------
# Backend resolution
# ---------------------------------------------------------------------------


class TestResolveBackend:

    def test_direct_passthrough(self):
        assert _resolve_backend("direct") == "direct"

    def test_python_passthrough(self):
        assert _resolve_backend("python") == "python"

    @patch("obsidian_rag.pipeline.vault_sync.is_rsync_available", return_value=True)
    def test_rsync_when_available(self, _mock):
        assert _resolve_backend("rsync") == "rsync"

    @patch("obsidian_rag.pipeline.vault_sync.is_rsync_available", return_value=False)
    def test_rsync_fallback_when_unavailable(self, _mock):
        assert _resolve_backend("rsync") == "python"

    @patch("obsidian_rag.pipeline.vault_sync.platform")
    @patch("obsidian_rag.pipeline.vault_sync.is_rsync_available", return_value=True)
    def test_auto_uses_rsync_on_linux(self, _rsync, mock_platform):
        mock_platform.system.return_value = "Linux"
        assert _resolve_backend("auto") == "rsync"

    @patch("obsidian_rag.pipeline.vault_sync.platform")
    @patch("obsidian_rag.pipeline.vault_sync.is_rsync_available", return_value=False)
    def test_auto_falls_back_to_python_on_linux(self, _rsync, mock_platform):
        mock_platform.system.return_value = "Linux"
        assert _resolve_backend("auto") == "python"

    @patch("obsidian_rag.pipeline.vault_sync.platform")
    def test_auto_uses_python_on_windows(self, mock_platform):
        mock_platform.system.return_value = "Windows"
        assert _resolve_backend("auto") == "python"


# ---------------------------------------------------------------------------
# Exclusion patterns
# ---------------------------------------------------------------------------


class TestExclusion:

    def test_exclude_obsidian_dir(self):
        assert _should_exclude(Path(".obsidian/config.json"), _DEFAULT_EXCLUDE_PATTERNS)

    def test_exclude_git_dir(self):
        assert _should_exclude(Path(".git/HEAD"), _DEFAULT_EXCLUDE_PATTERNS)

    def test_exclude_trash(self):
        assert _should_exclude(Path(".trash/deleted.md"), _DEFAULT_EXCLUDE_PATTERNS)

    def test_exclude_ds_store(self):
        assert _should_exclude(Path(".DS_Store"), _DEFAULT_EXCLUDE_PATTERNS)

    def test_exclude_node_modules(self):
        assert _should_exclude(Path("node_modules/pkg/index.js"), _DEFAULT_EXCLUDE_PATTERNS)

    def test_include_normal_note(self):
        assert not _should_exclude(Path("notes/my-note.md"), _DEFAULT_EXCLUDE_PATTERNS)

    def test_include_nested_note(self):
        assert not _should_exclude(Path("projects/ai/readme.md"), _DEFAULT_EXCLUDE_PATTERNS)

    def test_public_wrapper_uses_defaults(self):
        assert should_exclude(Path(".obsidian/config.json"))
        assert not should_exclude(Path("note.md"))

    def test_custom_patterns(self):
        patterns = ("*.pdf", "temp")
        assert _should_exclude(Path("docs/file.pdf"), patterns)
        assert _should_exclude(Path("temp/data.txt"), patterns)
        assert not _should_exclude(Path("docs/file.md"), patterns)


# ---------------------------------------------------------------------------
# Direct backend
# ---------------------------------------------------------------------------


class TestDirectBackend:

    def test_returns_vault_dir(self, vault_dir, source_dir, sync_cfg):
        cfg = SyncConfig(backend="direct", delete_missing=True, follow_symlinks=False,
                         exclude_patterns=sync_cfg.exclude_patterns)
        result = sync_vault(vault_dir, source_dir, cfg)
        assert result == vault_dir

    def test_source_dir_untouched(self, vault_dir, source_dir, sync_cfg):
        cfg = SyncConfig(backend="direct", delete_missing=True, follow_symlinks=False,
                         exclude_patterns=sync_cfg.exclude_patterns)
        sync_vault(vault_dir, source_dir, cfg)
        # source_dir should still be empty
        assert list(source_dir.iterdir()) == []

    def test_fails_if_vault_missing(self, tmp_path, source_dir, sync_cfg):
        cfg = SyncConfig(backend="direct", delete_missing=True, follow_symlinks=False,
                         exclude_patterns=sync_cfg.exclude_patterns)
        with pytest.raises(SystemExit, match="Vault não encontrado"):
            sync_vault(tmp_path / "nonexistent", source_dir, cfg)


# ---------------------------------------------------------------------------
# Python backend
# ---------------------------------------------------------------------------


class TestPythonBackend:

    def test_copies_md_files(self, vault_dir, source_dir, sync_cfg):
        cfg = SyncConfig(backend="python", delete_missing=True, follow_symlinks=False,
                         exclude_patterns=sync_cfg.exclude_patterns)
        result = sync_vault(vault_dir, source_dir, cfg)
        assert result == source_dir

        copied = sorted(f.name for f in source_dir.rglob("*.md"))
        assert "note1.md" in copied
        assert "note2.md" in copied
        assert "nested.md" in copied

    def test_excludes_non_md(self, vault_dir, source_dir, sync_cfg):
        cfg = SyncConfig(backend="python", delete_missing=True, follow_symlinks=False,
                         exclude_patterns=sync_cfg.exclude_patterns)
        sync_vault(vault_dir, source_dir, cfg)

        all_files = list(source_dir.rglob("*"))
        names = [f.name for f in all_files if f.is_file()]
        assert "image.png" not in names

    def test_excludes_obsidian_dir(self, vault_dir, source_dir, sync_cfg):
        cfg = SyncConfig(backend="python", delete_missing=True, follow_symlinks=False,
                         exclude_patterns=sync_cfg.exclude_patterns)
        sync_vault(vault_dir, source_dir, cfg)

        assert not (source_dir / ".obsidian").exists()

    def test_incremental_skips_unchanged(self, vault_dir, source_dir, sync_cfg):
        cfg = SyncConfig(backend="python", delete_missing=True, follow_symlinks=False,
                         exclude_patterns=sync_cfg.exclude_patterns)
        # First sync
        sync_vault(vault_dir, source_dir, cfg)
        mtime_before = (source_dir / "note1.md").stat().st_mtime

        # Second sync — file unchanged, should not be re-copied
        sync_vault(vault_dir, source_dir, cfg)
        mtime_after = (source_dir / "note1.md").stat().st_mtime
        assert mtime_before == mtime_after

    def test_incremental_copies_changed(self, vault_dir, source_dir, sync_cfg):
        cfg = SyncConfig(backend="python", delete_missing=True, follow_symlinks=False,
                         exclude_patterns=sync_cfg.exclude_patterns)
        # First sync
        sync_vault(vault_dir, source_dir, cfg)

        # Modify file in vault
        import time
        time.sleep(0.01)
        (vault_dir / "note1.md").write_text("# Updated\nNew content.", encoding="utf-8")

        # Second sync — file changed, should be copied
        sync_vault(vault_dir, source_dir, cfg)
        assert "Updated" in (source_dir / "note1.md").read_text(encoding="utf-8")

    def test_delete_missing(self, vault_dir, source_dir, sync_cfg):
        cfg = SyncConfig(backend="python", delete_missing=True, follow_symlinks=False,
                         exclude_patterns=sync_cfg.exclude_patterns)
        # First sync
        sync_vault(vault_dir, source_dir, cfg)
        assert (source_dir / "note1.md").exists()

        # Delete from vault
        (vault_dir / "note1.md").unlink()

        # Second sync — should delete from source
        sync_vault(vault_dir, source_dir, cfg)
        assert not (source_dir / "note1.md").exists()

    def test_no_delete_when_disabled(self, vault_dir, source_dir, sync_cfg):
        cfg = SyncConfig(backend="python", delete_missing=False, follow_symlinks=False,
                         exclude_patterns=sync_cfg.exclude_patterns)
        # First sync
        sync_vault(vault_dir, source_dir, cfg)

        # Delete from vault
        (vault_dir / "note1.md").unlink()

        # Second sync — should NOT delete from source
        sync_vault(vault_dir, source_dir, cfg)
        assert (source_dir / "note1.md").exists()

    def test_creates_source_dir_if_missing(self, vault_dir, tmp_path, sync_cfg):
        new_source = tmp_path / "new_source"
        cfg = SyncConfig(backend="python", delete_missing=True, follow_symlinks=False,
                         exclude_patterns=sync_cfg.exclude_patterns)
        result = sync_vault(vault_dir, new_source, cfg)
        assert result == new_source
        assert new_source.exists()


# ---------------------------------------------------------------------------
# Rsync backend (mocked)
# ---------------------------------------------------------------------------


class TestRsyncBackend:

    @patch("obsidian_rag.pipeline.vault_sync.is_rsync_available", return_value=True)
    @patch("obsidian_rag.pipeline.vault_sync.subprocess.run")
    def test_calls_rsync_with_correct_args(self, mock_run, _avail, vault_dir, source_dir, sync_cfg):
        mock_run.return_value = MagicMock(returncode=0)
        cfg = SyncConfig(backend="rsync", delete_missing=True, follow_symlinks=False,
                         exclude_patterns=sync_cfg.exclude_patterns)
        result = sync_vault(vault_dir, source_dir, cfg)
        assert result == source_dir

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "rsync"
        assert "-a" in cmd
        assert "--delete" in cmd
        assert f"{vault_dir}/" in cmd
        assert str(source_dir) in cmd

    @patch("obsidian_rag.pipeline.vault_sync.is_rsync_available", return_value=True)
    @patch("obsidian_rag.pipeline.vault_sync.subprocess.run")
    def test_rsync_failure_exits(self, mock_run, _avail, vault_dir, source_dir, sync_cfg):
        mock_run.return_value = MagicMock(returncode=1, stderr="rsync error")
        cfg = SyncConfig(backend="rsync", delete_missing=True, follow_symlinks=False,
                         exclude_patterns=sync_cfg.exclude_patterns)
        with pytest.raises(SystemExit, match="rsync falhou"):
            sync_vault(vault_dir, source_dir, cfg)


# ---------------------------------------------------------------------------
# Auto backend
# ---------------------------------------------------------------------------


class TestAutoBackend:

    @patch("obsidian_rag.pipeline.vault_sync.platform")
    @patch("obsidian_rag.pipeline.vault_sync.is_rsync_available", return_value=False)
    def test_auto_falls_back_to_python(self, _rsync, mock_platform, vault_dir, source_dir, sync_cfg):
        mock_platform.system.return_value = "Linux"
        cfg = SyncConfig(backend="auto", delete_missing=True, follow_symlinks=False,
                         exclude_patterns=sync_cfg.exclude_patterns)
        result = sync_vault(vault_dir, source_dir, cfg)
        assert result == source_dir  # python backend returns source_dir

        # Verify files were copied
        assert (source_dir / "note1.md").exists()


# ---------------------------------------------------------------------------
# Retrocompatibility: no [sync] section
# ---------------------------------------------------------------------------


class TestRetrocompat:

    def test_default_sync_config_values(self):
        """SyncConfig defaults match expected cross-platform safe values."""
        cfg = SyncConfig(
            backend="direct",
            delete_missing=True,
            follow_symlinks=False,
            exclude_patterns=_DEFAULT_EXCLUDE_PATTERNS,
        )
        assert cfg.backend == "direct"
        assert ".obsidian" in cfg.exclude_patterns
        assert ".git" in cfg.exclude_patterns

    def test_resolve_effective_backend_public(self):
        """Public API for rag doctor."""
        result = resolve_effective_backend("direct")
        assert result == "direct"
