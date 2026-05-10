"""Pipeline de sincronização: chunk → embed → store.

Suporta três fontes:
  1. Notas Obsidian (Markdown) — coleção "obsidian_vault"
  2. Repositórios Git (código Python + docs) — coleção "code_repos"
  3. Graphify — knowledge graph estrutural dos repos (opcional)

CLI:
  rag-sync -l      Embeddings de notas + repos (só deltas)
  rag-sync -g      Grafos para repos sem grafo ou desatualizados
  rag-sync --all   Tudo (-l + -g)
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from obsidian_rag.chunking.code import chunk_repo
from obsidian_rag.chunking.markdown import chunk_all_notes
from obsidian_rag.config import settings
from obsidian_rag.store.chroma import get_client, get_collection, sync_repo_to_chroma, sync_to_chroma

# ---------------------------------------------------------------------------
# Sync functions
# ---------------------------------------------------------------------------

def sync_notes() -> None:
    """Sincroniza notas Obsidian → ChromaDB (coleção obsidian_vault)."""
    print("==> [Notas] A fazer chunking das notas Obsidian...")
    chunks = chunk_all_notes()
    print(f"    Total de chunks: {len(chunks)}")

    print("==> [Notas] A sincronizar com ChromaDB (obsidian_vault)...")
    sync_to_chroma(chunks)

    client = get_client()
    collection = get_collection(client, name="obsidian_vault")
    print(f"==> [Notas] ChromaDB: {collection.count()} chunks na coleção 'obsidian_vault'")


def _chunk_single_repo(repo_path: Path) -> tuple[str, list]:
    """Chunk a single repo — runs in worker thread."""
    repo_chunks = chunk_repo(repo_path, cfg=settings.repos.chunking)
    return repo_path.name, repo_chunks


def sync_repos() -> None:
    """Sincroniza repos git → ChromaDB (coleção code_repos).

    Chunking de repos é feito em paralelo com ThreadPoolExecutor.
    """
    if not settings.repos.paths:
        print("==> [Repos] Sem repos configurados em rag.toml [repos] paths. Skipping.")
        return

    valid_paths = []
    for repo_path in settings.repos.paths:
        repo_path = Path(repo_path)
        if not repo_path.exists():
            print(f"    [AVISO] Repo não encontrado: {repo_path} — skipping.")
            continue
        valid_paths.append(repo_path)

    if not valid_paths:
        print("==> [Repos] Nenhum repo válido encontrado.")
        return

    max_workers = min(settings.pipeline.max_workers, len(valid_paths))
    all_repo_chunks = []

    if max_workers <= 1:
        # Sequential fallback
        for repo_path in valid_paths:
            print(f"==> [Repos] A processar repo: {repo_path.name} ({repo_path})")
            repo_chunks = chunk_repo(repo_path, cfg=settings.repos.chunking)
            print(f"    Chunks extraídos: {len(repo_chunks)}")
            all_repo_chunks.extend(repo_chunks)
    else:
        print(f"==> [Repos] A processar {len(valid_paths)} repos em paralelo (max_workers={max_workers})...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_chunk_single_repo, p): p for p in valid_paths}
            for future in as_completed(futures):
                repo_path = futures[future]
                try:
                    name, repo_chunks = future.result()
                    print(f"    [{name}] Chunks extraídos: {len(repo_chunks)}")
                    all_repo_chunks.extend(repo_chunks)
                except Exception as e:
                    print(f"    [ERRO] {repo_path.name}: {e}")

    if not all_repo_chunks:
        print("==> [Repos] Nenhum chunk extraído dos repos.")
        return

    print(f"==> [Repos] Total de chunks: {len(all_repo_chunks)}")
    print(f"==> [Repos] A sincronizar com ChromaDB ({settings.repos.collection_name})...")
    sync_repo_to_chroma(all_repo_chunks)

    client = get_client()
    collection = get_collection(client, name=settings.repos.collection_name)
    print(f"==> [Repos] ChromaDB: {collection.count()} chunks na coleção '{settings.repos.collection_name}'")


def sync_local() -> None:
    """Embeddings: notas Obsidian + repos Git (só deltas — sync incremental)."""
    sync_notes()
    print()
    sync_repos()


def sync_graphify(*, force: bool = False) -> None:
    """Grafos: constrói/actualiza grafos para todos os repos.

    Se *force* é True, apaga o manifest.json de cada repo antes de extrair,
    forçando um rebuild completo (AST + LLM) mesmo que o grafo já exista.
    Após build, exporta para o vault Obsidian configurado em graph_vault_dir.
    """
    if not settings.graphify.enabled:
        print("==> [Graphify] Desabilitado em rag.toml [graphify] enabled = false. Skipping.")
        return
    try:
        from obsidian_rag.graph.builder import build_graphs
        build_graphs(force=force)
    except ImportError:
        print("==> [Graphify] graphifyy não está instalado. Instala com: pip install graphifyy")
        return
    except FileNotFoundError:
        print("==> [Graphify] Comando 'graphify' não encontrado. Instala com: pip install graphifyy")
        return

    # Exportar grafos para o vault Obsidian
    print()
    try:
        from obsidian_rag.graph.obsidian_export import export_all
        export_all(force=force)
    except Exception as e:
        print(f"==> [Obsidian] Erro na exportação para o vault (não fatal): {e}")

    # Invalidar cache do grafo para que o RAG use dados actualizados
    try:
        from obsidian_rag.graph.cache import graph_cache
        graph_cache.invalidate()
        print("==> [GraphCache] Cache invalidada — próximo chat usará dados actualizados.")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    """Entry point: rag-sync [-l | -g | --all]"""
    parser = argparse.ArgumentParser(
        prog="rag-sync",
        description="Sincronização de embeddings e grafos para o RAG local.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-l", "--local",
        action="store_true",
        help="Processar embeddings de notas Obsidian e repos Git (só deltas).",
    )
    group.add_argument(
        "-g", "--graph",
        action="store_true",
        help="Processar grafos Graphify para repos sem grafo ou desatualizados.",
    )
    group.add_argument(
        "--all",
        action="store_true",
        dest="run_all",
        help="Tudo: embeddings + grafos (equivalente a -l + -g).",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="(com -g ou --all) Rebuild completo do grafo, apagando cache anterior.",
    )

    args = parser.parse_args()

    if args.local:
        sync_local()
    elif args.graph:
        sync_graphify(force=args.force)
    elif args.run_all:
        sync_local()
        print()
        sync_graphify(force=args.force)


if __name__ == "__main__":
    main()
