"""SQLite manifest for incremental ingest — tracks files, chunks, and runs.

Enables crash recovery: if sync is interrupted, the next run resumes
from the last checkpoint instead of reprocessing everything.
"""

from __future__ import annotations

import hashlib
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True)
class FileRecord:
    path: str
    repo: str
    mtime: float
    size: int
    sha256: str
    status: str
    chunk_count: int
    last_indexed_at: str


_SCHEMA = """\
CREATE TABLE IF NOT EXISTS files (
    path            TEXT PRIMARY KEY,
    repo            TEXT NOT NULL,
    mtime           REAL NOT NULL,
    size            INTEGER NOT NULL,
    sha256          TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'indexed',
    chunk_count     INTEGER NOT NULL DEFAULT 0,
    last_indexed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id      TEXT PRIMARY KEY,
    file_path     TEXT NOT NULL,
    repo          TEXT NOT NULL,
    chunk_hash    TEXT NOT NULL,
    vector_status TEXT NOT NULL DEFAULT 'pending',
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (file_path) REFERENCES files(path) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ingest_runs (
    run_id      TEXT PRIMARY KEY,
    started_at  TEXT NOT NULL DEFAULT (datetime('now')),
    finished_at TEXT,
    status      TEXT NOT NULL DEFAULT 'running',
    error       TEXT
);

CREATE INDEX IF NOT EXISTS idx_chunks_file ON chunks(file_path);
CREATE INDEX IF NOT EXISTS idx_chunks_repo ON chunks(repo);
CREATE INDEX IF NOT EXISTS idx_chunks_status ON chunks(vector_status);
CREATE INDEX IF NOT EXISTS idx_files_repo ON files(repo);
"""


