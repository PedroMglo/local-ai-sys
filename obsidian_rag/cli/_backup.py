"""Thin wrapper — delegates backup logic."""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path


def run_backup(args: Namespace) -> None:
    from obsidian_rag.pipeline.backup import backup_store

    try:
        dest = Path(args.dest) if args.dest else None
        backup_path = backup_store(dest)
        print(f"Backup criado: {backup_path}")
    except FileNotFoundError as e:
        print(f"Erro: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Erro no backup: {e}", file=sys.stderr)
        sys.exit(1)
