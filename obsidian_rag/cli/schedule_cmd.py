"""``rag schedule`` — cross-platform scheduled sync helper.

Generates and installs OS-appropriate scheduled tasks:
  - Linux: systemd user timer
  - macOS: launchd user agent (plist)
  - Windows: schtasks.exe scheduled task

Usage:
    rag schedule install   Install daily sync schedule
    rag schedule remove    Remove installed schedule
    rag schedule status    Show current schedule status
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

from obsidian_rag.config import PROJECT_ROOT

_SYSTEM = platform.system()
_SERVICE_NAME = "obsidian-rag-sync"
_SCHEDULE_TIME = "04:00"  # daily at 4 AM


def _find_rag_binary() -> str:
    """Find the rag command path."""
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        if _SYSTEM == "Windows":
            candidate = Path(venv) / "Scripts" / "rag.exe"
        else:
            candidate = Path(venv) / "bin" / "rag"
        if candidate.exists():
            return str(candidate)
    return "rag"


# ---------------------------------------------------------------------------
# Linux: systemd user timer
# ---------------------------------------------------------------------------

_SYSTEMD_SERVICE = """[Unit]
Description=Obsidian RAG — sync embeddings and graphs
After=network.target

[Service]
Type=oneshot
WorkingDirectory={project_root}
ExecStart={rag_bin} sync --all
Environment="PATH={venv_bin}:%h/.local/bin:/usr/local/bin:/usr/bin:/bin"

[Install]
WantedBy=default.target
"""

_SYSTEMD_TIMER = """[Unit]
Description=Obsidian RAG — daily sync timer

[Timer]
OnCalendar=*-*-* {time}
Persistent=true

[Install]
WantedBy=timers.target
"""


def _systemd_dir() -> Path:
    return Path.home() / ".config" / "systemd" / "user"


def _install_linux() -> None:
    sd = _systemd_dir()
    sd.mkdir(parents=True, exist_ok=True)

    rag_bin = _find_rag_binary()
    venv_bin = str(Path(rag_bin).parent) if "/" in rag_bin else ""

    service_path = sd / f"{_SERVICE_NAME}.service"
    timer_path = sd / f"{_SERVICE_NAME}.timer"

    service_path.write_text(
        _SYSTEMD_SERVICE.format(
            project_root=PROJECT_ROOT,
            rag_bin=rag_bin,
            venv_bin=venv_bin,
        ),
        encoding="utf-8",
    )
    timer_path.write_text(
        _SYSTEMD_TIMER.format(time=_SCHEDULE_TIME),
        encoding="utf-8",
    )

    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    subprocess.run(["systemctl", "--user", "enable", "--now", f"{_SERVICE_NAME}.timer"], check=True)

    print(f"✓ Timer systemd instalado: {timer_path}")
    print(f"  Sync diário às {_SCHEDULE_TIME}")
    print(f"  Verificar: systemctl --user status {_SERVICE_NAME}.timer")


def _remove_linux() -> None:
    subprocess.run(["systemctl", "--user", "disable", "--now", f"{_SERVICE_NAME}.timer"], check=False)
    sd = _systemd_dir()
    for f in [f"{_SERVICE_NAME}.service", f"{_SERVICE_NAME}.timer"]:
        p = sd / f
        if p.exists():
            p.unlink()
    subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
    print("✓ Timer systemd removido")


def _status_linux() -> None:
    result = subprocess.run(
        ["systemctl", "--user", "status", f"{_SERVICE_NAME}.timer"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"Timer '{_SERVICE_NAME}' não está instalado ou activo.")


# ---------------------------------------------------------------------------
# macOS: launchd user agent
# ---------------------------------------------------------------------------

_LAUNCHD_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.obsidian-rag.sync</string>
    <key>ProgramArguments</key>
    <array>
        <string>{rag_bin}</string>
        <string>sync</string>
        <string>--all</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{project_root}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>{hour}</integer>
        <key>Minute</key>
        <integer>{minute}</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>{log_dir}/obsidian-rag-sync.log</string>
    <key>StandardErrorPath</key>
    <string>{log_dir}/obsidian-rag-sync.err</string>
</dict>
</plist>
"""


def _launchd_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / "com.obsidian-rag.sync.plist"


def _install_macos() -> None:
    plist_path = _launchd_path()
    plist_path.parent.mkdir(parents=True, exist_ok=True)

    rag_bin = _find_rag_binary()
    hour, minute = _SCHEDULE_TIME.split(":")
    log_dir = Path.home() / "Library" / "Logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    plist_path.write_text(
        _LAUNCHD_PLIST.format(
            rag_bin=rag_bin,
            project_root=PROJECT_ROOT,
            hour=int(hour),
            minute=int(minute),
            log_dir=log_dir,
        ),
        encoding="utf-8",
    )

    subprocess.run(["launchctl", "load", str(plist_path)], check=True)
    print(f"✓ LaunchAgent instalado: {plist_path}")
    print(f"  Sync diário às {_SCHEDULE_TIME}")


def _remove_macos() -> None:
    plist_path = _launchd_path()
    if plist_path.exists():
        subprocess.run(["launchctl", "unload", str(plist_path)], check=False)
        plist_path.unlink()
    print("✓ LaunchAgent removido")


def _status_macos() -> None:
    result = subprocess.run(
        ["launchctl", "list", "com.obsidian-rag.sync"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"LaunchAgent activo:\n{result.stdout}")
    else:
        print("LaunchAgent 'com.obsidian-rag.sync' não está instalado.")


# ---------------------------------------------------------------------------
# Windows: schtasks.exe
# ---------------------------------------------------------------------------

_TASK_NAME = "ObsidianRAGSync"


def _install_windows() -> None:
    rag_bin = _find_rag_binary()

    # schtasks /Create — daily at configured time
    cmd = [
        "schtasks", "/Create",
        "/TN", _TASK_NAME,
        "/TR", f'"{rag_bin}" sync --all',
        "/SC", "DAILY",
        "/ST", _SCHEDULE_TIME,
        "/F",  # force overwrite
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"✓ Scheduled Task criada: {_TASK_NAME}")
        print(f"  Sync diário às {_SCHEDULE_TIME}")
        print(f"  Verificar: schtasks /Query /TN {_TASK_NAME}")
    else:
        print(f"✗ Falha ao criar Scheduled Task: {result.stderr.strip()}")
        sys.exit(1)


def _remove_windows() -> None:
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", _TASK_NAME, "/F"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(f"✓ Scheduled Task removida: {_TASK_NAME}")
    else:
        print(f"Task '{_TASK_NAME}' não encontrada.")


def _status_windows() -> None:
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", _TASK_NAME, "/V", "/FO", "LIST"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        print(result.stdout)
    else:
        print(f"Task '{_TASK_NAME}' não está instalada.")


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_HANDLERS = {
    "Linux": (_install_linux, _remove_linux, _status_linux),
    "Darwin": (_install_macos, _remove_macos, _status_macos),
    "Windows": (_install_windows, _remove_windows, _status_windows),
}


def run_schedule(args: Namespace) -> None:
    action = args.schedule_command
    if not action:
        print("Uso: rag schedule {install|remove|status}")
        sys.exit(1)

    handlers = _HANDLERS.get(_SYSTEM)
    if not handlers:
        print(f"✗ Sistema operativo não suportado para agendamento: {_SYSTEM}")
        sys.exit(1)

    install_fn, remove_fn, status_fn = handlers

    if action == "install":
        install_fn()
    elif action == "remove":
        remove_fn()
    elif action == "status":
        status_fn()
    else:
        print(f"Acção desconhecida: {action}")
        sys.exit(1)
