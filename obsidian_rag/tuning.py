"""Auto-tuning de performance baseado nos recursos da máquina.

Detecta RAM, CPU, disco e GPU e ajusta limites automaticamente
quando ``[performance] auto_tune = true`` (default).
"""

from __future__ import annotations

import logging
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
    disk_path = data_dir or str(shutil.os.path.expanduser("~"))
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
    auto_jobs = max(1, min(res.cpu_cores // 4, 8))

    # --- embedding_batch_size ---
    if res.ram_total_gb < 8:
        auto_batch = 25
    elif res.ram_total_gb < 16:
        auto_batch = 50
    else:
        auto_batch = 100

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
        query_timeout_seconds=perf.query_timeout_seconds,
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

    Chamado antes de cada repo no sync pipeline.
    """
    try:
        res = detect_resources(data_dir)
    except Exception:
        return ThrottleAdvice()

    reasons: list[str] = []
    pause = False
    reduce = False
    low_disk = False

    if res.ram_percent > perf.max_memory_percent + 10:
        # Critical: >10% above threshold
        pause = True
        reasons.append(f"RAM {res.ram_percent:.0f}% (limite: {perf.max_memory_percent}%)")
    elif res.ram_percent > perf.max_memory_percent:
        reduce = True
        reasons.append(f"RAM {res.ram_percent:.0f}% acima do limite ({perf.max_memory_percent}%)")

    if res.cpu_percent > perf.max_cpu_percent + 10:
        reduce = True
        reasons.append(f"CPU {res.cpu_percent:.0f}% acima do limite ({perf.max_cpu_percent}%)")

    if res.disk_free_gb < 1.0:
        low_disk = True
        reasons.append(f"Disco: apenas {res.disk_free_gb:.1f} GB livres")

    return ThrottleAdvice(
        pause_sync=pause,
        reduce_workers=reduce,
        low_disk=low_disk,
        reason="; ".join(reasons) if reasons else "",
    )
