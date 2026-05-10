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
import gc
import os
from pathlib import Path

from obsidian_rag.chunking.code import chunk_repo
from obsidian_rag.chunking.markdown import chunk_all_notes
from obsidian_rag.config import settings
from obsidian_rag.embeddings.ollama import clear_embed_cache
from obsidian_rag.pipeline.ingest import IngestPipeline, IngestSource
from obsidian_rag.pipeline.manifest import IngestManifest
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
    from obsidian_rag.pipeline.governor import GovernorAction, ResourceGovernor

    # --- Resource protection via governor ---
    gov = ResourceGovernor(settings.performance, data_dir=str(settings.paths.data_dir))
    gov.start()
    try:
        action = gov.check()
        if action is GovernorAction.ABORT:
            snap = gov.snapshot()
            reason = f"RAM {snap.ram_percent:.0f}%" if snap else "recursos críticos"
            print(f"✗ [Notas] {reason} — sync abortado.")
            return
        if action is GovernorAction.PAUSE:
            print("⚠ [Notas] Sistema sob pressão — a aguardar recursos...")
            action = gov.wait_until_safe(timeout=15)
            if action is GovernorAction.ABORT:
                print("✗ [Notas] Recursos críticos após espera — sync abortado.")
                return
            if action is GovernorAction.PAUSE:
                print("    Pressão mantém-se — a continuar com precaução.")
    finally:
        gov.stop()

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


def sync_repos() -> None:
    """Sincroniza repos git → ChromaDB (coleção code_repos).

    Uses the bounded ingest pipeline: files are parsed in parallel via
    ProcessPoolExecutor, embedded in micro-batches by a single embedder,
    and written to ChromaDB by a single writer. Bounded queues between
    every stage prevent unbounded memory growth.

    Falls back to sequential processing if the pipeline fails to initialize.
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

    # --- Resource protection via governor ---
    from obsidian_rag.pipeline.governor import GovernorAction, ResourceGovernor

    gov = ResourceGovernor(settings.performance, data_dir=str(settings.paths.data_dir))
    gov.start()

    action = gov.check()
    if action is GovernorAction.ABORT:
        snap = gov.snapshot()
        reason = f"RAM {snap.ram_percent:.0f}%" if snap else "recursos críticos"
        print(f"✗ [Repos] {reason} — sync abortado.")
        gov.stop()
        return
    if action is GovernorAction.PAUSE:
        print("⚠ [Repos] Sistema sob pressão — a aguardar recursos...")
        action = gov.wait_until_safe(timeout=15)
        if action is GovernorAction.ABORT:
            print("✗ [Repos] Recursos críticos após espera — sync abortado.")
            gov.stop()
            return
        if action is GovernorAction.PAUSE:
            print("    Pressão mantém-se — a continuar com precaução.")

    # --- Bounded ingest pipeline ---
    print(f"==> [Repos] A processar {len(valid_paths)} repos via bounded pipeline...")

    manifest_path = settings.paths.data_dir / "manifest.db"
    manifest = IngestManifest(manifest_path)

    client = get_client()
    collection = get_collection(client, name=settings.repos.collection_name)

    sources = [
        IngestSource(source_type="code", path=p, name=p.name)
        for p in valid_paths
    ]

    pipeline = IngestPipeline(
        manifest=manifest,
        perf=settings.performance,
        collection=collection,
        governor=gov,    # pass the already-running governor
    )

    try:
        result = pipeline.run(sources)
    finally:
        manifest.close()
        gov.stop()

    # --- Report ---
    print(f"\n==> [Repos] Pipeline concluído em {result.elapsed_seconds:.1f}s")
    print(f"    Ficheiros: {result.files_scanned} scanned, {result.files_parsed} parsed, {result.files_skipped} skipped")
    print(f"    Chunks: {result.chunks_produced} produced, {result.chunks_embedded} embedded, {result.chunks_stored} stored")
    if result.stale_deleted:
        print(f"    Removidos: {result.stale_deleted} chunks obsoletos")
    if result.errors:
        print(f"    Erros: {len(result.errors)}")
        for err in result.errors[:5]:
            print(f"      - {err}")
        if len(result.errors) > 5:
            print(f"      ... e mais {len(result.errors) - 5}")

    final_count = collection.count()
    print(f"==> [Repos] ChromaDB: {final_count} chunks na coleção '{settings.repos.collection_name}'")


def _wait_for_resources(label: str) -> bool:
    """Aguarda recursos disponíveis entre fases. Retorna False se recursos críticos."""
    from obsidian_rag.pipeline.governor import GovernorAction, ResourceGovernor

    gov = ResourceGovernor(settings.performance, data_dir=str(settings.paths.data_dir))
    gov.start()
    try:
        action = gov.check()
        if action is GovernorAction.ABORT:
            snap = gov.snapshot()
            reason = f"RAM {snap.ram_percent:.0f}%" if snap else "recursos críticos"
            print(f"✗ [{label}] {reason} — fase seguinte abortada.")
            return False
        if action is GovernorAction.PAUSE:
            print(f"⚠ [{label}] Sistema sob pressão após fase anterior — a aguardar...")
            action = gov.wait_until_safe(timeout=15)
            if action is GovernorAction.ABORT:
                print(f"✗ [{label}] Recursos críticos — fase seguinte abortada.")
                return False
            if action is GovernorAction.PAUSE:
                print(f"    [{label}] Pressão mantém-se — a continuar com precaução.")
    finally:
        gov.stop()
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
    # Lower process priority so sync doesn't starve the desktop/OS
    try:
        os.nice(10)
    except OSError:
        pass  # non-root may not be able to increase niceness further
    try:
        _main_inner()
    except KeyboardInterrupt:
        print("\n\n⚠ Interrompido pelo utilizador (Ctrl+C). Sync parcial pode ter sido gravado.")
        raise SystemExit(130)


def _main_inner() -> None:
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
