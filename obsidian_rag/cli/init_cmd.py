"""``rag init`` — interactive setup wizard for rag.toml."""

from __future__ import annotations

import os
import secrets
import sys
from argparse import Namespace
from pathlib import Path

from obsidian_rag.config import PROJECT_ROOT, config_exists

# Paths that must never be indexed
_DANGEROUS_PATHS = frozenset({
    "/", "/bin", "/boot", "/dev", "/etc", "/lib", "/proc", "/root",
    "/sbin", "/sys", "/tmp", "/usr", "/var",
})

_SENSITIVE_SUFFIXES = frozenset({
    ".ssh", ".gnupg", ".cache", ".local/share/Trash",
    ".config", ".mozilla", ".thunderbird",
})


def _is_dangerous_path(p: str) -> str | None:
    """Return an error message if path is dangerous, else None."""
    expanded = os.path.expanduser(p)
    resolved = os.path.realpath(expanded)

    if resolved in _DANGEROUS_PATHS:
        return f"Path perigoso (directório de sistema): {resolved}"

    home = os.path.expanduser("~")
    if resolved == home:
        return f"Path perigoso (home inteiro): {resolved} — usa um subdirectório"

    if resolved == os.path.dirname(home):  # /home
        return f"Path perigoso (/home inteiro): {resolved}"

    for suffix in _SENSITIVE_SUFFIXES:
        if resolved.endswith(suffix) or f"/{suffix}/" in resolved + "/":
            return f"Path sensível ({suffix}): {resolved}"

    return None


def _ask(prompt: str, default: str = "", auto_yes: bool = False) -> str:
    """Ask user for input with optional default."""
    if auto_yes and default:
        print(f"  {prompt} [{default}] → {default}")
        return default
    suffix = f" [{default}]" if default else ""
    try:
        value = input(f"  {prompt}{suffix}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nAbortado.")
        sys.exit(1)
    return value or default


def _ask_yn(prompt: str, default: bool = True, auto_yes: bool = False) -> bool:
    """Yes/no question."""
    if auto_yes:
        print(f"  {prompt} [{'S' if default else 'N'}] → {'S' if default else 'N'}")
        return default
    hint = "S/n" if default else "s/N"
    try:
        val = input(f"  {prompt} [{hint}]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nAbortado.")
        sys.exit(1)
    if not val:
        return default
    return val in ("s", "sim", "y", "yes")


