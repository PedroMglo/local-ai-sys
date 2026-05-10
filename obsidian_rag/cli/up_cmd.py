"""``rag up`` — pre-flight checks + start API."""

from __future__ import annotations

import subprocess
import sys

from obsidian_rag.config import PROJECT_ROOT, config_exists


def _check_ollama_running(base_url: str) -> bool:
    try:
        import httpx
        resp = httpx.get(f"{base_url}/api/tags", timeout=5.0)
        return resp.status_code == 200
    except Exception:
        return False


def _get_installed_models(base_url: str) -> list[str]:
    try:
        import httpx
        resp = httpx.get(f"{base_url}/api/tags", timeout=5.0)
        if resp.status_code != 200:
            return []
        return [m["name"] for m in resp.json().get("models", [])]
    except Exception:
        return []


def _pull_model(model: str) -> bool:
    """Pull an Ollama model, returning True on success."""
    try:
        result = subprocess.run(
            ["ollama", "pull", model],
            check=False,
            capture_output=False,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def run_up() -> None:
    print("╔══════════════════════════════════════╗")
    print("║        Obsidian RAG — Start          ║")
    print("╚══════════════════════════════════════╝")
    print()

    # 1. Config check
    if not config_exists():
        print("✗ rag.toml não encontrado.")
        print("  Corre primeiro: rag init")
        sys.exit(1)

    from obsidian_rag.config import settings

    print(f"✓ Configuração carregada ({PROJECT_ROOT / 'rag.toml'})")

    # 2. Ollama connectivity
    base_url = settings.ollama.base_url
    if not _check_ollama_running(base_url):
        print(f"✗ Ollama não acessível em {base_url}")
        print("  Verifica se o Ollama está a correr: ollama serve")
        sys.exit(1)
    print(f"✓ Ollama acessível ({base_url})")

    # 3. Required models
    installed = _get_installed_models(base_url)
    installed_base = {m.split(":")[0] for m in installed}

    embedding_model = settings.ollama.embedding_model
    embedding_base = embedding_model.split(":")[0]
    if embedding_base not in installed_base:
        print(f"⚠ Modelo de embeddings '{embedding_model}' não encontrado.")
        try:
            answer = input(f"  Fazer pull de {embedding_model}? [S/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAbortado.")
            sys.exit(1)
        if answer in ("", "s", "sim", "y", "yes"):
            if not _pull_model(embedding_model):
                print(f"✗ Falha ao fazer pull de {embedding_model}")
                sys.exit(1)
            print(f"✓ {embedding_model} instalado")
        else:
            print("  Sem modelo de embeddings — o sync não vai funcionar.")
    else:
        print(f"✓ Modelo de embeddings: {embedding_model}")

    # Check router model
    if settings.router.enabled:
        router_model = settings.router.model
        router_base = router_model.split(":")[0]
        if router_base not in installed_base:
            print(f"⚠ Modelo do router '{router_model}' não encontrado (fallback para heurística)")
        else:
            print(f"✓ Modelo do router: {router_model}")

    # 4. ChromaDB status
    try:
        from obsidian_rag.store.chroma import get_client, get_collection
        client = get_client()
        notes_col = get_collection(client, name="obsidian_vault")
        notes_count = notes_col.count()
        code_count = 0
        if settings.repos.paths:
            try:
                code_col = get_collection(client, name=settings.repos.collection_name)
                code_count = code_col.count()
            except Exception:
                pass
        if notes_count == 0 and code_count == 0:
            print("⚠ ChromaDB vazio — corre: rag sync --all")
        else:
            print(f"✓ ChromaDB: {notes_count} chunks notas, {code_count} chunks código")
    except Exception as e:
        print(f"⚠ ChromaDB: {e}")

    print()

    # 5. Start API
    host = settings.api.host
    port = settings.api.port
    print(f"A iniciar API em http://{host}:{port} ...")
    print()
    print("Comandos úteis:")
    print(f"  curl http://localhost:{port}/health")
    print(f'  rag query "como configurar aliases no zsh"')
    print(f"  rag chat")
    print()

    from obsidian_rag.api.app import serve
    serve()
