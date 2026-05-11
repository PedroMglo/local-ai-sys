"""Tests for incremental graphify change detection (graph/builder.py)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from obsidian_rag.graph.builder import _detect_changes, _file_md5


# ---------------------------------------------------------------------------
# _file_md5
# ---------------------------------------------------------------------------

class TestFileMd5:

    def test_basic_hash(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("hello world")
        h = _file_md5(f)
        assert len(h) == 32  # md5 hex
        assert h == _file_md5(f)  # deterministic

    def test_different_content_different_hash(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("foo")
        f2.write_text("bar")
        assert _file_md5(f1) != _file_md5(f2)

    def test_missing_file_returns_empty(self, tmp_path):
        assert _file_md5(tmp_path / "nonexistent.py") == ""


# ---------------------------------------------------------------------------
# _detect_changes
# ---------------------------------------------------------------------------

def _write_manifest(manifest_path: Path, files: dict[str, str]):
    """Write a graphify-style manifest.json.

    files: {abs_path_str: md5_hash}
    """
    data = {}
    for path_str, md5 in files.items():
        data[path_str] = {"mtime": 1234567890.0, "hash": md5}
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(data), encoding="utf-8")


class TestDetectChanges:

    def test_no_manifest_returns_full_rebuild(self, tmp_path):
        """Missing manifest → (True, True)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        manifest = tmp_path / "manifest.json"
        has_changes, has_doc = _detect_changes(repo, manifest)
        assert has_changes is True
        assert has_doc is True

    def test_corrupt_manifest_returns_full_rebuild(self, tmp_path):
        """Invalid JSON → (True, True)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        manifest = tmp_path / "manifest.json"
        manifest.write_text("{invalid json")
        has_changes, has_doc = _detect_changes(repo, manifest)
        assert has_changes is True
        assert has_doc is True

    def test_no_changes(self, tmp_path):
        """All files match manifest → (False, False)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        f1 = repo / "main.py"
        f1.write_text("print('hello')")
        f2 = repo / "lib.py"
        f2.write_text("x = 1")

        manifest = tmp_path / "manifest.json"
        _write_manifest(manifest, {
            str(f1): _file_md5(f1),
            str(f2): _file_md5(f2),
        })

        has_changes, has_doc = _detect_changes(repo, manifest)
        assert has_changes is False
        assert has_doc is False

    def test_code_file_changed(self, tmp_path):
        """Python file hash changed → (True, False)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        f1 = repo / "main.py"
        f1.write_text("original")

        manifest = tmp_path / "manifest.json"
        _write_manifest(manifest, {str(f1): _file_md5(f1)})

        # Modify the file
        f1.write_text("modified")

        has_changes, has_doc = _detect_changes(repo, manifest)
        assert has_changes is True
        assert has_doc is False

    def test_doc_file_changed(self, tmp_path):
        """Markdown file hash changed → (True, True)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        f1 = repo / "README.md"
        f1.write_text("# Old")

        manifest = tmp_path / "manifest.json"
        _write_manifest(manifest, {str(f1): _file_md5(f1)})

        f1.write_text("# New")

        has_changes, has_doc = _detect_changes(repo, manifest)
        assert has_changes is True
        assert has_doc is True

    def test_deleted_code_file(self, tmp_path):
        """File in manifest no longer exists → (True, False) for .py."""
        repo = tmp_path / "repo"
        repo.mkdir()
        f1 = repo / "gone.py"
        f1.write_text("x = 1")
        old_hash = _file_md5(f1)
        f1.unlink()

        manifest = tmp_path / "manifest.json"
        _write_manifest(manifest, {str(f1): old_hash})

        has_changes, has_doc = _detect_changes(repo, manifest)
        assert has_changes is True
        assert has_doc is False

    def test_deleted_doc_file(self, tmp_path):
        """Doc file in manifest no longer exists → (True, True)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        f1 = repo / "notes.md"
        f1.write_text("# Notes")
        old_hash = _file_md5(f1)
        f1.unlink()

        manifest = tmp_path / "manifest.json"
        _write_manifest(manifest, {str(f1): old_hash})

        has_changes, has_doc = _detect_changes(repo, manifest)
        assert has_changes is True
        assert has_doc is True

    def test_new_code_file(self, tmp_path):
        """New .py file not in manifest → (True, False)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        existing = repo / "old.py"
        existing.write_text("x = 1")

        manifest = tmp_path / "manifest.json"
        _write_manifest(manifest, {str(existing): _file_md5(existing)})

        # Add a new file
        (repo / "new.py").write_text("y = 2")

        has_changes, has_doc = _detect_changes(repo, manifest)
        assert has_changes is True
        assert has_doc is False

    def test_new_doc_file(self, tmp_path):
        """New .md file not in manifest → (True, True)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        existing = repo / "main.py"
        existing.write_text("pass")

        manifest = tmp_path / "manifest.json"
        _write_manifest(manifest, {str(existing): _file_md5(existing)})

        (repo / "CHANGELOG.md").write_text("# Changes")

        has_changes, has_doc = _detect_changes(repo, manifest)
        assert has_changes is True
        assert has_doc is True

    def test_hidden_dirs_ignored(self, tmp_path):
        """Files inside .git, __pycache__, etc. are ignored."""
        repo = tmp_path / "repo"
        repo.mkdir()
        f1 = repo / "main.py"
        f1.write_text("pass")

        manifest = tmp_path / "manifest.json"
        _write_manifest(manifest, {str(f1): _file_md5(f1)})

        # Add files in hidden/ignored dirs
        git_dir = repo / ".git" / "objects"
        git_dir.mkdir(parents=True)
        (git_dir / "abc123").write_text("git object")

        pycache = repo / "__pycache__"
        pycache.mkdir()
        (pycache / "main.cpython-312.pyc").write_bytes(b"\x00")

        has_changes, has_doc = _detect_changes(repo, manifest)
        assert has_changes is False
        assert has_doc is False

    def test_txt_extension_is_doc(self, tmp_path):
        """.txt files count as doc files (need LLM)."""
        repo = tmp_path / "repo"
        repo.mkdir()
        f1 = repo / "notes.txt"
        f1.write_text("old content")

        manifest = tmp_path / "manifest.json"
        _write_manifest(manifest, {str(f1): _file_md5(f1)})

        f1.write_text("new content")

        has_changes, has_doc = _detect_changes(repo, manifest)
        assert has_changes is True
        assert has_doc is True


# ---------------------------------------------------------------------------
# build_graph incremental behaviour (mocked subprocess)
# ---------------------------------------------------------------------------

class TestBuildGraphIncremental:

    @pytest.fixture
    def repo_setup(self, tmp_path):
        """Set up a fake repo with graphify output directory."""
        repo = tmp_path / "my_repo"
        repo.mkdir()
        (repo / "main.py").write_text("print('hello')")

        out_dir = tmp_path / "graphify_out" / "my_repo" / "graphify-out"
        out_dir.mkdir(parents=True)

        graph_json = out_dir / "graph.json"
        graph_json.write_text('{"nodes":[],"edges":[]}')

        manifest = out_dir / "manifest.json"
        f = repo / "main.py"
        _write_manifest(manifest, {str(f): _file_md5(f)})

        return repo, out_dir, graph_json, manifest

    @patch("obsidian_rag.graph.builder.settings")
    def test_skip_when_no_changes(self, mock_settings, repo_setup):
        """No file changes → subprocess not called, returns True."""
        repo, out_dir, graph_json, manifest = repo_setup

        mock_settings.graphify.output_dir = str(out_dir.parent.parent)
        mock_settings.graphify.auto_update = True
        mock_settings.graphify.backend = "ollama"
        mock_settings.graphify.model = ""

        from obsidian_rag.graph.builder import build_graph

        with patch("obsidian_rag.graph.builder.subprocess") as mock_sub:
            result = build_graph(repo, force=False)

        assert result is True
        mock_sub.run.assert_not_called()

    @patch("obsidian_rag.graph.builder.settings")
    def test_update_when_only_code_changed(self, mock_settings, repo_setup):
        """Only .py changed → uses 'graphify update', not 'extract'."""
        repo, out_dir, graph_json, manifest = repo_setup

        mock_settings.graphify.output_dir = str(out_dir.parent.parent)
        mock_settings.graphify.auto_update = True
        mock_settings.graphify.backend = "ollama"
        mock_settings.graphify.model = ""
        mock_settings.ollama.base_url = "http://localhost:11434"
        mock_settings.performance.graph_timeout = 600

        # Modify the .py file
        (repo / "main.py").write_text("print('changed')")

        from obsidian_rag.graph.builder import build_graph

        with patch("obsidian_rag.graph.builder.subprocess") as mock_sub:
            mock_sub.run.return_value.stderr = ""
            build_graph(repo, force=False)

        call_args = mock_sub.run.call_args
        cmd = call_args[0][0]
        assert cmd[1] == "update"  # graphify update, not extract

    @patch("obsidian_rag.graph.builder.settings")
    def test_extract_when_doc_changed(self, mock_settings, repo_setup):
        """Doc file changed → uses 'graphify extract' (with LLM)."""
        repo, out_dir, graph_json, manifest = repo_setup

        # Add a markdown file to manifest and repo
        md_file = repo / "README.md"
        md_file.write_text("# Old")
        # Update manifest to include the md file
        m = json.loads(manifest.read_text())
        m[str(md_file)] = {"mtime": 1234567890.0, "hash": _file_md5(md_file)}
        manifest.write_text(json.dumps(m))
        # Now change the md file
        md_file.write_text("# New content")

        mock_settings.graphify.output_dir = str(out_dir.parent.parent)
        mock_settings.graphify.auto_update = True
        mock_settings.graphify.backend = "ollama"
        mock_settings.graphify.model = ""
        mock_settings.ollama.base_url = "http://localhost:11434"
        mock_settings.performance.graph_timeout = 600

        from obsidian_rag.graph.builder import build_graph

        with patch("obsidian_rag.graph.builder.subprocess") as mock_sub:
            mock_sub.run.return_value.stderr = ""
            build_graph(repo, force=False)

        call_args = mock_sub.run.call_args
        cmd = call_args[0][0]
        assert cmd[1] == "extract"  # full extract with LLM

    @patch("obsidian_rag.graph.builder.settings")
    def test_force_ignores_change_detection(self, mock_settings, repo_setup):
        """force=True → always runs extract, ignores manifest."""
        repo, out_dir, graph_json, manifest = repo_setup

        mock_settings.graphify.output_dir = str(out_dir.parent.parent)
        mock_settings.graphify.auto_update = True
        mock_settings.graphify.backend = "ollama"
        mock_settings.graphify.model = ""
        mock_settings.ollama.base_url = "http://localhost:11434"
        mock_settings.performance.graph_timeout = 600

        from obsidian_rag.graph.builder import build_graph

        with patch("obsidian_rag.graph.builder.subprocess") as mock_sub:
            mock_sub.run.return_value.stderr = ""
            build_graph(repo, force=True)

        call_args = mock_sub.run.call_args
        cmd = call_args[0][0]
        assert cmd[1] == "extract"
