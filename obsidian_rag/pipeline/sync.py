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
import os
from pathlib import Path

from obsidian_rag.config import settings
from obsidian_rag.embeddings.ollama import clear_embed_cache
from obsidian_rag.pipeline.ingest import IngestPipeline, IngestSource
from obsidian_rag.pipeline.manifest import IngestManifest
from obsidian_rag.pipeline.vault_sync import sync_vault
from obsidian_rag.store import get_store

# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# Sync functions
# ---------------------------------------------------------------------------

def sync_notes(*, vault_filter: str | None = None) -> None:
    """Sincroniza notas Obsidian → vector store (coleção obsidian_vault).

    Supports multiple vaults via ``settings.paths.vault_dirs``.
    Each vault's chunks are tagged with ``vault_name`` metadata for
    query-time filtering.

    Args:
        vault_filter: If set, sync only the vault whose directory name
                      matches (case-insensitive).
    """
    from obsidian_rag.pipeline.governor import GovernorAction, ResourceGovernor

    # --- Resource protection via governor ---
    gov = ResourceGovernor(settings.performance, data_dir=str(settings.paths.data_dir))
    gov.start()

    action = gov.check()
    if action is GovernorAction.ABORT:
        snap = gov.snapshot()
        reasons = []
        if snap:
            reasons.append(f"RAM {snap.ram_percent:.0f}%")
            if snap.swap_percent > 0:
                reasons.append(f"Swap {snap.swap_percent:.0f}%")
        reason = ", ".join(reasons) if reasons else "recursos críticos"
        print(f"✗ [Notas] {reason} — sync abortado.")
        gov.stop()
        return
    if action is GovernorAction.PAUSE:
        snap = gov.snapshot()
        detail = ""
        if snap:
            detail = f" (RAM {snap.ram_percent:.0f}%, Swap {snap.swap_percent:.0f}%)"
        print(f"⚠ [Notas] Sistema sob pressão{detail} — a aguardar recursos...")
        action = gov.wait_until_safe(timeout=15)
        if action is GovernorAction.ABORT:
            print("✗ [Notas] Recursos críticos após espera — sync abortado.")
            gov.stop()
            return
        if action is GovernorAction.PAUSE:
            print("    Pressão mantém-se — a continuar com precaução.")

    clear_embed_cache()

    # Resolve vault directories (multi-vault support)
    vault_dirs = settings.paths.vault_dirs
    if vault_filter:
        vault_dirs = tuple(
            vd for vd in vault_dirs
            if vd.name.lower() == vault_filter.lower()
        )
        if not vault_dirs:
            print(f"✗ Vault '{vault_filter}' não encontrado em vault_dirs.")
            gov.stop()
            return

    # Build IngestSource per vault
    sources: list[IngestSource] = []
    for vault_dir in vault_dirs:
        effective_dir = sync_vault(
            vault_dir=vault_dir,
            source_dir=settings.paths.source_dir,
            cfg=settings.sync,
        )
        vault_name = vault_dir.name
        sources.append(
            IngestSource(source_type="vault", path=effective_dir, name=vault_name),
        )

    if not sources:
        print("⚠ [Notas] Nenhum vault configurado.")
        gov.stop()
        return

    vault_names = ", ".join(s.name for s in sources)
    print(f"==> [Notas] A processar {len(sources)} vault(s): {vault_names}")

    manifest_path = settings.paths.data_dir / "manifest.db"
    manifest = IngestManifest(manifest_path)

    store = get_store()

    pipeline = IngestPipeline(
        manifest=manifest,
        perf=settings.performance,
        store=store,
        collection_name="obsidian_vault",
        governor=gov,
        pipeline_config=settings.pipeline,
    )

    try:
        result = pipeline.run(sources)
    finally:
        manifest.close()
        gov.stop()

    # --- Report ---
    print(f"\n==> [Notas] Pipeline concluído em {result.elapsed_seconds:.1f}s")
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

    final_count = store.count(collection="obsidian_vault")
    print(f"==> [Notas] Store: {final_count} chunks na coleção 'obsidian_vault'")