def _detect_vault() -> str:
    """Try common Obsidian vault locations."""
    candidates = [
        Path.home() / "Obsidian" / "Vault",
        Path.home() / "Obsidian",
        Path.home() / "Documents" / "Obsidian",
        Path.home() / "Documents" / "Obsidian Vault",
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return str(Path.home() / "Obsidian" / "Vault")


def _detect_repos() -> list[str]:
    """Scan common dirs for git repos."""
    found = []
    search_dirs = [
        Path.home() / "Projects",
        Path.home() / "ai-local",
        Path.home() / "repos",
        Path.home() / "dev",
    ]
    for d in search_dirs:
        if not d.exists():
            continue
        for child in sorted(d.iterdir()):
            if child.is_dir() and (child / ".git").exists():
                found.append(str(child))
    return found[:10]  # cap


def _check_ollama(url: str) -> bool:
    """Quick connectivity check."""
    try:
        import httpx
        resp = httpx.get(f"{url}/api/tags", timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False


def _list_ollama_models(url: str) -> list[str]:
    """List installed Ollama models."""
    try:
        import httpx
        resp = httpx.get(f"{url}/api/tags", timeout=5.0)
        if resp.status_code != 200:
            return []
        return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return []


def _generate_toml(
    *,
    vault_dir: str,
    repos: list[str],
    ollama_url: str,
    models: dict[str, bool],
    host: str,
    api_key: str,
) -> str:
    """Generate rag.toml content with the current schema."""
    repo_paths = ", ".join(f'"{r}"' for r in repos)
    model_lines = "\n".join(f'"{name}" = {str(enabled).lower()}' for name, enabled in models.items())

    return f'''# Obsidian RAG — Configuração Central
# Gerado por: rag init
# Todas as opções podem ser overridden via env vars com prefixo RAG_
# Ex: RAG_RETRIEVAL_TOP_K=15 sobrepõe [retrieval] top_k

[paths]
source_dir = "source"
data_dir = "data/chroma"
vault_dir = "{vault_dir}"

[ollama]
base_url = "{ollama_url}"
embedding_model = "bge-m3"

[chunking]
max_chars = 2000
overlap_chars = 200
min_chars = 50
strip_frontmatter = true
contextual_prefix = true

[retrieval]
top_k = 10
score_threshold = 0.45
dynamic_threshold_ratio = 0.75
embedding_cache_size = 128
context_mode = "auto"
token_budget = 4000
graph_max_neighbors = 5
graph_max_communities = 3
graph_cache_ttl = 300

[api]
host = "{host}"
port = 8484
query_top_k = 10
api_key = "{api_key}"
rate_limit = 60
chat_rate_limit = 20

[models]
{model_lines}

[router]
enabled = true
model = "gemma3:4b"
timeout = 15.0

[reranker]
enabled = false
model = "gemma3:4b"
top_k_candidates = 30
min_score = 0.3

[context_policy]
min_relevance_score = 0.50
min_relevant_chunks = 1
log_weak_context = true

[debug]
enabled = false
log_to_file = false
log_level = "INFO"
log_format = "text"

[pipeline]
max_workers = 4

[repos]
paths = [{repo_paths}]
collection_name = "code_repos"

[repos.chunking]
strategy = "ast"
max_chars = 2000
overlap_chars = 200
min_chars = 80
contextual_prefix = true

[graphify]
enabled = false
backend = "ollama"
model = ""
output_dir = "data/graphify"
graph_vault_dir = "~/Obsidian/knowledge-graphs"
auto_update = false
'''


def run_init(args: Namespace) -> None:
    auto = args.yes

    print("╔══════════════════════════════════════╗")
    print("║        Obsidian RAG — Setup          ║")
    print("╚══════════════════════════════════════╝")
    print()

    # Check existing config
    if config_exists():
        if not _ask_yn("rag.toml já existe. Recriar?", default=False, auto_yes=auto):
            print("Setup cancelado.")
            sys.exit(0)

    # --- Vault ---
    print("─── Vault Obsidian ───")
    default_vault = args.vault or _detect_vault()
    vault_dir = _ask("Caminho do Vault Obsidian", default=default_vault, auto_yes=auto)
    err = _is_dangerous_path(vault_dir)
    if err:
        print(f"✗ {err}", file=sys.stderr)
        sys.exit(1)
    print()

    # --- Repos ---
    print("─── Repositórios Git ───")
    if args.repos:
        repos = [r.strip() for r in args.repos.split(",") if r.strip()]
    else:
        detected = _detect_repos()
        if detected and not auto:
            print("  Repos encontrados:")
            for i, r in enumerate(detected, 1):
                print(f"    {i}. {r}")
            selected = _ask("Escolhe números (ex: 1,3,5) ou escreve paths", default=",".join(str(i) for i in range(1, len(detected) + 1)))
            repos = []
            for part in selected.split(","):
                part = part.strip()
                if part.isdigit():
                    idx = int(part) - 1
                    if 0 <= idx < len(detected):
                        repos.append(detected[idx])
                elif part:
                    repos.append(part)
        elif detected:
            repos = detected
        else:
            repos_input = _ask("Repos Git a indexar (paths separados por vírgula)", auto_yes=auto)
            repos = [r.strip() for r in repos_input.split(",") if r.strip()]

    for r in repos:
        err = _is_dangerous_path(r)
        if err:
            print(f"✗ {err}", file=sys.stderr)
            sys.exit(1)
    print()

    # --- Ollama ---
    print("─── Ollama ───")
    ollama_url = args.ollama_url or _ask("URL do Ollama", default="http://localhost:11434", auto_yes=auto)

    if _check_ollama(ollama_url):
        print(f"  ✓ Ollama acessível em {ollama_url}")
        installed_models = _list_ollama_models(ollama_url)
        if installed_models:
            print(f"  Modelos instalados: {', '.join(installed_models)}")
    else:
        print(f"  ⚠ Ollama não acessível em {ollama_url} (podes configurar depois)")
        installed_models = []
    print()

    # --- Models mapping ---
    models: dict[str, bool] = {}
    # RAG-enabled by default for general/multilingual models
    rag_enabled_patterns = {"qwen3", "deepseek", "gemma", "llama", "mistral"}
    # RAG-disabled for pure code models
    rag_disabled_patterns = {"coder", "codellama", "starcoder"}
    for m in installed_models:
        name = m.split(":")[0].lower()
        if any(p in name for p in rag_disabled_patterns):
            models[m] = False
        elif any(p in name for p in rag_enabled_patterns):
            models[m] = True
        elif "bge" not in name:  # skip embedding models
            models[m] = True
    if not models:
        models = {"qwen3:8b": True, "deepseek-r1:8b": True}

    # --- API bind ---
    print("─── Segurança ───")
    host = "127.0.0.1"
    api_key = ""
    if not auto:
        if _ask_yn("Expor API em 0.0.0.0 (acesso remoto)?", default=False):
            host = "0.0.0.0"
            api_key = secrets.token_urlsafe(32)
            print(f"  ⚠ API key gerada: {api_key}")
            print("  Guarda esta chave! Necessária para aceder à API.")
    print()

    # --- Generate ---
    toml_content = _generate_toml(
        vault_dir=vault_dir,
        repos=repos,
        ollama_url=ollama_url,
        models=models,
        host=host,
        api_key=api_key,
    )

    toml_path = PROJECT_ROOT / "rag.toml"
    toml_path.write_text(toml_content, encoding="utf-8")
    print(f"✓ Configuração escrita em {toml_path}")

    # --- Create directories ---
    for d in ["data/chroma", "data/graphify", "source"]:
        (PROJECT_ROOT / d).mkdir(parents=True, exist_ok=True)
    print("✓ Directórios criados (data/chroma, data/graphify, source)")

    print()
    print("Próximos passos:")
    print("  1. rag sync --all    ← sincronizar notas e repos")
    print("  2. rag up            ← iniciar API")
    print("  3. rag query \"teste\" ← testar pesquisa")
