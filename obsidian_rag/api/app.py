"""FastAPI application — endpoints + lifespan."""

import json as _json
import secrets
import time
from contextlib import asynccontextmanager

import httpx as _httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from obsidian_rag import __version__
from obsidian_rag.api.schemas import (
    ChatMessage,
    ChatRequest,
    ChunkResult,
    CodeQueryRequest,
    GraphNeighborsResponse,
    GraphQueryRequest,
    QueryRequest,
    QueryResponse,
    RepoInfo,
    ReposResponse,
    StatsResponse,
)
from obsidian_rag.config import settings
from obsidian_rag.embeddings.ollama import get_query_embedding
from obsidian_rag.prompts.templates import SYSTEM_GENERAL
from obsidian_rag.retrieval.observe import QueryTrace, setup_logging
from obsidian_rag.retrieval.rag import _get_store, build_rag_context, should_use_rag

# === Globals ===
_http_pool: _httpx.AsyncClient | None = None


# === Authentication ===

async def _verify_api_key(request: Request) -> None:
    """Validate Bearer token against configured api_key.

    If api_key is empty in config, authentication is disabled (open access).
    """
    key = settings.api.api_key
    if not key:
        return
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = auth.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(token, key):
        raise HTTPException(status_code=401, detail="Invalid API key")


def _check_api_key(request: Request) -> JSONResponse | None:
    """Check Bearer token; returns a 401 JSONResponse on failure, None on success."""
    key = settings.api.api_key
    if not key:
        return None
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "Missing or invalid Authorization header"})
    token = auth.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(token, key):
        return JSONResponse(status_code=401, content={"detail": "Invalid API key"})
    return None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Preload ChromaDB collections + create connection pool."""
    global _http_pool
    setup_logging()
    _get_store()   # warm up the VectorStore singleton
    _http_pool = _httpx.AsyncClient(
        base_url=settings.ollama.base_url,
        timeout=_httpx.Timeout(connect=5.0, read=300.0, write=30.0, pool=10.0),
        limits=_httpx.Limits(max_connections=10, max_keepalive_connections=5),
    )
    yield
    await _http_pool.aclose()
    _http_pool = None


app = FastAPI(
    title="Obsidian RAG API",
    description="API local para queries semânticas ao Vault Obsidian e repositórios de código",
    version=__version__,
    lifespan=lifespan,
)

# === Rate limiting ===
_rate_limit = settings.api.rate_limit
_chat_rate_limit = settings.api.chat_rate_limit

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{_rate_limit}/minute"] if _rate_limit > 0 else [],
    enabled=_rate_limit > 0,
)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )


# Paths exempt from API key authentication
_AUTH_EXEMPT_PATHS = frozenset({"/health", "/docs", "/openapi.json", "/redoc"})


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Enforce API key on all endpoints except health and docs."""
    if request.url.path not in _AUTH_EXEMPT_PATHS:
        error_response = _check_api_key(request)
        if error_response is not None:
            return error_response
    return await call_next(request)


# === Endpoints ===

@app.get("/health")
def health():
    return {"status": "ok", "service": "obsidian-rag", "version": __version__}


@app.get("/stats", response_model=StatsResponse)
def stats():
    store = _get_store()
    code_chunks = 0
    code_name = ""
    if settings.repos.paths:
        try:
            code_chunks = store.count(collection=settings.repos.collection_name)
            code_name = settings.repos.collection_name
        except Exception:
            pass
    return StatsResponse(
        total_chunks=store.count(collection="obsidian_vault"),
        collection_name="obsidian_vault",
        chroma_path=str(settings.paths.data_dir),
        code_chunks=code_chunks,
        code_collection_name=code_name,
    )


def _query_store(store, collection_name: str, req: QueryRequest, *, filters: dict | None = None) -> list[ChunkResult]:
    """Executa query vectorial via VectorStore e devolve ChunkResults."""
    query_embedding = get_query_embedding(req.query)
    results = store.query(query_embedding, n=req.top_k, collection=collection_name, filters=filters)
    chunks = []
    for r in results:
        if r.score >= req.min_score:
            display = r.metadata.get("display_text", r.document)
            chunks.append(ChunkResult(
                text=display,
                score=round(r.score, 4),
                source_path=r.metadata.get("source_path", ""),
                note_title=r.metadata.get("note_title", ""),
                section_header=r.metadata.get("section_header", ""),
                source_type=r.metadata.get("source_type", "markdown"),
                repo_name=r.metadata.get("repo_name"),
                symbol_type=r.metadata.get("symbol_type"),
            ))
    return chunks


