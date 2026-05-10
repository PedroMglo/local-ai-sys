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
from obsidian_rag.embeddings.ollama import clear_embed_cache
from obsidian_rag.pipeline.vault_sync import sync_vault
from obsidian_rag.store.chroma import get_client, get_collection, sync_repo_to_chroma, sync_to_chroma

# ---------------------------------------------------------------------------
# Sync functions
# ---------------------------------------------------------------------------

def sync_notes() -> None:
    """Sincroniza notas Obsidian → ChromaDB (coleção obsidian_vault).

    1. Sync vault → source (or read vault directly, depending on backend)
    2. Chunk all .md files
    3. Embed and store in ChromaDB
    """
    from obsidian_rag.tuning import should_throttle

    # --- Resource protection ---
    advice = should_throttle(settings.performance, str(settings.paths.data_dir))
    if advice.low_disk:
        print(f"✗ [Notas] Disco quase cheio — sync abortado. {advice.reason}")
        return
    if advice.pause_sync:
        import time as _time
        print(f"⚠ [Notas] Sistema sob pressão: {advice.reason}")
        for attempt in range(1, 4):
            print(f"    Pausa {attempt}/3 — a aguardar 5s...")
            _time.sleep(5)
            advice = should_throttle(settings.performance, str(settings.paths.data_dir))
            if not advice.pause_sync:
                break
        else:
            print("    Pressão mantém-se — a continuar com precaução.")

    clear_embed_cache()

    # Step 1: resolve effective notes directory via sync backend
    effective_dir = sync_vault(
        vault_dir=settings.paths.vault_dir,
        source_dir=settings.paths.source_dir,
        cfg=settings.sync,
    )

    # Step 2: chunk
    print("==> [Notas] A fazer chunking das notas Obsidian...")
    chunks = chunk_all_notes(source_dir=effective_dir)
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

    # --- Resource protection ---
    import time as _time

    from obsidian_rag.tuning import should_throttle

    advice = should_throttle(settings.performance, str(settings.paths.data_dir))
    if advice.low_disk:
        print(f"✗ [Repos] Disco quase cheio — sync abortado. {advice.reason}")
        return

    max_workers = min(settings.pipeline.max_workers, len(valid_paths))

    if advice.pause_sync:
        print(f"⚠ [Repos] Sistema sob pressão: {advice.reason}")
        for attempt in range(1, 4):
            print(f"    Pausa {attempt}/3 — a aguardar 5s...")
            _time.sleep(5)
            advice = should_throttle(settings.performance, str(settings.paths.data_dir))
            if not advice.pause_sync:
                break
        else:
            max_workers = max(1, max_workers // 2)
            print(f"    Pressão mantém-se — a reduzir workers para {max_workers}")

    if advice.reduce_workers:
        max_workers = max(1, max_workers // 2)
        print(f"⚠ [Repos] Workers reduzidos para {max_workers}: {advice.reason}")
    all_repo_chunks = []

    if max_workers <= 1:
        # Sequential fallback
        for repo_path in valid_paths:
            # Throttle check before each repo
            advice = should_throttle(settings.performance, str(settings.paths.data_dir))
            if advice.low_disk:
                print(f"✗ [Repos] Disco quase cheio — sync abortado. {advice.reason}")
                break
            if advice.pause_sync:
                print(f"⚠ [Repos] Pressão antes de {repo_path.name}: {advice.reason} — a aguardar...")
                for attempt in range(1, 4):
                    _time.sleep(5)
                    advice = should_throttle(settings.performance, str(settings.paths.data_dir))
                    if not advice.pause_sync:
                        break
            print(f"==> [Repos] A processar repo: {repo_path.name} ({repo_path})")
            repo_chunks = chunk_repo(repo_path, cfg=settings.repos.chunking)
            print(f"    Chunks extraídos: {len(repo_chunks)}")
            all_repo_chunks.extend(repo_chunks)
    else:
        print(f"==> [Repos] A processar {len(valid_paths)} repos em paralelo (max_workers={max_workers})...")
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit repos one at a time with throttle checks between submissions
            pending: dict = {}
            remaining = list(valid_paths)

            while remaining or pending:
                # Submit next repo if under worker limit and resources allow
                while remaining and len(pending) < max_workers:
                    advice = should_throttle(settings.performance, str(settings.paths.data_dir))
                    if advice.low_disk:
                        print(f"\n✗ [Repos] Disco quase cheio — não submete mais repos. {advice.reason}")
                        remaining.clear()
                        break
                    if advice.pause_sync and pending:
                        # Already have work in progress — wait for some to finish first
                        print(f"\n⚠ [Repos] Pressão detectada — a aguardar repos em curso ({len(pending)})...")
                        break
                    repo_path = remaining.pop(0)
                    future = executor.submit(_chunk_single_repo, repo_path)
                    pending[future] = repo_path

                if not pending:
                    break

                # Wait for at least one to complete
                done_iter = as_completed(pending)
                done_future = next(done_iter)
                repo_path = pending.pop(done_future)
                try:
                    name, repo_chunks = done_future.result()
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


def _wait_for_resources(label: str) -> bool:
    """Aguarda recursos disponíveis entre fases. Retorna False se disco cheio."""
    import time as _time

    from obsidian_rag.tuning import should_throttle

    advice = should_throttle(settings.performance, str(settings.paths.data_dir))
    if advice.low_disk:
        print(f"✗ [{label}] Disco quase cheio — fase seguinte abortada. {advice.reason}")
        return False
    if advice.pause_sync:
        print(f"⚠ [{label}] Sistema sob pressão após fase anterior: {advice.reason}")
        for attempt in range(1, 4):
            print(f"    Pausa {attempt}/3 — a aguardar 5s...")
            _time.sleep(5)
            advice = should_throttle(settings.performance, str(settings.paths.data_dir))
            if not advice.pause_sync:
                break
        else:
            print(f"    [{label}] Pressão mantém-se — a continuar com precaução.")
    return True


def sync_local() -> None:
    """Embeddings: notas Obsidian + repos Git (só deltas — sync incremental)."""
    sync_notes()
    print()
    if not _wait_for_resources("Transição notas→repos"):
        return
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
        if _wait_for_resources("Transição local→graphify"):
            sync_graphify(force=args.force)


if __name__ == "__main__":
    main()
