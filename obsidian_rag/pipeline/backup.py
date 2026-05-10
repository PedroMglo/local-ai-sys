"""Backup do ChromaDB — copia a directoria de dados com rotação."""

from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

from obsidian_rag.config import settings

MAX_BACKUPS = 3


def backup_chroma(dest_dir: Path | None = None) -> Path:
    """Create a timestamped backup of the ChromaDB data directory.

    Keeps only the last MAX_BACKUPS copies, removing older ones.
    Returns the path to the new backup.
    """
    chroma_dir = settings.paths.data_dir
    if not chroma_dir.exists():
        raise FileNotFoundError(f"ChromaDB directory not found: {chroma_dir}")

    if dest_dir is None:
        dest_dir = chroma_dir.parent / "backups"

    dest_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = dest_dir / f"chroma_backup_{timestamp}"

    shutil.copytree(chroma_dir, backup_path)

    # Rotate: keep only the newest MAX_BACKUPS
    existing = sorted(dest_dir.glob("chroma_backup_*"), key=lambda p: p.name)
    while len(existing) > MAX_BACKUPS:
        oldest = existing.pop(0)
        shutil.rmtree(oldest)

    return backup_path


def main() -> None:
    """CLI entry point for rag-backup."""
    try:
        dest = Path(sys.argv[1]) if len(sys.argv) > 1 else None
        backup_path = backup_chroma(dest)
        print(f"Backup criado: {backup_path}")
    except FileNotFoundError as e:
        print(f"Erro: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Erro no backup: {e}", file=sys.stderr)
        sys.exit(1)