def sync_repos() -> None:
    """Sincroniza repos git → vector store (coleção code_repos).

    Uses the bounded ingest pipeline: files are parsed in parallel via
    ProcessPoolExecutor, embedded in micro-batches by a single embedder,
    and written to the vector store by a single writer. Bounded queues
    between every stage prevent unbounded memory growth.

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
        reasons = []
        if snap:
            reasons.append(f"RAM {snap.ram_percent:.0f}%")
            if snap.swap_percent > 0:
                reasons.append(f"Swap {snap.swap_percent:.0f}%")
        reason = ", ".join(reasons) if reasons else "recursos críticos"
        print(f"✗ [Repos] {reason} — sync abortado.")
        gov.stop()
        return
    if action is GovernorAction.PAUSE:
        snap = gov.snapshot()
        detail = ""
        if snap:
            detail = f" (RAM {snap.ram_percent:.0f}%, Swap {snap.swap_percent:.0f}%)"
        print(f"⚠ [Repos] Sistema sob pressão{detail} — a aguardar recursos...")
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

    store = get_store()

    sources = [
        IngestSource(source_type="code", path=p, name=p.name)
        for p in valid_paths
    ]

    pipeline = IngestPipeline(
        manifest=manifest,
        perf=settings.performance,
        store=store,
        collection_name=settings.repos.collection_name,
        governor=gov,    # pass the already-running governor
        pipeline_config=settings.pipeline,
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

    final_count = store.count(collection=settings.repos.collection_name)
    print(f"==> [Repos] Store: {final_count} chunks na coleção '{settings.repos.collection_name}'")


def _wait_for_resources(label: str) -> bool:
    """Aguarda recursos disponíveis entre fases. Retorna False se recursos críticos."""
    from obsidian_rag.pipeline.governor import GovernorAction, ResourceGovernor

    gov = ResourceGovernor(settings.performance, data_dir=str(settings.paths.data_dir))
    gov.start()
    try:
        action = gov.check()
        if action is GovernorAction.ABORT:
            snap = gov.snapshot()
            reasons = []
            if snap:
                reasons.append(f"RAM {snap.ram_percent:.0f}%")
                if snap.swap_percent > 0:
                    reasons.append(f"Swap {snap.swap_percent:.0f}%")
            reason = ", ".join(reasons) if reasons else "recursos críticos"
            print(f"✗ [{label}] {reason} — fase seguinte abortada.")
            return False
        if action is GovernorAction.PAUSE:
            snap = gov.snapshot()
            detail = ""
            if snap:
                detail = f" (RAM {snap.ram_percent:.0f}%, Swap {snap.swap_percent:.0f}%)"
            print(f"⚠ [{label}] Sistema sob pressão{detail} — a aguardar...")
            action = gov.wait_until_safe(timeout=15)
            if action is GovernorAction.ABORT:
                print(f"✗ [{label}] Recursos críticos — fase seguinte abortada.")
                return False
            if action is GovernorAction.PAUSE:
                print(f"    [{label}] Pressão mantém-se — a continuar com precaução.")
    finally:
        gov.stop()
    return True


def sync_local(*, vault_filter: str | None = None) -> None:
    """Embeddings: notas Obsidian + repos Git (só deltas — sync incremental)."""
    import gc

    sync_notes(vault_filter=vault_filter)
    gc.collect()  # free chunk lists, ASTs, source code from notes phase
    print()
    if not _wait_for_resources("Transição notas→repos"):
        return
    sync_repos()
    gc.collect()  # free pipeline objects


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
        from obsidian_rag.pipeline.graph.builder import build_graphs
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
        from obsidian_rag.pipeline.graph.obsidian_export import export_all
        export_all(force=force)
    except Exception as e:
        print(f"==> [Obsidian] Erro na exportação para o vault (não fatal): {e}")

    # Invalidar cache do grafo para que o RAG use dados actualizados
    try:
        from obsidian_rag.pipeline.graph.cache import graph_cache
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


# ---------------------------------------------------------------------------
# System snapshot
# ---------------------------------------------------------------------------

def sync_system_snapshot() -> None:
    """Generate a static system profile snapshot as a markdown file.

    Writes ``source/AI-context/system-profile/live-state.md`` with
    a comprehensive hardware/software snapshot that can be indexed
    alongside other project sources.
    """
    import datetime

    from obsidian_rag.retrieval.system_context import collect_system_context

    print("🖥  Generating system snapshot...")

    # Broad query to trigger all subsystems
    snapshot = collect_system_context(
        "system machine hardware cpu gpu ram memory disk processes network temperatura"
    )

    if not snapshot:
        print("⚠  No system data collected — skipping snapshot.")
        return

    project_root = Path(__file__).resolve().parent.parent.parent
    out_dir = project_root / "source" / "AI-context" / "system-profile"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "live-state.md"

    header = (
        "---\n"
        f"generated: {datetime.datetime.now().isoformat()}\n"
        "type: system-snapshot\n"
        "---\n\n"
        "# System Profile — Live State\n\n"
        "This file is auto-generated by `rag sync --system`.\n"
        "It contains a point-in-time snapshot of the machine's hardware and software state.\n\n"
    )

    out_file.write_text(header + snapshot + "\n", encoding="utf-8")
    print(f"✓ Snapshot saved to {out_file.relative_to(project_root)}")
