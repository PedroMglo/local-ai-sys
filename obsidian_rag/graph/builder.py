"""Wrapper para execução do graphify CLI.

Invoca `graphify extract` via subprocess para cada repo configurado.
O graphify processa:
  - Código Python via AST (tree-sitter) — local, sem LLM
  - Markdown/docs via Ollama — local, sem API key externa

Os grafos ficam persistidos em:
  {settings.graphify.output_dir}/{repo_name}/graphify-out/graph.json
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from obsidian_rag.config import settings


def _graphify_output_dir(repo_path: Path) -> Path:
    """Directório de output do graphify para um repo.

    graphify extract --out DIR escreve em DIR/graphify-out/,
    portanto apontamos --out para {output_dir}/{repo_name}.
    """
    return settings.graphify.output_dir / repo_path.name / "graphify-out"


def _graphify_out_parent(repo_path: Path) -> Path:
    """O valor a passar a --out (o pai de graphify-out/)."""
    return settings.graphify.output_dir / repo_path.name


def _graph_json_path(repo_path: Path) -> Path:
    return _graphify_output_dir(repo_path) / "graph.json"


def _report_path(repo_path: Path) -> Path:
    return _graphify_output_dir(repo_path) / "GRAPH_REPORT.md"


def build_graph(repo_path: Path | str, *, force: bool = False) -> bool:
    """Executa graphify extract para um único repo.

    Se *force* for True, apaga o manifest.json para forçar re-extracção total.
    Caso contrário, extract detecta automaticamente se faz rebuild ou incremental.
    Retorna True se bem sucedido, False caso contrário.
    """
    repo_path = Path(repo_path).expanduser().resolve()
    if not repo_path.exists():
        print(f"    [Graphify] Repo não encontrado: {repo_path} — skipping.")
        return False

    output_dir = _graphify_output_dir(repo_path)
    graph_json = _graph_json_path(repo_path)
    manifest_json = output_dir / "manifest.json"

    # Criar directório de output se necessário
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    # force=True: apagar manifest para trigger rebuild completo (AST + LLM)
    if force and manifest_json.exists():
        manifest_json.unlink()
        print("    [Graphify] Manifest removido — rebuild completo forçado.")

    if graph_json.exists() and not force and not settings.graphify.auto_update:
        print(f"    [Graphify] Grafo já existe para '{repo_path.name}' e auto_update=false — skipping.")
        print("    Para forçar rebuild completo: rag-sync -g --force")
        return True

    mode = "rebuild completo" if force else ("incremental" if manifest_json.exists() else "build inicial")

    cmd = [
        "graphify", "extract", str(repo_path),
        "--backend", settings.graphify.backend,
        "--out", str(_graphify_out_parent(repo_path)),
    ]

    # Modelo específico (por defeito graphify usa qwen2.5-coder:7b com ollama)
    if settings.graphify.model:
        cmd += ["--model", settings.graphify.model]

    print(f"==> [Graphify] {repo_path.name} — {mode}")
    print(f"    Comando: {' '.join(cmd)}")

    # Graphify exige OLLAMA_BASE_URL para o backend ollama.
    # Injectar a partir do base_url configurado em rag.toml [ollama].
    env = os.environ.copy()
    if settings.graphify.backend == "ollama":
        ollama_base = settings.ollama.base_url.rstrip("/")
        env.setdefault("OLLAMA_BASE_URL", f"{ollama_base}/v1")
        env.setdefault("OLLAMA_API_KEY", "ollama")

    try:
        subprocess.run(
            cmd,
            cwd=str(repo_path),
            env=env,
            check=True,
            capture_output=False,
        )
        print(f"    [Graphify] Concluído. Grafo em: {graph_json}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"    [Graphify] ERRO (exit code {e.returncode}): {e}")
        return False
    except FileNotFoundError:
        raise FileNotFoundError(
            "Comando 'graphify' não encontrado. "
            "Instala com: pip install graphifyy"
        )


def build_graphs(*, force: bool = False) -> None:
    """Executa graphify extract para todos os repos configurados em rag.toml.

    Se *force* for True, faz update mesmo que auto_update=false.
    """
    if not settings.repos.paths:
        print("==> [Graphify] Sem repos configurados. Skipping.")
        return

    model_info = f" | modelo: {settings.graphify.model}" if settings.graphify.model else ""
    print(f"==> [Graphify] Backend: {settings.graphify.backend}{model_info} | force: {force}")

    successes = 0
    for repo_path in settings.repos.paths:
        if build_graph(repo_path, force=force):
            successes += 1

    print(f"==> [Graphify] {successes}/{len(settings.repos.paths)} repos processados.")


def graph_exists(repo_name: str) -> bool:
    """True se o graph.json existe para um repo."""
    for repo_path in settings.repos.paths:
        if Path(repo_path).name == repo_name:
            return _graph_json_path(repo_path).exists()
    return False


def get_graph_json_path(repo_name: str) -> Path | None:
    """Devolve o path para o graph.json de um repo, ou None se não existir."""
    for repo_path in settings.repos.paths:
        p = Path(repo_path)
        if p.name == repo_name:
            gp = _graph_json_path(p)
            return gp if gp.exists() else None
    return None


def get_report_path(repo_name: str) -> Path | None:
    """Devolve o path para o GRAPH_REPORT.md de um repo, ou None se não existir."""
    for repo_path in settings.repos.paths:
        p = Path(repo_path)
        if p.name == repo_name:
            rp = _report_path(p)
            return rp if rp.exists() else None
    return None
