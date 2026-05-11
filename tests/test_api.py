"""Integration tests for API authentication middleware."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


def _make_client(api_key: str = ""):
    """Create a TestClient with a specific api_key config."""
    from obsidian_rag.config import ApiConfig

    mock_api = ApiConfig(host="127.0.0.1", port=8484, query_top_k=10, api_key=api_key)

    with patch("obsidian_rag.api.app.settings") as mock_settings:
        mock_settings.api = mock_api
        # Re-import to pick up the patched settings
        from obsidian_rag.api.app import app
        yield TestClient(app, raise_server_exceptions=False)


class TestHealthEndpoint:
    """Health endpoint should always be accessible."""

    def test_health_no_auth_configured(self):
        with patch("obsidian_rag.api.app.settings") as mock_settings:
            mock_settings.api.api_key = ""
            from obsidian_rag.api.app import app
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ok"

    def test_health_with_auth_configured_no_key(self):
        with patch("obsidian_rag.api.app.settings") as mock_settings:
            mock_settings.api.api_key = "secret123"
            from obsidian_rag.api.app import app
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/health")
            assert resp.status_code == 200


class TestAuthMiddleware:
    """Protected endpoints should enforce API key when configured."""

    def test_no_auth_when_key_empty(self):
        with patch("obsidian_rag.api.app.settings") as mock_settings:
            mock_settings.api.api_key = ""
            from obsidian_rag.api.app import app
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/stats")
            # May fail for other reasons (Qdrant not available) but NOT 401
            assert resp.status_code != 401

    def test_401_when_key_configured_no_header(self):
        with patch("obsidian_rag.api.app.settings") as mock_settings:
            mock_settings.api.api_key = "test-secret-key"
            from obsidian_rag.api.app import app
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/stats")
            assert resp.status_code == 401

    def test_401_when_wrong_key(self):
        with patch("obsidian_rag.api.app.settings") as mock_settings:
            mock_settings.api.api_key = "correct-key"
            from obsidian_rag.api.app import app
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/stats", headers={"Authorization": "Bearer wrong-key"})
            assert resp.status_code == 401

    def test_passes_with_correct_key(self):
        with patch("obsidian_rag.api.app.settings") as mock_settings:
            mock_settings.api.api_key = "correct-key"
            from obsidian_rag.api.app import app
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/stats", headers={"Authorization": "Bearer correct-key"})
            # Should not be 401 (may be 500 if Qdrant not available, that's fine)
            assert resp.status_code != 401

    def test_401_missing_bearer_prefix(self):
        with patch("obsidian_rag.api.app.settings") as mock_settings:
            mock_settings.api.api_key = "mykey"
            from obsidian_rag.api.app import app
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.get("/stats", headers={"Authorization": "mykey"})
            assert resp.status_code == 401
