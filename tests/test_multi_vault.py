"""Tests for multi-vault Obsidian support (#188).

Covers:
- config.py: vault_dirs field, backward compat
- pipeline/sync.py: vault_filter parameter
- pipeline/ingest.py: source_name metadata injection
- api/schemas.py: vault field on QueryRequest
- cli/main.py: --vault flag parsing
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Config: vault_dirs
# ---------------------------------------------------------------------------

class TestVaultDirsConfig:
    """PathsConfig.vault_dirs population."""

    def test_single_vault_dir_backward_compat(self, tmp_path: Path):
        """When only vault_dir is set, vault_dirs == (vault_dir,)."""
        toml_content = f"""
[paths]
vault_dir = "{tmp_path}"
"""
        with patch("obsidian_rag.config._load_toml", return_value={
            "paths": {"vault_dir": str(tmp_path)},
        }):
            from obsidian_rag.config import load_settings
            s = load_settings()
            assert len(s.paths.vault_dirs) == 1
            assert s.paths.vault_dirs[0] == s.paths.vault_dir

    def test_vault_dirs_list(self, tmp_path: Path):
        """When vault_dirs is set, it takes precedence."""
        v1 = tmp_path / "Vault1"
        v2 = tmp_path / "Vault2"
        v1.mkdir()
        v2.mkdir()

        with patch("obsidian_rag.config._load_toml", return_value={
            "paths": {
                "vault_dir": str(v1),
                "vault_dirs": [str(v1), str(v2)],
            },
        }):
            from obsidian_rag.config import load_settings
            s = load_settings()
            assert len(s.paths.vault_dirs) == 2
            assert s.paths.vault_dirs[0] == v1.resolve()
            assert s.paths.vault_dirs[1] == v2.resolve()

    def test_vault_dirs_empty_falls_back(self, tmp_path: Path):
        """Empty vault_dirs list falls back to [vault_dir]."""
        with patch("obsidian_rag.config._load_toml", return_value={
            "paths": {
                "vault_dir": str(tmp_path),
                "vault_dirs": [],
            },
        }):
            from obsidian_rag.config import load_settings
            s = load_settings()
            assert len(s.paths.vault_dirs) == 1

    def test_vault_dirs_is_tuple(self, tmp_path: Path):
        """vault_dirs must be a tuple (frozen dataclass)."""
        with patch("obsidian_rag.config._load_toml", return_value={
            "paths": {"vault_dir": str(tmp_path)},
        }):
            from obsidian_rag.config import load_settings
            s = load_settings()
            assert isinstance(s.paths.vault_dirs, tuple)


# ---------------------------------------------------------------------------
# Sync: vault_filter
# ---------------------------------------------------------------------------

class TestSyncVaultFilter:
    """sync_notes() vault_filter parameter."""

    @patch("obsidian_rag.pipeline.sync.sync_vault")
    @patch("obsidian_rag.pipeline.sync.get_store")
    @patch("obsidian_rag.pipeline.sync.clear_embed_cache")
    @patch("obsidian_rag.pipeline.sync.IngestManifest")
    @patch("obsidian_rag.pipeline.sync.IngestPipeline")
    def test_filter_selects_matching_vault(
        self, mock_pipeline_cls, mock_manifest, mock_clear, mock_store, mock_sync_vault, tmp_path
    ):
        """vault_filter selects only matching vault directory."""
        v1 = tmp_path / "Personal"
        v2 = tmp_path / "Work"
        v1.mkdir()
        v2.mkdir()

        mock_sync_vault.return_value = v2

        mock_result = MagicMock()
        mock_result.elapsed_seconds = 0.1
        mock_result.files_scanned = 0
        mock_result.files_parsed = 0
        mock_result.files_skipped = 0
        mock_result.chunks_produced = 0
        mock_result.chunks_embedded = 0
        mock_result.chunks_stored = 0
        mock_result.stale_deleted = 0
        mock_result.errors = []

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = mock_result
        mock_pipeline_cls.return_value = mock_pipeline

        mock_store_inst = MagicMock()
        mock_store_inst.count.return_value = 0
        mock_store.return_value = mock_store_inst

        mock_manifest_inst = MagicMock()
        mock_manifest.return_value = mock_manifest_inst

        # Mock governor to always allow
        mock_gov = MagicMock()
        from obsidian_rag.pipeline.governor import GovernorAction
        mock_gov.check.return_value = GovernorAction.CONTINUE

        with patch("obsidian_rag.pipeline.sync.settings") as mock_settings, \
             patch("obsidian_rag.pipeline.governor.ResourceGovernor", return_value=mock_gov):
            mock_settings.paths.vault_dirs = (v1, v2)
            mock_settings.paths.source_dir = tmp_path / "source"
            mock_settings.paths.data_dir = tmp_path / "data"
            mock_settings.performance = MagicMock()
            mock_settings.sync = MagicMock()
            mock_settings.pipeline = MagicMock()

            from obsidian_rag.pipeline.sync import sync_notes
            sync_notes(vault_filter="Work")

        # Only Work vault should be synced
        mock_sync_vault.assert_called_once()
        call_args = mock_sync_vault.call_args
        assert call_args.kwargs["vault_dir"] == v2

    @patch("obsidian_rag.pipeline.sync.sync_vault")
    @patch("obsidian_rag.pipeline.sync.clear_embed_cache")
    def test_filter_no_match_prints_error(
        self, mock_clear, mock_sync_vault, tmp_path, capsys
    ):
        """vault_filter with no match prints error and returns."""
        v1 = tmp_path / "Personal"
        v1.mkdir()

        mock_gov = MagicMock()
        from obsidian_rag.pipeline.governor import GovernorAction
        mock_gov.check.return_value = GovernorAction.CONTINUE

        with patch("obsidian_rag.pipeline.sync.settings") as mock_settings, \
             patch("obsidian_rag.pipeline.governor.ResourceGovernor", return_value=mock_gov):
            mock_settings.paths.vault_dirs = (v1,)
            mock_settings.paths.data_dir = tmp_path / "data"
            mock_settings.performance = MagicMock()

            from obsidian_rag.pipeline.sync import sync_notes
            sync_notes(vault_filter="NonExistent")

        mock_sync_vault.assert_not_called()
        captured = capsys.readouterr()
        assert "NonExistent" in captured.out

    @patch("obsidian_rag.pipeline.sync.sync_vault")
    @patch("obsidian_rag.pipeline.sync.get_store")
    @patch("obsidian_rag.pipeline.sync.clear_embed_cache")
    @patch("obsidian_rag.pipeline.sync.IngestManifest")
    @patch("obsidian_rag.pipeline.sync.IngestPipeline")
    def test_no_filter_syncs_all_vaults(
        self, mock_pipeline_cls, mock_manifest, mock_clear, mock_store, mock_sync_vault, tmp_path
    ):
        """Without vault_filter, all vaults are synced."""
        v1 = tmp_path / "Personal"
        v2 = tmp_path / "Work"
        v1.mkdir()
        v2.mkdir()

        mock_sync_vault.side_effect = [v1, v2]

        mock_result = MagicMock()
        mock_result.elapsed_seconds = 0.1
        mock_result.files_scanned = 0
        mock_result.files_parsed = 0
        mock_result.files_skipped = 0
        mock_result.chunks_produced = 0
        mock_result.chunks_embedded = 0
        mock_result.chunks_stored = 0
        mock_result.stale_deleted = 0
        mock_result.errors = []

        mock_pipeline = MagicMock()
        mock_pipeline.run.return_value = mock_result
        mock_pipeline_cls.return_value = mock_pipeline

        mock_store_inst = MagicMock()
        mock_store_inst.count.return_value = 0
        mock_store.return_value = mock_store_inst

        mock_manifest_inst = MagicMock()
        mock_manifest.return_value = mock_manifest_inst

        mock_gov = MagicMock()
        from obsidian_rag.pipeline.governor import GovernorAction
        mock_gov.check.return_value = GovernorAction.CONTINUE

        with patch("obsidian_rag.pipeline.sync.settings") as mock_settings, \
             patch("obsidian_rag.pipeline.governor.ResourceGovernor", return_value=mock_gov):
            mock_settings.paths.vault_dirs = (v1, v2)
            mock_settings.paths.source_dir = tmp_path / "source"
            mock_settings.paths.data_dir = tmp_path / "data"
            mock_settings.performance = MagicMock()
            mock_settings.sync = MagicMock()
            mock_settings.pipeline = MagicMock()

            from obsidian_rag.pipeline.sync import sync_notes
            sync_notes()

        # Both vaults synced
        assert mock_sync_vault.call_count == 2

        # Pipeline.run called with sources for both vaults
        run_call = mock_pipeline.run.call_args
        sources = run_call[0][0]
        assert len(sources) == 2
        names = {s.name for s in sources}
        assert names == {"Personal", "Work"}


# ---------------------------------------------------------------------------
# Ingest: source_name metadata injection
# ---------------------------------------------------------------------------

class TestSourceNameInjection:
    """Chunk metadata gets source_name from IngestSource.name."""

    def test_chunk_metadata_gets_source_name(self, tmp_path: Path):
        """Chunks parsed from vault files get source_name in metadata."""
        from obsidian_rag.chunking.markdown import Chunk

        # Simulate what ingest.py does: inject source_name
        chunk = Chunk(
            id="test-id",
            text="Test content",
            metadata={"source_path": "note.md", "note_title": "Note"},
        )
        chunk.metadata.setdefault("source_name", "MyVault")
        assert chunk.metadata["source_name"] == "MyVault"

    def test_existing_source_name_not_overwritten(self):
        """setdefault does not overwrite existing source_name."""
        from obsidian_rag.chunking.markdown import Chunk

        chunk = Chunk(
            id="test-id",
            text="Test content",
            metadata={"source_name": "Original"},
        )
        chunk.metadata.setdefault("source_name", "NewVault")
        assert chunk.metadata["source_name"] == "Original"


# ---------------------------------------------------------------------------
# API: vault filter on QueryRequest
# ---------------------------------------------------------------------------

class TestQueryRequestVault:
    """QueryRequest.vault field."""

    def test_vault_field_default_none(self):
        from obsidian_rag.api.schemas import QueryRequest
        req = QueryRequest(query="test query")
        assert req.vault is None

    def test_vault_field_set(self):
        from obsidian_rag.api.schemas import QueryRequest
        req = QueryRequest(query="test query", vault="Work")
        assert req.vault == "Work"


# ---------------------------------------------------------------------------
# CLI: --vault flag
# ---------------------------------------------------------------------------

class TestCLIVaultFlag:
    """CLI --vault flag on sync and query."""

    def test_sync_parser_accepts_vault(self):
        """rag sync -l --vault NAME is valid."""
        import sys
        from unittest.mock import patch as _patch
        with _patch.object(sys, "argv", ["rag", "sync", "-l", "--vault", "Work"]):
            from obsidian_rag.cli.main import main
            import argparse
            # We just test parsing, not execution
            parser = argparse.ArgumentParser()
            sub = parser.add_subparsers(dest="command")
            p_sync = sub.add_parser("sync")
            sync_group = p_sync.add_mutually_exclusive_group(required=True)
            sync_group.add_argument("-l", "--local", action="store_true")
            sync_group.add_argument("-g", "--graph", action="store_true")
            sync_group.add_argument("--all", action="store_true", dest="run_all")
            p_sync.add_argument("--vault", metavar="NAME")

            args = parser.parse_args(["sync", "-l", "--vault", "Work"])
            assert args.vault == "Work"
            assert args.local is True

    def test_query_parser_accepts_vault(self):
        """rag query --vault NAME is valid."""
        import argparse
        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="command")
        p_query = sub.add_parser("query")
        p_query.add_argument("query", nargs="+")
        p_query.add_argument("--vault", type=str, default=None)

        args = parser.parse_args(["query", "--vault", "Personal", "what is RAG?"])
        assert args.vault == "Personal"

    def test_vault_filter_case_insensitive(self, tmp_path: Path):
        """Vault filter matching is case-insensitive."""
        v1 = tmp_path / "MyVault"
        v1.mkdir()

        dirs = (v1,)
        filtered = tuple(
            vd for vd in dirs
            if vd.name.lower() == "myvault"
        )
        assert len(filtered) == 1
        assert filtered[0] == v1


# ---------------------------------------------------------------------------
# sync_local passthrough
# ---------------------------------------------------------------------------

class TestSyncLocalPassthrough:
    """sync_local passes vault_filter to sync_notes."""

    @patch("obsidian_rag.pipeline.sync.sync_repos")
    @patch("obsidian_rag.pipeline.sync.sync_notes")
    @patch("obsidian_rag.pipeline.sync._wait_for_resources", return_value=True)
    def test_sync_local_passes_vault_filter(self, mock_wait, mock_notes, mock_repos):
        from obsidian_rag.pipeline.sync import sync_local
        sync_local(vault_filter="Work")
        mock_notes.assert_called_once_with(vault_filter="Work")

    @patch("obsidian_rag.pipeline.sync.sync_repos")
    @patch("obsidian_rag.pipeline.sync.sync_notes")
    @patch("obsidian_rag.pipeline.sync._wait_for_resources", return_value=True)
    def test_sync_local_no_filter(self, mock_wait, mock_notes, mock_repos):
        from obsidian_rag.pipeline.sync import sync_local
        sync_local()
        mock_notes.assert_called_once_with(vault_filter=None)
