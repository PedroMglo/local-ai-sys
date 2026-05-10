"""ChromaDB vector store — client, collection, and sync operations."""

import time

import chromadb
from chromadb.config import Settings as ChromaSettings

from obsidian_rag.config import settings
from obsidian_rag.chunking.markdown import Chunk
from obsidian_rag.embeddings.ollama import embed_texts


BATCH_SIZE = 50


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

    for i in range(0, total, BATCH_SIZE):
        batch = chunks_to_add[i : i + BATCH_SIZE]
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
