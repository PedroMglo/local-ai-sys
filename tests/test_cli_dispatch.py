"""Tests for the unified rag CLI dispatcher."""

from __future__ import annotations

import subprocess
import sys

import pytest


class TestCLIDispatch:
    """Verify that rag dispatches subcommands correctly."""

    def test_rag_no_args_shows_help(self):
        result = subprocess.run(
            [sys.executable, "-m", "obsidian_rag.cli.main"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "rag" in result.stdout.lower() or "subcomando" in result.stdout.lower()

    def test_rag_help_flag(self):
        result = subprocess.run(
            [sys.executable, "-m", "obsidian_rag.cli.main", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        assert "init" in result.stdout
        assert "sync" in result.stdout
        assert "serve" in result.stdout
        assert "query" in result.stdout
        assert "doctor" in result.stdout
        assert "graph" in result.stdout

    def test_rag_sync_requires_flag(self):
        result = subprocess.run(
            [sys.executable, "-m", "obsidian_rag.cli.main", "sync"],
            capture_output=True, text=True,
        )
        # Should fail because -l, -g, or --all is required
        assert result.returncode != 0

    def test_rag_graph_no_subcommand(self):
        result = subprocess.run(
            [sys.executable, "-m", "obsidian_rag.cli.main", "graph"],
            capture_output=True, text=True,
        )
        # Should show graph help and exit
        assert result.returncode != 0 or "build" in result.stdout or "status" in result.stdout