def _count_repo_chunks(store, repo_name: str) -> int:
    """Count code chunks belonging to a specific repo (best-effort)."""
    col_name = settings.repos.collection_name
    try:
        from obsidian_rag.store.chroma_store import ChromaVectorStore
        if isinstance(store, ChromaVectorStore):
            col = store._col(col_name)
            result = col.get(where={"repo_name": {"$eq": repo_name}}, include=[])  # type: ignore[dict-item]
            return len(result["ids"]) if result["ids"] else 0
    except ImportError:
        pass
    try:
        from obsidian_rag.store.qdrant_store import QdrantVectorStore
        if isinstance(store, QdrantVectorStore):
            qdrant_models = store._models
            result = store._client.count(
                collection_name=col_name,
                count_filter=qdrant_models.Filter(
                    must=[qdrant_models.FieldCondition(
                        key="repo_name",
                        match=qdrant_models.MatchValue(value=repo_name),
                    )]
                ),
            )
            return int(result.count)
    except ImportError:
        pass
    return 0


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    """Pesquisa semântica nas notas Obsidian (obsidian_vault)."""
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query vazia")
    start = time.time()
    store = _get_store()
    chunks = _query_store(store, "obsidian_vault", req)
    elapsed_ms = (time.time() - start) * 1000
    return QueryResponse(results=chunks, query=req.query, elapsed_ms=round(elapsed_ms, 1))


@app.post("/query/code", response_model=QueryResponse)
def query_code(req: CodeQueryRequest):
    """Pesquisa semântica na coleção de código (code_repos).

    Suporta filtro por repo_name e symbol_type.
    """
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="Query vazia")
    if not settings.repos.paths:
        raise HTTPException(status_code=404, detail="Sem repos configurados em rag.toml")

    start = time.time()
    store = _get_store()

    # Build query-time filters
    code_filters: dict[str, str] = {}
    if req.repo:
        code_filters["repo_name"] = req.repo
    if req.symbol_type:
        code_filters["symbol_type"] = req.symbol_type

    chunks = _query_store(store, settings.repos.collection_name, req, filters=code_filters or None)

    elapsed_ms = (time.time() - start) * 1000
    return QueryResponse(results=chunks, query=req.query, elapsed_ms=round(elapsed_ms, 1))


@app.get("/repos", response_model=ReposResponse)
def repos():
    """Lista repos configurados com stats de chunks e grafo."""
    from obsidian_rag.graph.query import list_repos

    repo_infos_raw = list_repos()
    repo_list = []
    for r in repo_infos_raw:
        # Contar chunks de código para este repo
        code_chunks = 0
        if settings.repos.paths:
            try:
                store = _get_store()
                code_chunks = _count_repo_chunks(store, r["name"])
            except Exception:
                pass

        repo_list.append(RepoInfo(
            name=r["name"],
            path=r["path"],
            exists=r["exists"],
            graph_built=r["graph_built"],
            graph_path=r.get("graph_path"),
            report_path=r.get("report_path"),
            node_count=r.get("node_count"),
            edge_count=r.get("edge_count"),
            code_chunks=code_chunks,
        ))

    return ReposResponse(
        repos=repo_list,
        graphify_enabled=settings.graphify.enabled,
        graphify_backend=settings.graphify.backend,
    )


@app.get("/graph/{repo}")
def graph_report(repo: str):
    """Devolve o GRAPH_REPORT.md de um repo como texto."""
    from obsidian_rag.graph.query import get_report
    try:
        report = get_report(repo)
        return {"repo": repo, "report": report}
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/graph/{repo}/query")
def graph_query(repo: str, req: GraphQueryRequest):
    """Executa uma query ao knowledge graph de um repo."""
    from obsidian_rag.graph.query import query_graph
    result = query_graph(repo, req.query)
    return {"repo": repo, "query": req.query, "result": result}


