"""Tests for security validations."""

from __future__ import annotations

import subprocess
import sys
from unittest.mock import patch

import pytest


class TestBindSecurity:
    """API must refuse 0.0.0.0 without api_key."""

    def test_serve_refuses_wildcard_without_key(self):
        """serve() should exit(1) when host=0.0.0.0 and api_key is empty."""
        from obsidian_rag.config import ApiConfig

        mock_api = ApiConfig(
            host="0.0.0.0",
            port=8484,
            query_top_k=10,
            api_key="",
            rate_limit=60,
            chat_rate_limit=20,
        )

        with (
            patch("obsidian_rag.api.app.settings") as mock_settings,
            pytest.raises(SystemExit) as exc_info,
        ):
            mock_settings.api = mock_api
            from obsidian_rag.api.app import serve
            serve()

        assert exc_info.value.code == 1

    def test_serve_allows_wildcard_with_key(self):
        """serve() should proceed when host=0.0.0.0 and api_key is set."""
        from obsidian_rag.config import ApiConfig

        mock_api = ApiConfig(
            host="0.0.0.0",
            port=9999,
            query_top_k=10,
            api_key="my-secret-key",
            rate_limit=60,
            chat_rate_limit=20,
        )

        with (
            patch("obsidian_rag.api.app.settings") as mock_settings,
            patch("uvicorn.run") as mock_uvicorn,
        ):
            mock_settings.api = mock_api
            from obsidian_rag.api.app import serve
            serve()
            mock_uvicorn.assert_called_once_with(
                "obsidian_rag.api.app:app",
                host="0.0.0.0",
                port=9999,
            )

    def test_serve_allows_localhost(self):
        """serve() should proceed with 127.0.0.1 without api_key."""
        from obsidian_rag.config import ApiConfig

        mock_api = ApiConfig(
            host="127.0.0.1",
            port=8484,
            query_top_k=10,
            api_key="",
            rate_limit=60,
            chat_rate_limit=20,
        )

        with (
            patch("obsidian_rag.api.app.settings") as mock_settings,
            patch("uvicorn.run") as mock_uvicorn,
        ):
            mock_settings.api = mock_api
            from obsidian_rag.api.app import serve
            serve()
            mock_uvicorn.assert_called_once()


class TestConfigLazyLoading:
    """settings must not crash on import when rag.toml is missing."""

    def test_import_config_without_toml(self, tmp_path, monkeypatch):
        """Importing settings should not raise when rag.toml doesn't exist."""
        monkeypatch.setattr("obsidian_rag.config.PROJECT_ROOT", tmp_path)
        # Reset singleton
        from obsidian_rag import config
        config.settings = config._LazySettings()
        # Import should succeed — no attribute access yet
        assert repr(config.settings) == "<LazySettings: not loaded>"

    def test_config_exists_false(self, tmp_path, monkeypatch):
        monkeypatch.setattr("obsidian_rag.config.PROJECT_ROOT", tmp_path)
        from obsidian_rag.config import config_exists
        assert config_exists() is False

    def test_config_exists_true(self, tmp_path, monkeypatch):
        (tmp_path / "rag.toml").write_text("[paths]\n")
        monkeypatch.setattr("obsidian_rag.config.PROJECT_ROOT", tmp_path)
        from obsidian_rag.config import config_exists
        assert config_exists() is True
