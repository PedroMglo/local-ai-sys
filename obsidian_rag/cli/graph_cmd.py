"""``rag graph`` — knowledge graph subcommands."""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path


def run_graph(args: Namespace) -> None:
    if not args.graph_command:
        print("Uso: rag graph {build|status}")
        print("  build  — construir/actualizar grafos")
        print("  status — estado dos grafos")
        sys.exit(1)

    if args.graph_command == "build":
        _graph_build(force=args.force, repo=args.repo)
    elif args.graph_command == "status":
        _graph_status()


def _graph_build(*, force: bool = False, repo: str | None = None) -> None:
    from obsidian_rag.config import settings

    if not settings.repos.paths:
        print("Sem repos configurados em rag.toml [repos] paths.")
        sys.exit(1)

    # If specific repo requested, filter
    if repo:
        matching = [p for p in settings.repos.paths if Path(p).name == repo]
        if not matching:
            print(f"Repo '{repo}' não encontrado nos repos configurados.")
            available = [Path(p).name for p in settings.repos.paths]
            print(f"Disponíveis: {', '.join(available)}")
            sys.exit(1)

    try:
        from obsidian_rag.pipeline.graph.builder import build_graph, build_graphs
    except ImportError:
        print("✗ graphifyy não está instalado. Instala com: pip install -e .")
        sys.exit(1)

    if repo:
        print(f"==> [Graphify] A construir grafo para {repo}...")
        try:
            build_graph(matching[0], force=force)
        except Exception as e:
            print(f"✗ Erro: {e}")
            sys.exit(1)
    else:
        print("==> [Graphify] A construir grafos para todos os repos...")
        build_graphs(force=force)

    # Export to Obsidian vault
    try:
        from obsidian_rag.pipeline.graph.obsidian_export import export_all
        export_all(force=force)
    except Exception as e:
        print(f"⚠ Exportação para vault: {e}")

    # Invalidate cache
    try:
        from obsidian_rag.pipeline.graph.cache import graph_cache
        graph_cache.invalidate()
    except Exception:
        pass

    print("✓ Grafos construídos")


def _graph_status() -> None:
    from obsidian_rag.config import settings

    if not settings.repos.paths:
        print("Sem repos configurados em rag.toml [repos] paths.")
        return

    output_dir = settings.graphify.output_dir

    print("─── Estado dos Grafos ───")
    print()
    print(f"  {'Repo':<25} {'Grafo':<8} {'Nós':<8} {'Edges':<8} {'Tamanho':<12}")
    print(f"  {'─' * 25} {'─' * 8} {'─' * 8} {'─' * 8} {'─' * 12}")

    for repo_path in settings.repos.paths:
        repo_name = Path(repo_path).name
        graph_json = output_dir / repo_name / "graphify-out" / "graph.json"

        if graph_json.exists():
            import json
            try:
                data = json.loads(graph_json.read_text())
                nodes = len(data.get("nodes", []))
                edges = len(data.get("links", []))
                size_kb = graph_json.stat().st_size / 1024
                size_str = f"{size_kb:.0f} KB" if size_kb < 1024 else f"{size_kb / 1024:.1f} MB"
                print(f"  {repo_name:<25} {'✓':<8} {nodes:<8} {edges:<8} {size_str:<12}")
            except Exception:
                print(f"  {repo_name:<25} {'✗ erro':<8}")
        else:
            print(f"  {repo_name:<25} {'—':<8} {'—':<8} {'—':<8} {'—':<12}")

    print()
    if settings.graphify.enabled:
        print(f"  Graphify: habilitado (backend: {settings.graphify.backend})")
    else:
        print("  Graphify: opt-in (corre: rag graph build)")
