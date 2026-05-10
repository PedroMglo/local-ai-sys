"""Pydantic schemas for API request/response models."""

from typing import Any

from pydantic import BaseModel, Field

from obsidian_rag.config import settings


class QueryRequest(BaseModel):
    query: str = Field(..., description="Texto da pergunta/busca", min_length=1, max_length=10000)
    top_k: int = Field(default=settings.api.query_top_k, ge=1, le=50)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)


class CodeQueryRequest(QueryRequest):
    """Query apenas na coleção de código (code_repos)."""
    repo: str | None = Field(default=None, description="Filtrar por repo_name específico (opcional)")
    symbol_type: str | None = Field(default=None, description="Filtrar por tipo de símbolo: function, class, method, module")


class ChunkResult(BaseModel):
    text: str
    score: float
    source_path: str
    note_title: str
    section_header: str
    # Campos opcionais presentes em chunks de código
    source_type: str = "markdown"
    repo_name: str | None = None
    symbol_type: str | None = None


class QueryResponse(BaseModel):
    results: list[ChunkResult]
    query: str
    elapsed_ms: float


class StatsResponse(BaseModel):
    total_chunks: int
    collection_name: str
    chroma_path: str
    # Coleções adicionais
    code_chunks: int = 0
    code_collection_name: str = ""


class RepoInfo(BaseModel):
    name: str
    path: str
    exists: bool
    graph_built: bool
    graph_path: str | None = None
    report_path: str | None = None
    node_count: int | None = None
    edge_count: int | None = None
    code_chunks: int = 0


class ReposResponse(BaseModel):
    repos: list[RepoInfo]
    graphify_enabled: bool
    graphify_backend: str


class GraphQueryRequest(BaseModel):
    query: str = Field(..., description="Query em linguagem natural para o grafo", min_length=1, max_length=10000)


class GraphNeighborsResponse(BaseModel):
    node: str
    repo: str
    neighbors: list[dict[str, Any]]


class ChatMessage(BaseModel):
    role: str = Field(..., max_length=20)
    content: str = Field(..., max_length=50000)


class ChatRequest(BaseModel):
    model: str = Field(default="qwen3-pt", max_length=100)
    messages: list[ChatMessage] = Field(..., max_length=200)
    stream: bool = True
    context_mode: str | None = Field(default=None, description="Override do context_mode: auto|rag_only|graph_only|both|none", max_length=20)