class IngestManifest:
    """SQLite-backed manifest for tracking ingest state.

    Uses WAL mode for concurrent read safety and transactional writes.
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._conn: sqlite3.Connection | None = None
        self._lock = threading.Lock()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                self._db_path,
                timeout=10,
                check_same_thread=False,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.executescript(_SCHEMA)
        return self._conn

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Cursor]:
        """Transaction context manager — auto-commit on success, rollback on error."""
        with self._lock:
            conn = self._get_conn()
            cursor = conn.cursor()
            try:
                yield cursor
                conn.commit()
            except Exception:
                conn.rollback()
                raise

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    # -- Runs --

    def start_run(self) -> str:
        """Create a new ingest run and return its ID."""
        run_id = uuid.uuid4().hex[:12]
        with self._tx() as cur:
            cur.execute(
                "INSERT INTO ingest_runs (run_id, status) VALUES (?, 'running')",
                (run_id,),
            )
        return run_id

    def finish_run(self, run_id: str, status: str = "completed", error: str | None = None) -> None:
        with self._tx() as cur:
            cur.execute(
                "UPDATE ingest_runs SET finished_at = datetime('now'), status = ?, error = ? WHERE run_id = ?",
                (status, error, run_id),
            )

    def get_last_incomplete_run(self) -> str | None:
        """Return the run_id of the last incomplete run, if any."""
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT run_id FROM ingest_runs WHERE status = 'running' ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        return row[0] if row else None

    # -- Files --

    def needs_reindex(self, path: str, mtime: float, size: int, sha256: str) -> bool:
        """Return True if file is new or has changed since last index."""
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT mtime, size, sha256 FROM files WHERE path = ?",
                (path,),
            ).fetchone()
        if row is None:
            return True
        return row[0] != mtime or row[1] != size or row[2] != sha256

    def record_file(
        self,
        path: str,
        repo: str,
        mtime: float,
        size: int,
        sha256: str,
        chunk_count: int,
    ) -> None:
        """Upsert a file record after successful indexing."""
        with self._tx() as cur:
            cur.execute(
                """INSERT INTO files (path, repo, mtime, size, sha256, status, chunk_count, last_indexed_at)
                   VALUES (?, ?, ?, ?, ?, 'indexed', ?, datetime('now'))
                   ON CONFLICT(path) DO UPDATE SET
                     repo = excluded.repo,
                     mtime = excluded.mtime,
                     size = excluded.size,
                     sha256 = excluded.sha256,
                     status = 'indexed',
                     chunk_count = excluded.chunk_count,
                     last_indexed_at = datetime('now')""",
                (path, repo, mtime, size, sha256, chunk_count),
            )

    def get_indexed_files(self, repo: str) -> set[str]:
        """Return set of file paths currently indexed for a repo."""
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute("SELECT path FROM files WHERE repo = ?", (repo,)).fetchall()
        return {r[0] for r in rows}

    # -- Chunks --

    def record_chunks(self, chunk_ids: list[str], file_path: str, repo: str, chunk_hashes: list[str]) -> None:
        """Batch insert chunk records for a file, replacing any previous chunks for that file."""
        with self._tx() as cur:
            # Remove old chunks for this file
            cur.execute("DELETE FROM chunks WHERE file_path = ?", (file_path,))
            cur.executemany(
                "INSERT INTO chunks (chunk_id, file_path, repo, chunk_hash) VALUES (?, ?, ?, ?)",
                [(cid, file_path, repo, ch) for cid, ch in zip(chunk_ids, chunk_hashes)],
            )

    def mark_chunks_embedded(self, chunk_ids: list[str]) -> None:
        """Mark chunks as successfully embedded in the vector store."""
        if not chunk_ids:
            return
        with self._tx() as cur:
            placeholders = ",".join("?" for _ in chunk_ids)
            cur.execute(
                f"UPDATE chunks SET vector_status = 'embedded' WHERE chunk_id IN ({placeholders})",  # noqa: S608  # nosec B608
                chunk_ids,
            )

    def get_chunk_ids_for_repo(self, repo: str) -> set[str]:
        """Return all chunk IDs currently tracked for a repo."""
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute("SELECT chunk_id FROM chunks WHERE repo = ?", (repo,)).fetchall()
        return {r[0] for r in rows}

    def get_stale_chunks(self, repo: str, valid_ids: set[str]) -> set[str]:
        """Return chunk IDs in the manifest that are NOT in valid_ids."""
        current = self.get_chunk_ids_for_repo(repo)
        return current - valid_ids

    def delete_stale_files(self, repo: str, valid_paths: set[str]) -> list[str]:
        """Remove files no longer present in repo. Returns deleted chunk IDs."""
        indexed = self.get_indexed_files(repo)
        stale = indexed - valid_paths
        if not stale:
            return []
        deleted_chunk_ids: list[str] = []
        with self._tx() as cur:
            for path in stale:
                rows = cur.execute("SELECT chunk_id FROM chunks WHERE file_path = ?", (path,)).fetchall()
                deleted_chunk_ids.extend(r[0] for r in rows)
                cur.execute("DELETE FROM chunks WHERE file_path = ?", (path,))
                cur.execute("DELETE FROM files WHERE path = ?", (path,))
        return deleted_chunk_ids

    def delete_chunks(self, chunk_ids: list[str]) -> None:
        """Remove specific chunks from the manifest."""
        if not chunk_ids:
            return
        with self._tx() as cur:
            placeholders = ",".join("?" for _ in chunk_ids)
            cur.execute(
                f"DELETE FROM chunks WHERE chunk_id IN ({placeholders})",  # noqa: S608  # nosec B608
                chunk_ids,
            )

    # -- Utilities --

    @staticmethod
    def file_sha256(path: str | Path) -> str:
        """Compute SHA256 of a file's contents (first 64KB for speed)."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            # Read first 64KB — sufficient for change detection, fast for large files
            h.update(f.read(65536))
        return h.hexdigest()[:16]

    def stats(self) -> dict[str, int]:
        """Return summary stats."""
        with self._lock:
            conn = self._get_conn()
            files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
            embedded = conn.execute("SELECT COUNT(*) FROM chunks WHERE vector_status = 'embedded'").fetchone()[0]
            runs = conn.execute("SELECT COUNT(*) FROM ingest_runs").fetchone()[0]
        return {"files": files, "chunks": chunks, "embedded": embedded, "runs": runs}