@app.get("/graph/{repo}/neighbors/{node}")
def graph_neighbors(repo: str, node: str, max_results: int = 10):
    """Devolve nós vizinhos de um conceito no grafo."""
    from obsidian_rag.graph.query import get_neighbors
    try:
        neighbors = get_neighbors(repo, node, max_results=max_results)
        return GraphNeighborsResponse(node=node, repo=repo, neighbors=neighbors)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ImportError as e:
        raise HTTPException(status_code=503, detail=str(e))


def _inject_rag_into_messages(messages: list[ChatMessage], context: str) -> list[dict]:
    """Inject RAG context as system message prefix."""
    msg_list = [m.model_dump() for m in messages]
    if msg_list and msg_list[0]["role"] == "system":
        msg_list[0]["content"] = context + "\n\n" + msg_list[0]["content"]
    else:
        msg_list.insert(0, {"role": "system", "content": context})
    return msg_list


def _ensure_system_prompt(messages: list[dict]) -> list[dict]:
    """Ensure a domain-neutral system prompt exists when no RAG context is injected."""
    if messages and messages[0]["role"] == "system":
        return messages
    return [{"role": "system", "content": SYSTEM_GENERAL}] + messages


@app.post("/chat")
@limiter.limit(f"{_chat_rate_limit}/minute" if _chat_rate_limit and _chat_rate_limit > 0 else "999999/minute")
async def chat(request: Request, req: ChatRequest):
    """RAG-augmented chat proxy to Ollama.

    Now uses the LLM router to decide if context is needed.
    For general questions, the LLM responds without any RAG context.
    """
    rag_used = False
    sources_used = "none"
    messages = [m.model_dump() for m in req.messages]
    trace = QueryTrace()
    trace.model = req.model

    if should_use_rag(req.model):
        user_msgs = [m for m in req.messages if m.role == "user"]
        if user_msgs:
            query_text = user_msgs[-1].content
            trace.query = query_text

            context, relevant, sources_used = build_rag_context(
                query_text,
                context_mode=req.context_mode,
                trace=trace,
            )
            if relevant:
                messages = _inject_rag_into_messages(req.messages, context)
                rag_used = True
            else:
                # No context needed — ensure clean system prompt
                messages = _ensure_system_prompt(messages)
    else:
        messages = _ensure_system_prompt(messages)

    trace.finish()

    ollama_payload = {
        "model": req.model,
        "messages": messages,
        "stream": req.stream,
    }

    if not req.stream:
        assert _http_pool is not None, "HTTP pool not initialized"
        resp = await _http_pool.post("/api/chat", json=ollama_payload)
        data = resp.json()
        data["rag_used"] = rag_used
        data["sources_used"] = sources_used
        if settings.debug.enabled:
            data["debug"] = trace.to_debug_dict()
        return data

    # Streaming proxy
    async def _stream_ollama():
        assert _http_pool is not None, "HTTP pool not initialized"
        async with _http_pool.stream("POST", "/api/chat", json=ollama_payload) as resp:
            async for line in resp.aiter_lines():
                if line:
                    yield line + "\n"
        # Append debug info as final NDJSON line if debug enabled
        if settings.debug.enabled:
            yield _json.dumps({"debug": trace.to_debug_dict()}) + "\n"

    return StreamingResponse(
        _stream_ollama(),
        media_type="application/x-ndjson",
        headers={
            "X-RAG-Used": str(rag_used).lower(),
            "X-Sources-Used": sources_used,
            "X-Route-Mode": trace.route_mode or "unknown",
        },
    )


def serve():
    """Entry point for rag serve."""
    import uvicorn

    host = settings.api.host
    port = settings.api.port

    # Security: refuse 0.0.0.0 without API key
    if host == "0.0.0.0" and not settings.api.api_key:  # nosec B104
        import sys
        print(
            "ERRO: API exposta em 0.0.0.0 sem api_key configurada.\n"
            "Define [api] api_key em rag.toml ou usa host = \"127.0.0.1\".",
            file=sys.stderr,
        )
        sys.exit(1)

    uvicorn.run(
        "obsidian_rag.api.app:app",
        host=host,
        port=port,
    )


if __name__ == "__main__":
    serve()
