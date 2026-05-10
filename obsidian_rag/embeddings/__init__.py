"""Embeddings — generate vector embeddings via Ollama."""

from obsidian_rag.embeddings.ollama import embed_texts, get_query_embedding

__all__ = ["embed_texts", "get_query_embedding"]
