"""``rag doctor`` — system diagnostic with ✓/✗ output."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

from obsidian_rag.config import PROJECT_ROOT, config_exists


def _ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def _fail(msg: str) -> None:
    print(f"  ✗ {msg}")


def _warn(msg: str) -> None:
    print(f"  ⚠ {msg}")


def run_doctor() -> None:
    print("╔══════════════════════════════════════╗")
    print("║      Obsidian RAG — Diagnóstico      ║")
    print("╚══════════════════════════════════════╝")
    print()
    issues = 0

    # 1. Python version
    print("─── Python ───")
    v = sys.version_info
    if v >= (3, 11):
        _ok(f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        _fail(f"Python {v.major}.{v.minor}.{v.micro} — requer ≥ 3.11")
        issues += 1

    # 2. Virtual env
    if os.environ.get("VIRTUAL_ENV"):
        _ok(f"Virtualenv activo: {os.environ['VIRTUAL_ENV']}")
    else:
        _warn("Virtualenv não detectado (recomendado)")

    print()

    # 3. Dependencies
    print("─── Dependências ───")
    deps = {
        "chromadb": "chromadb",
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "httpx": "httpx",
        "networkx": "networkx",
        "slowapi": "slowapi",
        "graphifyy": "graphify",  # pip package=graphifyy, import=graphify
    }
    for name, module in deps.items():
        try:
            mod = importlib.import_module(module)
            version = getattr(mod, "__version__", "?")
            _ok(f"{name} ({version})")
        except ImportError:
            _fail(f"{name} — não instalado")
            issues += 1

    print()

    # 4. Config
    print("─── Configuração ───")
    if not config_exists():
        _fail("rag.toml não encontrado — corre: rag init")
        issues += 1
        print()
        print(f"Resultado: {issues} problema(s) encontrado(s)")
        sys.exit(1 if issues else 0)

    try:
        from obsidian_rag.config import settings
        # Force load
        _ = settings.paths
        _ok(f"rag.toml válido ({PROJECT_ROOT / 'rag.toml'})")
    except Exception as e:
        _fail(f"rag.toml inválido: {e}")
        issues += 1
        print()
        print(f"Resultado: {issues} problema(s) encontrado(s)")
        sys.exit(1)

    print()

    # 5. Paths
    print("─── Paths ───")
    vault = settings.paths.vault_dir
    if vault.exists():
        md_count = len(list(vault.rglob("*.md")))
        _ok(f"Vault: {vault} ({md_count} ficheiros .md)")
    else:
        _warn(f"Vault não encontrado: {vault}")

    source_dir = settings.paths.source_dir
    if source_dir.exists():
        _ok(f"Source: {source_dir}")
    else:
        _warn(f"Source não existe: {source_dir} (criado no primeiro sync)")

    data_dir = settings.paths.data_dir
    if data_dir.exists():
        _ok(f"Data: {data_dir}")
    else:
        _warn(f"Data não existe: {data_dir} (criado no primeiro sync)")

    # Write permissions
    test_dir = data_dir if data_dir.exists() else data_dir.parent
    if test_dir.exists() and os.access(test_dir, os.W_OK):
        _ok(f"Permissões de escrita em {test_dir}")
    else:
        _fail(f"Sem permissões de escrita em {test_dir}")
        issues += 1

    # Repos
    if settings.repos.paths:
        for repo_path in settings.repos.paths:
            repo_path = Path(repo_path)
            if repo_path.exists():
                _ok(f"Repo: {repo_path.name} ({repo_path})")
            else:
                _warn(f"Repo não encontrado: {repo_path}")
    else:
        _warn("Sem repos configurados em [repos] paths")

    print()

    # 6. Ollama
    print("─── Ollama ───")
    base_url = settings.ollama.base_url
    try:
        import httpx
        resp = httpx.get(f"{base_url}/api/tags", timeout=5.0)
        if resp.status_code == 200:
            _ok(f"Ollama acessível ({base_url})")
            models_data = resp.json().get("models", [])
            model_names = [m["name"] for m in models_data]

            # Check embedding model
            embed = settings.ollama.embedding_model
            embed_base = embed.split(":")[0]
            if any(embed_base in m for m in model_names):
                _ok(f"Embedding: {embed}")
            else:
                _fail(f"Embedding '{embed}' não instalado — corre: ollama pull {embed}")
                issues += 1

            # Check router model
            if settings.router.enabled:
                router = settings.router.model
                router_base = router.split(":")[0]
                if any(router_base in m for m in model_names):
                    _ok(f"Router: {router}")
                else:
                    _warn(f"Router '{router}' não instalado (fallback heurística)")

            # List chat models
            chat_models = [m for m in model_names if "bge" not in m.lower() and "embed" not in m.lower()]
            if chat_models:
                _ok(f"Modelos chat: {', '.join(chat_models[:5])}")
        else:
            _fail(f"Ollama respondeu com status {resp.status_code}")
            issues += 1
    except Exception:
        _fail(f"Ollama não acessível em {base_url}")
        issues += 1

    print()

    # 7. ChromaDB
    print("─── ChromaDB ───")
    try:
        from obsidian_rag.store.chroma import get_client, get_collection
        client = get_client()
        notes_col = get_collection(client, name="obsidian_vault")
        notes_count = notes_col.count()
        _ok(f"Notas: {notes_count} chunks (obsidian_vault)")

        if settings.repos.paths:
            try:
                code_col = get_collection(client, name=settings.repos.collection_name)
                code_count = code_col.count()
                _ok(f"Código: {code_count} chunks ({settings.repos.collection_name})")
            except Exception:
                _warn("Coleção de código não existe (corre: rag sync -l)")
    except Exception as e:
        _warn(f"ChromaDB: {e}")

    print()

    # 8. Graphify
    print("─── Graphify ───")
    if settings.graphify.enabled:
        _ok("Graphify habilitado")
    else:
        _ok("Graphify instalado (execução opt-in: rag graph build)")

    output_dir = settings.graphify.output_dir
    if output_dir.exists():
        repos_with_graph = []
        for repo_path in settings.repos.paths:
            repo_name = Path(repo_path).name
            graph_json = output_dir / repo_name / "graphify-out" / "graph.json"
            if graph_json.exists():
                repos_with_graph.append(repo_name)
        if repos_with_graph:
            _ok(f"Grafos: {', '.join(repos_with_graph)}")
        else:
            _warn("Sem grafos construídos (corre: rag graph build)")
    else:
        _warn(f"Directório graphify não existe: {output_dir}")

    print()

    # Summary
    if issues == 0:
        print("✓ Tudo OK — sistema pronto")
    else:
        print(f"✗ {issues} problema(s) encontrado(s)")
    sys.exit(1 if issues else 0)
