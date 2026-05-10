#!/usr/bin/env bash
# =============================================================================
# Obsidian RAG — Instalador
# Cria virtualenv, instala dependências e valida comandos.
# Uso: ./install.sh
# =============================================================================
set -euo pipefail

# --- Cores ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { printf "${GREEN}✓${NC} %s\n" "$1"; }
fail() { printf "${RED}✗${NC} %s\n" "$1"; }
warn() { printf "${YELLOW}⚠${NC} %s\n" "$1"; }

echo "╔══════════════════════════════════════╗"
echo "║     Obsidian RAG — Instalação        ║"
echo "╚══════════════════════════════════════╝"
echo

# --- 1. Python ≥ 3.11 ---
echo "─── Verificações ───"

if ! command -v python3 &>/dev/null; then
    fail "python3 não encontrado. Instala Python 3.11+: https://python.org/downloads"
    exit 1
fi

PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    fail "Python $PY_VERSION — requer ≥ 3.11"
    exit 1
fi
ok "Python $PY_VERSION"

# --- 2. Git ---
if ! command -v git &>/dev/null; then
    fail "git não encontrado. Instala Git."
    exit 1
fi
ok "Git $(git --version | awk '{print $3}')"

# --- 3. Ollama (aviso, não fatal) ---
if command -v ollama &>/dev/null; then
    ok "Ollama encontrado"
else
    warn "Ollama não encontrado — instala de https://ollama.com antes de usar"
fi

echo

# --- 4. Virtualenv ---
echo "─── Ambiente Virtual ───"
VENV_DIR=".venv"

if [ -d "$VENV_DIR" ]; then
    ok "Virtualenv já existe ($VENV_DIR)"
else
    python3 -m venv "$VENV_DIR"
    ok "Virtualenv criado ($VENV_DIR)"
fi

# Activate
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
ok "Virtualenv activado"

echo

# --- 5. Instalar ---
echo "─── Instalação ───"
pip install --upgrade pip --quiet
pip install -e . --quiet
ok "Dependências instaladas (incluindo Graphify)"

echo

# --- 6. Validar ---
echo "─── Validação ───"
if command -v rag &>/dev/null; then
    ok "Comando 'rag' disponível"
else
    # Pode estar no venv mas não no PATH se não activou
    if [ -f "$VENV_DIR/bin/rag" ]; then
        ok "Comando 'rag' disponível em $VENV_DIR/bin/rag"
    else
        fail "Comando 'rag' não encontrado após instalação"
        exit 1
    fi
fi

echo
echo "═══════════════════════════════════════"
echo "  Instalação concluída!"
echo ""
echo "  Próximos passos:"
echo "    source .venv/bin/activate"
echo "    rag init        ← configuração interactiva"
echo "    rag up           ← verificar e iniciar API"
echo ""
echo "  Outros comandos:"
echo "    rag doctor       ← diagnóstico do sistema"
echo "    rag sync --all   ← sincronizar tudo"
echo "    rag --help       ← ver todos os comandos"
echo "═══════════════════════════════════════"
