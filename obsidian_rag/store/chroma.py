"""ChromaDB vector store — client, collection, and sync operations."""

import logging
import time

import chromadb
from chromadb.config import Settings as ChromaSettings

from obsidian_rag.chunking.markdown import Chunk
from obsidian_rag.config import settings
from obsidian_rag.embeddings.ollama import embed_texts

log = logging.getLogger(__name__)


def get_client() -> chromadb.ClientAPI:
    """Inicializa ChromaDB em modo persistente."""
    data_dir = settings.paths.data_dir
    data_dir.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(data_dir),
        settings=ChromaSettings(anonymized_telemetry=False),
    )


def get_collection(client: chromadb.ClientAPI | None = None, name: str = "obsidian_vault"):
    """Obtém ou cria uma coleção ChromaDB pelo nome.

    Args:
        client: cliente ChromaDB (criado automaticamente se None)
        name: nome da coleção — "obsidian_vault" (notas) ou "code_repos" (código)
    """
    if client is None:
        client = get_client()
    return client.get_or_create_collection(
        name=name,
        metadata={"hnsw:space": "cosine"},
    )


def get_existing_ids(collection) -> set[str]:
    """Obtém IDs já existentes na coleção."""
    result = collection.get(include=[])
    return set(result["ids"]) if result["ids"] else set()


def sync_to_chroma(chunks: list[Chunk], verbose: bool = True, _collection=None) -> None:
    """Sincroniza chunks com o ChromaDB (incremental).

    Args:
        chunks: lista de Chunk a sincronizar
        verbose: imprimir progresso
        _collection: coleção ChromaDB (interna; usa obsidian_vault por omissão)
    """
    from obsidian_rag.tuning import should_throttle

    client = get_client()
    collection = _collection if _collection is not None else get_collection(client)

    existing_ids = get_existing_ids(collection)
    new_chunk_ids = {c.id for c in chunks}

    # Remover chunks que já não existem
    stale_ids = existing_ids - new_chunk_ids
    if stale_ids:
        stale_list = list(stale_ids)
        for i in range(0, len(stale_list), 500):
            collection.delete(ids=stale_list[i : i + 500])
        if verbose:
            print(f"  Removidos {len(stale_ids)} chunks obsoletos")

    # Filtrar chunks novos
    chunks_to_add = [c for c in chunks if c.id not in existing_ids]

    if not chunks_to_add:
        if verbose:
            print("  Nenhum chunk novo para processar.")
        return

    if verbose:
        print(f"  A processar {len(chunks_to_add)} chunks novos...")

    total = len(chunks_to_add)
    processed = 0
    start_time = time.time()
    batch_size = settings.performance.embedding_batch_size
    data_dir = str(settings.paths.data_dir)

    i = 0
    while i < total:
        # --- Resource protection between batches ---
        if i > 0:
            advice = should_throttle(settings.performance, data_dir)
            if advice.low_disk:
                log.warning("Disco quase cheio — sync abortado após %d/%d chunks. %s", processed, total, advice.reason)
                print(f"\n  ✗ Disco quase cheio — sync abortado após {processed}/{total} chunks. {advice.reason}")
                return
            if advice.pause_sync:
                for attempt in range(1, 4):
                    log.info("Pressão de recursos (chunk %d/%d): %s — pausa %d/3", i, total, advice.reason, attempt)
                    print(f"\n  ⚠ Sistema sob pressão: {advice.reason} — pausa {attempt}/3...")
                    time.sleep(5)
                    advice = should_throttle(settings.performance, data_dir)
                    if not advice.pause_sync:
                        break
                else:
                    batch_size = max(5, batch_size // 2)
                    log.info("Pressão mantém-se — batch reduzido para %d", batch_size)
                    print(f"  Pressão mantém-se — batch reduzido para {batch_size}")
            elif advice.reduce_workers:
                batch_size = max(5, batch_size // 2)
                log.info("Batch reduzido para %d: %s", batch_size, advice.reason)
                if verbose:
                    print(f"\n  ⚠ Batch reduzido para {batch_size}: {advice.reason}")

        batch = chunks_to_add[i : i + batch_size]
        texts = [c.text for c in batch]
        ids = [c.id for c in batch]
        metadatas = [c.metadata for c in batch]

        embeddings = embed_texts(texts)

        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        processed += len(batch)
        i += len(batch)
        if verbose:
            elapsed = time.time() - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            print(f"    [{processed}/{total}] {rate:.1f} chunks/s", end="\r")

    if verbose:
        elapsed = time.time() - start_time
        print(f"\n  Concluído em {elapsed:.1f}s ({total} chunks)")


def sync_repo_to_chroma(chunks: list[Chunk], verbose: bool = True) -> None:
    """Sincroniza chunks de código na coleção 'code_repos' (incremental).

    Usa a mesma lógica de sync_to_chroma mas na coleção configurada em
    settings.repos.collection_name, mantendo notas Obsidian separadas.
    """
    client = get_client()
    collection = get_collection(client, name=settings.repos.collection_name)
    sync_to_chroma(chunks, verbose=verbose, _collection=collection)


def upsert_embedded_batch(
    collection,
    chunks: list[Chunk],
    embeddings: list[list[float]],
) -> None:
    """Upsert a batch of chunks with pre-computed embeddings.

    Unlike sync_to_chroma(), this does NOT call embed_texts() — embeddings
    are provided by the caller (e.g. the ingest pipeline's embedder stage).
    """
    if not chunks:
        return
    collection.add(
        ids=[c.id for c in chunks],
        embeddings=embeddings,
        documents=[c.text for c in chunks],
        metadatas=[c.metadata for c in chunks],
    )


def delete_stale_from_collection(collection, stale_ids: set[str] | list[str]) -> int:
    """Delete stale chunk IDs from a collection in batches. Returns count deleted."""
    stale_list = list(stale_ids)
    if not stale_list:
        return 0
    for i in range(0, len(stale_list), 500):
        collection.delete(ids=stale_list[i : i + 500])
    return len(stale_list)
