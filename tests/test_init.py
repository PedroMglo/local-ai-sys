"""Tests for rag init — config generation and path validation."""

from __future__ import annotations

import tomllib
from pathlib import Path
from unittest.mock import patch

import pytest

from obsidian_rag.cli.init_cmd import _is_dangerous_path, _generate_toml


class TestDangerousPathValidation:
    """Validate that dangerous paths are rejected."""

    def test_root_path(self):
        assert _is_dangerous_path("/") is not None

    def test_home_path(self):
        assert _is_dangerous_path("~") is not None

    def test_ssh_path(self):
        assert _is_dangerous_path("~/.ssh") is not None

    def test_gnupg_path(self):
        assert _is_dangerous_path("~/.gnupg") is not None

    def test_cache_path(self):
        assert _is_dangerous_path("~/.cache") is not None

    def test_trash_path(self):
        assert _is_dangerous_path("~/.local/share/Trash") is not None

    def test_system_dirs(self):
        for d in ["/etc", "/usr", "/var", "/proc", "/sys"]:
            assert _is_dangerous_path(d) is not None, f"Should reject {d}"

    def test_valid_vault_path(self):
        assert _is_dangerous_path("~/Obsidian/Vault") is None

    def test_valid_repo_path(self):
        assert _is_dangerous_path("~/Projects/my-repo") is None

    def test_valid_absolute_path(self):
        assert _is_dangerous_path("/home/user/Documents/notes") is None


class TestTomlGeneration:
    """Validate generated rag.toml content."""

    def test_generates_valid_toml(self):
        content = _generate_toml(
            vault_dir="~/Obsidian/Vault",
            repos=["~/Projects/repo1", "~/Projects/repo2"],
            ollama_url="http://localhost:11434",
            models={"qwen3:8b": True, "coder:7b": False},
            host="127.0.0.1",
            api_key="",
        )
        # Must be parseable TOML
        parsed = tomllib.loads(content)
        assert parsed["paths"]["vault_dir"] == "~/Obsidian/Vault"
        assert parsed["paths"]["source_dir"] == "source"
        assert parsed["ollama"]["base_url"] == "http://localhost:11434"
        assert parsed["api"]["host"] == "127.0.0.1"
        assert parsed["api"]["api_key"] == ""
        assert parsed["graphify"]["enabled"] is False

    def test_repos_in_toml(self):
        content = _generate_toml(
            vault_dir="~/vault",
            repos=["~/repo-a", "~/repo-b"],
            ollama_url="http://localhost:11434",
            models={},
            host="127.0.0.1",
            api_key="",
        )
        parsed = tomllib.loads(content)
        assert "~/repo-a" in parsed["repos"]["paths"]
        assert "~/repo-b" in parsed["repos"]["paths"]

    def test_api_key_in_toml(self):
        content = _generate_toml(
            vault_dir="~/vault",
            repos=[],
            ollama_url="http://localhost:11434",
            models={},
            host="0.0.0.0",
            api_key="test-secret-key-123",
        )
        parsed = tomllib.loads(content)
        assert parsed["api"]["host"] == "0.0.0.0"
        assert parsed["api"]["api_key"] == "test-secret-key-123"

    def test_models_in_toml(self):
        content = _generate_toml(
            vault_dir="~/vault",
            repos=[],
            ollama_url="http://localhost:11434",
            models={"qwen3:8b": True, "coder:7b": False},
            host="127.0.0.1",
            api_key="",
        )
        parsed = tomllib.loads(content)
        assert parsed["models"]["qwen3:8b"] is True
        assert parsed["models"]["coder:7b"] is False
