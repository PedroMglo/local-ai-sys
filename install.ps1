# =============================================================================
# Obsidian RAG — Windows Installer (PowerShell)
# Creates virtualenv, installs dependencies, validates commands.
# Usage: .\install.ps1
# =============================================================================
$ErrorActionPreference = "Stop"

function Write-Ok($msg)   { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Write-Fail($msg) { Write-Host "  ✗ $msg" -ForegroundColor Red }
function Write-Warn($msg) { Write-Host "  ⚠ $msg" -ForegroundColor Yellow }

Write-Host "╔══════════════════════════════════════╗"
Write-Host "║     Obsidian RAG — Instalação        ║"
Write-Host "╚══════════════════════════════════════╝"
Write-Host ""

# --- 1. Python >= 3.11 ---
Write-Host "─── Verificações ───"
$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($LASTEXITCODE -eq 0) {
            $major, $minor = $ver -split '\.'
            if ([int]$major -ge 3 -and [int]$minor -ge 11) {
                $pythonCmd = $cmd
                break
            }
        }
    } catch {}
}

if (-not $pythonCmd) {
    Write-Fail "Python 3.11+ não encontrado. Instala de https://python.org/downloads"
    exit 1
}
Write-Ok "Python $ver ($pythonCmd)"

# --- 2. Git ---
try {
    $gitVer = git --version 2>$null
    if ($LASTEXITCODE -eq 0) {
        Write-Ok "Git ($gitVer)"
    } else { throw }
} catch {
    Write-Fail "Git não encontrado. Instala de https://git-scm.com"
    exit 1
}

# --- 3. Ollama (aviso, não fatal) ---
try {
    $null = Get-Command ollama -ErrorAction Stop
    Write-Ok "Ollama encontrado"
} catch {
    Write-Warn "Ollama não encontrado — instala de https://ollama.com antes de usar"
}

Write-Host ""

# --- 4. Virtualenv ---
Write-Host "─── Ambiente Virtual ───"
$venvDir = ".venv"

if (Test-Path $venvDir) {
    Write-Ok "Virtualenv já existe ($venvDir)"
} else {
    & $pythonCmd -m venv $venvDir
    Write-Ok "Virtualenv criado ($venvDir)"
}

# Activate
$activateScript = Join-Path $venvDir "Scripts\Activate.ps1"
if (Test-Path $activateScript) {
    . $activateScript
    Write-Ok "Virtualenv activado"
} else {
    Write-Fail "Não foi possível activar o virtualenv ($activateScript)"
    exit 1
}

Write-Host ""

# --- 5. Instalar ---
Write-Host "─── Instalação ───"
pip install --upgrade pip --quiet 2>$null
pip install -e . --quiet
Write-Ok "Dependências instaladas"

Write-Host ""

# --- 6. Validar ---
Write-Host "─── Validação ───"
$ragCmd = Join-Path $venvDir "Scripts\rag.exe"
if (Test-Path $ragCmd) {
    Write-Ok "Comando 'rag' disponível ($ragCmd)"
} else {
    try {
        $null = Get-Command rag -ErrorAction Stop
        Write-Ok "Comando 'rag' disponível"
    } catch {
        Write-Fail "Comando 'rag' não encontrado após instalação"
        exit 1
    }
}

Write-Host ""
Write-Host "═══════════════════════════════════════"
Write-Host "  Instalação concluída!"
Write-Host ""
Write-Host "  Próximos passos:"
Write-Host "    .venv\Scripts\Activate.ps1"
Write-Host "    rag init        ← configuração interactiva"
Write-Host "    rag up           ← verificar e iniciar API"
Write-Host ""
Write-Host "  Outros comandos:"
Write-Host "    rag doctor       ← diagnóstico do sistema"
Write-Host "    rag sync --all   ← sincronizar tudo"
Write-Host "    rag --help       ← ver todos os comandos"
Write-Host "═══════════════════════════════════════"
