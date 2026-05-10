"""Auto-tuning de performance baseado nos recursos da máquina.

Detecta RAM, CPU, disco e GPU e ajusta limites automaticamente
quando ``[performance] auto_tune = true`` (default).
"""

from __future__ import annotations

import logging
import os
import shutil
from dataclasses import dataclass
from typing import TYPE_CHECKING

import psutil

if TYPE_CHECKING:
    from obsidian_rag.config import PerformanceConfig

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Resource detection
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResourceInfo:
    """Snapshot dos recursos disponíveis da máquina."""
    ram_total_gb: float
    ram_available_gb: float
    ram_percent: float          # % em uso
    cpu_cores: int
    cpu_percent: float          # % média actual
    disk_free_gb: float         # partição do data_dir
    gpu_nvidia: bool            # nvidia-smi encontrado


def detect_resources(data_dir: str | None = None) -> ResourceInfo:
    """Detecta recursos actuais da máquina."""
    mem = psutil.virtual_memory()
    cpu_count = psutil.cpu_count(logical=True) or 4

    # CPU percent: non-blocking snapshot (interval=None → since last call)
    try:
        cpu_pct = psutil.cpu_percent(interval=0.1)
    except Exception:
        cpu_pct = 0.0

    # Disk free on data_dir partition (fallback to home)
    disk_path = data_dir or os.path.expanduser("~")
    try:
        disk = shutil.disk_usage(disk_path)
        disk_free = disk.free / (1024 ** 3)
    except Exception:
        disk_free = 0.0

    # GPU detection — simple check for nvidia-smi binary
    gpu = shutil.which("nvidia-smi") is not None

    return ResourceInfo(
        ram_total_gb=round(mem.total / (1024 ** 3), 1),
        ram_available_gb=round(mem.available / (1024 ** 3), 1),
        ram_percent=mem.percent,
        cpu_cores=cpu_count,
        cpu_percent=cpu_pct,
        disk_free_gb=round(disk_free, 1),
        gpu_nvidia=gpu,
    )


# ---------------------------------------------------------------------------
# Auto-tune
# ---------------------------------------------------------------------------

def auto_tune(perf: "PerformanceConfig") -> "PerformanceConfig":
    """Ajusta limites de performance baseado nos recursos detectados.

    Chamado automaticamente em ``load_settings()`` quando ``auto_tune=True``.
    Retorna uma nova instância com valores ajustados.
    """
    from obsidian_rag.config import PerformanceConfig

    try:
        res = detect_resources()
    except Exception as exc:
        log.warning("Auto-tune: falha na detecção de recursos (%s) — usando defaults", exc)
        return perf

    # --- max_parallel_jobs ---
    # Conservative: at most cpu_cores // 6, capped at 4
    auto_jobs = max(1, min(res.cpu_cores // 6, 4))

    # --- embedding_batch_size ---
    # Conservative to avoid RAM spikes during Ollama embedding calls
    if res.ram_total_gb < 8:
        auto_batch = 15
    elif res.ram_total_gb < 16:
        auto_batch = 25
    else:
        auto_batch = 50

    # --- If RAM available is critically low, reduce everything ---
    if res.ram_available_gb < 4:
        auto_jobs = max(1, auto_jobs // 2)
        auto_batch = max(10, auto_batch // 2)
        log.info("Auto-tune: RAM disponível baixa (%.1f GB) — limites reduzidos", res.ram_available_gb)

    result = PerformanceConfig(
        auto_tune=True,
        max_cpu_percent=perf.max_cpu_percent,
        max_memory_percent=perf.max_memory_percent,
        max_parallel_jobs=auto_jobs,
        embedding_batch_size=auto_batch,
        embedding_timeout=perf.embedding_timeout,
        query_timeout_seconds=perf.query_timeout_seconds,
        graph_timeout=perf.graph_timeout,
        parser_workers=perf.parser_workers,
        embedding_batch_max_chars=perf.embedding_batch_max_chars,
        chunks_queue_max=perf.chunks_queue_max,
        files_queue_max=perf.files_queue_max,
        pause_memory_percent=perf.pause_memory_percent,
        abort_memory_percent=perf.abort_memory_percent,
    )

    log.info(
        "Auto-tune: RAM=%.0fGB CPU=%d cores GPU=%s → jobs=%d batch=%d",
        res.ram_total_gb, res.cpu_cores, "✓" if res.gpu_nvidia else "✗",
        result.max_parallel_jobs, result.embedding_batch_size,
    )

    return result


# ---------------------------------------------------------------------------
# Throttle advisory (used during sync)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ThrottleAdvice:
    """Advisory: should the pipeline slow down or pause?"""
    pause_sync: bool = False
    reduce_workers: bool = False
    low_disk: bool = False
    reason: str = ""


def should_throttle(perf: "PerformanceConfig", data_dir: str | None = None) -> ThrottleAdvice:
    """Verifica se o sistema está sob pressão e recomenda acção.

    Thin wrapper around :class:`ResourceGovernor` for backward compatibility.
    Creates a governor, takes a single sample, and maps the action to
    ``ThrottleAdvice``.
    """
    from obsidian_rag.pipeline.governor import GovernorAction, ResourceGovernor

    gov = ResourceGovernor(perf, data_dir=data_dir, interval=1.0)
    # Take one synchronous sample (start/stop immediately)
    gov.start()
    action = gov.check()
    snap = gov.snapshot()
    gov.stop()

    if action is GovernorAction.ABORT:
        reasons = []
        if snap and snap.disk_free_gb < 1.0:
            reasons.append(f"Disco: apenas {snap.disk_free_gb:.1f} GB livres")
        if snap and snap.ram_percent >= perf.abort_memory_percent:
            reasons.append(f"RAM {snap.ram_percent:.0f}% (abort: {perf.abort_memory_percent}%)")
        return ThrottleAdvice(
            pause_sync=True,
            low_disk=bool(snap and snap.disk_free_gb < 1.0),
            reason="; ".join(reasons) if reasons else "recursos críticos",
        )

    if action is GovernorAction.PAUSE:
        reason = f"RAM {snap.ram_percent:.0f}% (pause: {perf.pause_memory_percent}%)" if snap else ""
        return ThrottleAdvice(pause_sync=True, reason=reason)

    if action is GovernorAction.REDUCE:
        reasons = []
        if snap and snap.ram_percent >= perf.max_memory_percent:
            reasons.append(f"RAM {snap.ram_percent:.0f}% acima do limite ({perf.max_memory_percent}%)")
        if snap and snap.cpu_percent > perf.max_cpu_percent + 10:
            reasons.append(f"CPU {snap.cpu_percent:.0f}% acima do limite ({perf.max_cpu_percent}%)")
        return ThrottleAdvice(
            reduce_workers=True,
            reason="; ".join(reasons) if reasons else "",
        )

    return ThrottleAdvice()
