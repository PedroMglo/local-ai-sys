"""Cross-platform vault sync backends.

Provides four strategies to get Obsidian notes ready for chunking:

  direct  — read vault_dir in-place (no copy, cross-platform, default)
  python  — incremental copy vault_dir → source_dir (shutil, cross-platform)
  rsync   — shell out to rsync (Linux/macOS optimisation)
  auto    — rsync if available, else python

Usage:
    effective_dir = sync_vault(settings)
    # Pass effective_dir to IngestPipeline via IngestSource(path=effective_dir)
"""

from __future__ import annotations

import logging
import platform
import shutil
import subprocess
from fnmatch import fnmatch
from pathlib import Path

from obsidian_rag.config import _DEFAULT_EXCLUDE_PATTERNS, SyncConfig

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def sync_vault(
    vault_dir: Path,
    source_dir: Path,
    cfg: SyncConfig,
) -> Path:
    """Sync vault and return the effective directory for chunking.

    Returns *vault_dir* when backend is ``direct`` (no copy needed),
    otherwise returns *source_dir* after syncing.
    """
    backend = _resolve_backend(cfg.backend)
    log.info("Sync backend: %s (configured: %s)", backend, cfg.backend)

    if backend == "direct":
        _validate_vault(vault_dir)
        print(f"==> [Sync] Modo directo — a ler de {vault_dir}")
        return vault_dir

    # python / rsync — need source_dir
    _validate_vault(vault_dir)
    source_dir.mkdir(parents=True, exist_ok=True)

    if backend == "rsync":
        _sync_rsync(vault_dir, source_dir, cfg)
    else:
        _sync_python(vault_dir, source_dir, cfg)

    return source_dir


def resolve_effective_backend(backend: str) -> str:
    """Return the backend that would actually be used (for ``rag doctor``)."""
    return _resolve_backend(backend)


def is_rsync_available() -> bool:
    """Check if rsync is installed and on PATH."""
    return shutil.which("rsync") is not None


# ---------------------------------------------------------------------------
# Backend resolution
# ---------------------------------------------------------------------------


def _resolve_backend(backend: str) -> str:
    """Resolve 'auto' to a concrete backend."""
    if backend == "auto":
        if platform.system() == "Windows":
            return "python"
        if is_rsync_available():
            return "rsync"
        return "python"
    if backend == "rsync" and not is_rsync_available():
        log.warning("rsync não disponível — a usar backend 'python' como fallback")
        return "python"
    return backend


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _validate_vault(vault_dir: Path) -> None:
    if not vault_dir.exists():
        raise SystemExit(
            f"Vault não encontrado: {vault_dir}\n"
            "Verifica [paths] vault_dir em rag.toml ou corre: rag init"
        )
    if not vault_dir.is_dir():
        raise SystemExit(f"vault_dir não é um directório: {vault_dir}")


# ---------------------------------------------------------------------------
# Exclusion logic (shared by python backend and direct scanning)
# ---------------------------------------------------------------------------


def _should_exclude(rel_path: Path, patterns: tuple[str, ...]) -> bool:
    """Return True if *rel_path* matches any exclusion pattern."""
    parts = rel_path.parts
    for pattern in patterns:
        # Match against any path component (directory names)
        for part in parts:
            if fnmatch(part, pattern):
                return True
        # Match against the full relative path (for file patterns like *.pdf)
        if fnmatch(rel_path.name, pattern):
            return True
    return False


def should_exclude(rel_path: Path, patterns: tuple[str, ...] | None = None) -> bool:
    """Public wrapper — uses default patterns when none provided."""
    if patterns is None:
        patterns = _DEFAULT_EXCLUDE_PATTERNS
    return _should_exclude(rel_path, patterns)


# ---------------------------------------------------------------------------
# Backend: Python (cross-platform incremental copy)
# ---------------------------------------------------------------------------


def _sync_python(
    vault_dir: Path,
    source_dir: Path,
    cfg: SyncConfig,
) -> None:
    """Incremental copy: vault_dir → source_dir using shutil."""
    patterns = cfg.exclude_patterns
    follow = cfg.follow_symlinks
    copied = 0
    skipped = 0
    deleted = 0

    print(f"==> [Sync] Python: {vault_dir} → {source_dir}")

    # Build set of valid relative paths for delete tracking
    vault_rel_paths: set[Path] = set()

    for src_file in vault_dir.rglob("*"):
        if not follow and src_file.is_symlink():
            continue
        if not src_file.is_file():
            continue

        try:
            rel = src_file.relative_to(vault_dir)
        except ValueError:
            continue

        if _should_exclude(rel, patterns):
            skipped += 1
            continue

        # Only sync .md files (Obsidian notes)
        if src_file.suffix.lower() != ".md":
            skipped += 1
            continue

        vault_rel_paths.add(rel)
        dst = source_dir / rel

        # Skip if unchanged (mtime + size check)
        if dst.exists():
            try:
                src_stat = src_file.stat()
                dst_stat = dst.stat()
                if (src_stat.st_size == dst_stat.st_size
                        and src_stat.st_mtime_ns <= dst_stat.st_mtime_ns):
                    continue
            except OSError:
                pass

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst)
        copied += 1

    # Delete files in source_dir that no longer exist in vault
    if cfg.delete_missing:
        for dst_file in source_dir.rglob("*.md"):
            try:
                rel = dst_file.relative_to(source_dir)
            except ValueError:
                continue
            if rel not in vault_rel_paths:
                dst_file.unlink()
                deleted += 1
                log.debug("Deleted orphan: %s", rel)

        # Clean empty directories
        for dirpath in sorted(source_dir.rglob("*"), reverse=True):
            if dirpath.is_dir() and not any(dirpath.iterdir()):
                dirpath.rmdir()

    print(f"    Copiados: {copied} | Ignorados: {skipped} | Removidos: {deleted}")


# ---------------------------------------------------------------------------
# Backend: rsync (Linux/macOS)
# ---------------------------------------------------------------------------


def _sync_rsync(
    vault_dir: Path,
    source_dir: Path,
    cfg: SyncConfig,
) -> None:
    """Sync via rsync subprocess."""
    cmd = [
        "rsync", "-a",
        "--include=*/",        # include directories for traversal
        "--include=*.md",      # include markdown files
        "--exclude=*",         # exclude everything else
    ]

    for pattern in cfg.exclude_patterns:
        cmd.append(f"--exclude={pattern}")

    if cfg.delete_missing:
        cmd.append("--delete")

    if not cfg.follow_symlinks:
        cmd.append("--no-links")

    # rsync requires trailing slash on source to sync contents
    cmd.append(f"{vault_dir}/")
    cmd.append(str(source_dir))

    print(f"==> [Sync] rsync: {vault_dir} → {source_dir}")
    log.debug("rsync command: %s", cmd)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        log.error("rsync stderr: %s", result.stderr)
        raise SystemExit(f"rsync falhou (exit {result.returncode}): {result.stderr.strip()}")

    print("    rsync concluído com sucesso")
