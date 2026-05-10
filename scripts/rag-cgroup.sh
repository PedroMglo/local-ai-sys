#!/usr/bin/env bash
# rag-cgroup.sh — Run rag-sync inside a systemd resource scope.
#
# Uses systemd-run --user --scope to apply MemoryMax and CPUQuota limits
# so that the ingest pipeline cannot starve the rest of the desktop.
#
# Usage:
#   ./scripts/rag-cgroup.sh              # defaults: 60% RAM, 75% CPU
#   ./scripts/rag-cgroup.sh --mem 50 --cpu 50
#   RAG_MEM_PCT=70 RAG_CPU_PCT=80 ./scripts/rag-cgroup.sh
#
# Requirements: systemd ≥ 240, cgroup v2 (default on Ubuntu 22.04+/Zorin 17+).
# Falls back to plain execution if systemd-run is unavailable.

set -euo pipefail

# ---------------------------------------------------------------------------
# Defaults (overridable via env or flags)
# ---------------------------------------------------------------------------
MEM_PCT="${RAG_MEM_PCT:-60}"      # % of total RAM
CPU_PCT="${RAG_CPU_PCT:-75}"      # % of total CPU (100 = 1 full core)

# ---------------------------------------------------------------------------
# Parse CLI flags
# ---------------------------------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        --mem)  MEM_PCT="$2"; shift 2 ;;
        --cpu)  CPU_PCT="$2"; shift 2 ;;
        -h|--help)
            echo "Usage: $0 [--mem PCT] [--cpu PCT]"
            echo "  --mem PCT   Max memory as % of total RAM (default: 60)"
            echo "  --cpu PCT   Max CPU quota as % of total logical CPUs (default: 75)"
            exit 0
            ;;
        *)  echo "Unknown flag: $1"; exit 1 ;;
    esac
done

# ---------------------------------------------------------------------------
# Calculate absolute limits
# ---------------------------------------------------------------------------
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
MEM_MAX=$(( TOTAL_RAM_KB * 1024 * MEM_PCT / 100 ))   # bytes

NCPU=$(nproc)
CPU_QUOTA=$(( NCPU * CPU_PCT ))                       # e.g. 24 cores × 75% = 1800%

echo "==> rag-cgroup: MemoryMax=${MEM_MAX} bytes (${MEM_PCT}% of $(( TOTAL_RAM_KB / 1024 )) MB)"
echo "==> rag-cgroup: CPUQuota=${CPU_QUOTA}% (${CPU_PCT}% of ${NCPU} cores)"

# ---------------------------------------------------------------------------
# Locate rag-sync
# ---------------------------------------------------------------------------
RAG_SYNC="rag-sync"
if ! command -v "$RAG_SYNC" &>/dev/null; then
    # Try the project venv
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
    if [[ -x "$PROJECT_DIR/.venv/bin/rag-sync" ]]; then
        RAG_SYNC="$PROJECT_DIR/.venv/bin/rag-sync"
    else
        echo "✗ rag-sync not found in PATH or .venv/bin. Install with: pip install -e ."
        exit 1
    fi
fi

# ---------------------------------------------------------------------------
# Execute under systemd scope (or fallback)
# ---------------------------------------------------------------------------
if command -v systemd-run &>/dev/null && [[ -d /sys/fs/cgroup/user.slice ]]; then
    exec systemd-run --user --scope \
        --unit="rag-sync-$(date +%s)" \
        -p MemoryMax="$MEM_MAX" \
        -p CPUQuota="${CPU_QUOTA}%" \
        "$RAG_SYNC" --all
else
    echo "⚠ systemd-run or cgroup v2 not available — running without resource limits."
    exec "$RAG_SYNC" --all
fi
