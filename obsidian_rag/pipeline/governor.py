"""Resource Governor — background monitor with graduated throttle levels.

Provides a single ``ResourceGovernor`` that runs a lightweight psutil
probe every *interval* seconds and exposes ``check()`` which returns the
current ``GovernorAction``.  The pipeline queries this instead of
re-sampling system resources on every batch.

Three thresholds drive the decision:

  max_memory_percent   → REDUCE  (lower concurrency)
  pause_memory_percent → PAUSE   (wait until safe)
  abort_memory_percent → ABORT   (fatal, stop pipeline)

CPU-only pressure triggers REDUCE; disk-full always triggers ABORT.

An optional JSONL metrics file records every sample for post-mortem
analysis.
"""

from __future__ import annotations

import json
import logging
import shutil
import threading
import time
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

import psutil

if TYPE_CHECKING:
    from obsidian_rag.config import PerformanceConfig

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------

class GovernorAction(Enum):
    """What the pipeline should do right now."""
    CONTINUE = auto()   # all good
    REDUCE = auto()     # lower concurrency / smaller batches
    PAUSE = auto()      # wait until resources free up
    ABORT = auto()      # fatal — stop immediately


@dataclass(frozen=True)
class ResourceSnapshot:
    """Point-in-time system resource readings."""
    ram_percent: float
    ram_available_gb: float
    cpu_percent: float
    disk_free_gb: float
    timestamp: float        # time.monotonic()


# ---------------------------------------------------------------------------
# Governor
# ---------------------------------------------------------------------------

class ResourceGovernor:
    """Background resource monitor with graduated throttle levels.

    Usage::

        gov = ResourceGovernor(perf, data_dir="/path/to/data")
        gov.start()
        try:
            action = gov.check()
            if action is GovernorAction.PAUSE:
                gov.wait_until_safe(timeout=60)
            ...
        finally:
            gov.stop()

    The monitor thread runs every *interval* seconds (default 1 s) and
    updates an internal snapshot.  ``check()`` reads the latest snapshot
    without blocking on I/O — it is safe to call from hot loops.
    """

    def __init__(
        self,
        perf: "PerformanceConfig",
        *,
        data_dir: str | Path | None = None,
        interval: float = 1.0,
        metrics_path: str | Path | None = None,
    ) -> None:
        self._perf = perf
        self._data_dir = str(data_dir) if data_dir else None
        self._interval = max(0.25, interval)
        self._metrics_path = Path(metrics_path) if metrics_path else None

        # Latest snapshot (written by monitor, read by check())
        self._snapshot: ResourceSnapshot | None = None
        self._lock = threading.Lock()

        # Monitor lifecycle
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

        # Metrics file handle (opened lazily)
        self._metrics_fh = None

    # -- lifecycle --

    def start(self) -> None:
        """Start the background monitor thread."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        # Take an initial sample synchronously so check() works immediately
        self._sample()
        self._thread = threading.Thread(
            target=self._monitor_loop,
            name="resource-governor",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        """Signal the monitor thread to stop and wait for it."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        if self._metrics_fh is not None:
            try:
                self._metrics_fh.close()
            except Exception:
                pass
            self._metrics_fh = None

    # -- public API --

    def check(self) -> GovernorAction:
        """Return the recommended action based on the latest snapshot.

        This is a non-blocking read — no system calls.
        """
        with self._lock:
            snap = self._snapshot

        if snap is None:
            return GovernorAction.CONTINUE

        return self._evaluate(snap)

    def snapshot(self) -> ResourceSnapshot | None:
        """Return the most recent snapshot (or None if not started)."""
        with self._lock:
            return self._snapshot

    def wait_until_safe(self, timeout: float = 60.0) -> GovernorAction:
        """Block until the action is CONTINUE or REDUCE, or *timeout* expires.

        Returns the final action after waiting.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            action = self.check()
            if action in (GovernorAction.CONTINUE, GovernorAction.REDUCE):
                return action
            if action is GovernorAction.ABORT:
                return action
            # PAUSE — keep waiting
            time.sleep(self._interval)
        return self.check()

    # -- internals --

    def _monitor_loop(self) -> None:
        """Background loop — samples resources every *interval* seconds."""
        while not self._stop_event.is_set():
            try:
                self._sample()
            except Exception as exc:
                log.debug("Governor sample error: %s", exc)
            self._stop_event.wait(self._interval)

    def _sample(self) -> None:
        """Take a single resource snapshot and store it."""
        mem = psutil.virtual_memory()
        try:
            cpu = psutil.cpu_percent(interval=None)
        except Exception:
            cpu = 0.0

        disk_free = 0.0
        if self._data_dir:
            try:
                du = shutil.disk_usage(self._data_dir)
                disk_free = du.free / (1024 ** 3)
            except Exception:
                pass

        snap = ResourceSnapshot(
            ram_percent=mem.percent,
            ram_available_gb=round(mem.available / (1024 ** 3), 2),
            cpu_percent=cpu,
            disk_free_gb=round(disk_free, 2),
            timestamp=time.monotonic(),
        )

        with self._lock:
            self._snapshot = snap

        self._emit_metrics(snap)

    def _evaluate(self, snap: ResourceSnapshot) -> GovernorAction:
        """Decide action from a snapshot and the configured thresholds."""
        # Disk-full is always fatal
        if self._data_dir and snap.disk_free_gb < 1.0:
            return GovernorAction.ABORT

        # RAM thresholds (ordered most severe → least severe)
        if snap.ram_percent >= self._perf.abort_memory_percent:
            return GovernorAction.ABORT
        if snap.ram_percent >= self._perf.pause_memory_percent:
            return GovernorAction.PAUSE
        if snap.ram_percent >= self._perf.max_memory_percent:
            return GovernorAction.REDUCE

        # CPU-only pressure → reduce
        if snap.cpu_percent > self._perf.max_cpu_percent + 10:
            return GovernorAction.REDUCE

        return GovernorAction.CONTINUE

    # -- metrics --

    def _emit_metrics(self, snap: ResourceSnapshot) -> None:
        """Append a JSONL line to the metrics file (if configured)."""
        if self._metrics_path is None:
            return
        try:
            if self._metrics_fh is None:
                self._metrics_path.parent.mkdir(parents=True, exist_ok=True)
                self._metrics_fh = open(self._metrics_path, "a", encoding="utf-8")  # noqa: SIM115

            record = {
                "ts": time.time(),
                "ram_pct": snap.ram_percent,
                "ram_avail_gb": snap.ram_available_gb,
                "cpu_pct": snap.cpu_percent,
                "disk_free_gb": snap.disk_free_gb,
                "action": self._evaluate(snap).name,
            }
            self._metrics_fh.write(json.dumps(record) + "\n")
            self._metrics_fh.flush()
        except Exception as exc:
            log.debug("Metrics write error: %s", exc)
