"""Real-time system context collector.

Executes safe, read-only commands to gather live machine state
(RAM, GPU, CPU, disk, processes) and formats the output for
injection into the LLM context window.

All commands are:
- Read-only (no writes, no sudo)
- Timeout-limited (default 5s per command)
- Failure-tolerant (graceful skip on error)
"""

from __future__ import annotations

import logging
import subprocess
import typing

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Keyword → subsystem mapping
# ---------------------------------------------------------------------------

_SUBSYSTEM_KEYWORDS: dict[str, set[str]] = {
    "memory": {
        "ram", "memória", "memory", "swap", "livre", "free",
        "disponível", "available", "usada", "used",
    },
    "gpu": {
        "gpu", "vram", "nvidia", "cuda", "amd",
        "gráfica", "graphics",
    },
    "disk": {
        "disco", "disk", "storage", "armazenamento",
        "espaço", "space", "ssd", "hdd", "nvme",
    },
    "cpu": {
        "cpu", "processador", "processor", "carga", "load",
        "uptime", "cores", "threads",
    },
    "processes": {
        "processos", "processes", "correr", "running",
        "consumir", "consuming", "usando", "using",
    },
    "system": {
        "sistema", "system", "kernel", "driver", "drivers",
        "máquina", "machine", "pc", "computador", "computer",
        "hardware",
    },
    "network": {
        "rede", "network", "ip", "interface",
    },
    "temperature": {
        "temperatura", "temperature", "temp",
    },
}


def _detect_subsystems(query: str) -> set[str]:
    """Detect which subsystems the query asks about."""
    q_lower = query.lower()
    words = {w.strip(".,!?:;\"'()[]{}") for w in q_lower.split()}

    found: set[str] = set()
    for subsystem, keywords in _SUBSYSTEM_KEYWORDS.items():
        if words & keywords:
            found.add(subsystem)

    # If nothing specific matched but we're here (SYSTEM route), collect basics
    if not found:
        found = {"memory", "cpu", "disk"}

    return found


def _run_cmd(cmd: list[str], timeout: int = 5) -> str:
    """Run a command and return stdout, or empty string on failure."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        log.debug("System command failed: %s — %s", cmd, exc)
        return ""


# ---------------------------------------------------------------------------
# Subsystem collectors
# ---------------------------------------------------------------------------

def _collect_memory() -> str:
    out = _run_cmd(["free", "-h"])
    return f"## Memory\n```\n{out}\n```" if out else ""


def _collect_gpu() -> str:
    out = _run_cmd([
        "nvidia-smi",
        "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
        "--format=csv,noheader",
    ])
    if out:
        return f"## GPU (nvidia-smi)\n```\n{out}\n```"

    # Fallback: try basic nvidia-smi
    out = _run_cmd(["nvidia-smi", "--query-gpu=name,memory.used,memory.total", "--format=csv,noheader"])
    if out:
        return f"## GPU (nvidia-smi)\n```\n{out}\n```"

    return ""


def _collect_disk() -> str:
    out = _run_cmd(["df", "-h", "--output=source,size,used,avail,pcent", "/", "/home"])
    return f"## Disk\n```\n{out}\n```" if out else ""


def _collect_cpu() -> str:
    parts: list[str] = []
    uptime = _run_cmd(["uptime"])
    if uptime:
        parts.append(f"Uptime/Load: {uptime}")
    nproc = _run_cmd(["nproc"])
    if nproc:
        parts.append(f"Cores: {nproc}")
    if parts:
        return "## CPU\n```\n" + "\n".join(parts) + "\n```"
    return ""


def _collect_processes() -> str:
    out = _run_cmd(["ps", "aux", "--sort=-%cpu"])
    if out:
        lines = out.split("\n")[:8]  # header + top 7
        return "## Top processes (by CPU)\n```\n" + "\n".join(lines) + "\n```"
    return ""


def _collect_system() -> str:
    uname = _run_cmd(["uname", "-a"])
    return f"## System\n```\n{uname}\n```" if uname else ""


def _collect_network() -> str:
    out = _run_cmd(["ip", "-br", "addr"])
    if out:
        lines = out.split("\n")[:6]
        return "## Network\n```\n" + "\n".join(lines) + "\n```"
    return ""


def _collect_temperature() -> str:
    # Try nvidia-smi for GPU temp
    gpu_temp = _run_cmd([
        "nvidia-smi", "--query-gpu=name,temperature.gpu",
        "--format=csv,noheader",
    ])
    parts: list[str] = []
    if gpu_temp:
        parts.append(f"GPU: {gpu_temp}°C")

    # Try sensors for CPU/system temps
    sensors = _run_cmd(["sensors"])
    if sensors:
        # Extract just temp lines
        temp_lines = [line for line in sensors.split("\n") if "°C" in line or "temp" in line.lower()]
        if temp_lines:
            parts.extend(temp_lines[:5])

    if parts:
        return "## Temperature\n```\n" + "\n".join(parts) + "\n```"
    return ""


# ---------------------------------------------------------------------------
# Collector dispatch
# ---------------------------------------------------------------------------

_COLLECTORS: dict[str, typing.Callable[[], str]] = {
    "memory": _collect_memory,
    "gpu": _collect_gpu,
    "disk": _collect_disk,
    "cpu": _collect_cpu,
    "processes": _collect_processes,
    "system": _collect_system,
    "network": _collect_network,
    "temperature": _collect_temperature,
}


def collect_system_context(query: str, *, timeout: int = 5) -> str:
    """Collect live system state relevant to the query.

    Returns a formatted markdown string under [SYSTEM — LIVE STATE] labels,
    or empty string if no data could be collected.
    """
    subsystems = _detect_subsystems(query)
    log.info("System context: collecting %s", ", ".join(sorted(subsystems)))

    sections: list[str] = []
    for name in ("system", "cpu", "memory", "gpu", "disk", "processes", "network", "temperature"):
        if name not in subsystems:
            continue
        collector = _COLLECTORS.get(name)
        if collector:
            section = collector()
            if section:
                sections.append(section)

    if not sections:
        return ""

    import datetime
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = f"[SYSTEM — LIVE STATE] (collected at {timestamp})"
    footer = "[/SYSTEM — LIVE STATE]"

    return header + "\n\n" + "\n\n".join(sections) + "\n\n" + footer
