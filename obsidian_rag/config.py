"""Configuração centralizada — carrega rag.toml com suporte a env overrides."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


def _find_project_root() -> Path:
    """Walk up from this file to find rag.toml, or check CWD."""
    current = Path(__file__).resolve().parent.parent
    if (current / "rag.toml").exists():
        return current
    # Check current working directory (useful in containers)
    cwd = Path.cwd()
    if (cwd / "rag.toml").exists():
        return cwd
    # fallback: home-based path
    return Path.home() / "ai-local" / "obsidian-rag"


PROJECT_ROOT = _find_project_root()


def _load_toml() -> dict:
    toml_path = PROJECT_ROOT / "rag.toml"
    if not toml_path.exists():
        raise FileNotFoundError(f"Config não encontrado: {toml_path}")
    with open(toml_path, "rb") as f:
        return tomllib.load(f)


def _env_override(section: str, key: str, default):
    """Check for env var RAG_{SECTION}_{KEY} (uppercase)."""
    env_key = f"RAG_{section.upper()}_{key.upper()}"
    val = os.environ.get(env_key)
    if val is None:
        return default
    # Coerce to same type as default
    if isinstance(default, bool):
        return val.lower() in ("true", "1", "yes")
    if isinstance(default, int):
        return int(val)
    if isinstance(default, float):
        return float(val)
    return val


def _resolve_path(raw: str) -> Path:
    """Resolve ~ and relative paths (relative to PROJECT_ROOT)."""
    p = Path(os.path.expanduser(raw))
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p


@dataclass(frozen=True)
class PathsConfig:
    source_dir: Path
    data_dir: Path
    vault_dir: Path


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str
    embedding_model: str


@dataclass(frozen=True)
class ChunkingConfig:
    max_chars: int
    overlap_chars: int
    min_chars: int
    strip_frontmatter: bool
    contextual_prefix: bool


@dataclass(frozen=True)
class RetrievalConfig:
    top_k: int
    score_threshold: float
    dynamic_threshold_ratio: float
    embedding_cache_size: int
    context_mode: str              # "auto" | "rag_only" | "graph_only" | "both" | "none"
    token_budget: int              # max tokens estimados no contexto
    graph_max_neighbors: int       # vizinhos por nó no graph context
    graph_max_communities: int     # max comunidades a injectar
    graph_cache_ttl: int           # TTL em segundos para cache do graph


@dataclass(frozen=True)
class ApiConfig:
    host: str
    port: int
    query_top_k: int
    api_key: str
    rate_limit: int          # requests per minute (0 = disabled)
    chat_rate_limit: int     # /chat requests per minute


@dataclass(frozen=True)
class RepoChunkingConfig:
    strategy: str       # "ast" | "text"
    max_chars: int
    overlap_chars: int
    min_chars: int
    contextual_prefix: bool


@dataclass(frozen=True)
class ReposConfig:
    paths: tuple[Path, ...]   # repos git a indexar
    collection_name: str      # coleção Qdrant separada
    chunking: RepoChunkingConfig


@dataclass(frozen=True)
class GraphifyConfig:
    enabled: bool
    backend: str        # "ollama" | "gemini" | "claude" | "openai"
    model: str          # modelo LLM; "" = usar default do backend
    output_dir: Path
    graph_vault_dir: Path
    auto_update: bool


@dataclass(frozen=True)
class RouterConfig:
    enabled: bool           # use LLM router or keyword-only heuristic
    model: str              # fast model for classification
    timeout: float          # max seconds for LLM call


@dataclass(frozen=True)
class RerankerConfig:
    enabled: bool
    model: str
    top_k_candidates: int   # how many candidates to evaluate
    min_score: float        # minimum reranker score


@dataclass(frozen=True)
class ContextPolicyConfig:
    min_relevance_score: float   # min best-chunk score to accept context
    min_relevant_chunks: int     # min chunks above threshold
    log_weak_context: bool


@dataclass(frozen=True)
class DebugConfig:
    enabled: bool           # show router decisions in output
    log_to_file: bool       # log to obsidian_rag.log
    log_level: str          # DEBUG | INFO | WARNING
    log_format: str         # "text" | "json"


@dataclass(frozen=True)
class SyncConfig:
    backend: str                    # "auto" | "python" | "rsync" | "direct"
    delete_missing: bool            # remove from source_dir files deleted from vault
    follow_symlinks: bool           # follow symlinks when scanning vault
    exclude_patterns: tuple[str, ...]  # glob patterns to skip during sync/scan


# Default patterns excluded from vault sync/scan
_DEFAULT_EXCLUDE_PATTERNS = (
    ".obsidian", ".trash", ".git", ".DS_Store", "Thumbs.db",
    "node_modules", ".venv", "venv", "__pycache__", ".cache",
    "dist", "build",
)


@dataclass(frozen=True)
class StoreConfig:
    backend: str             # "qdrant"
    qdrant_url: str          # Qdrant server URL (empty = embedded mode)
    qdrant_api_key: str      # Qdrant Cloud API key (empty = none)


@dataclass(frozen=True)
class PipelineConfig:
    max_workers: int        # max parallel workers for repo sync
    engine: str = "local"   # "local" (ProcessPoolExecutor) | "dask" (Dask distributed)
    dask_scheduler: str = ""  # Dask scheduler address (empty = local cluster)


@dataclass(frozen=True)
class PerformanceConfig:
    auto_tune: bool              # auto-detect resources and override limits
    max_cpu_percent: int         # throttle sync when CPU% exceeds this
    max_memory_percent: int      # throttle sync when RAM% exceeds this
    max_parallel_jobs: int       # effective cap on workers
    embedding_batch_size: int    # batch size for embedding calls
    embedding_timeout: int       # max seconds for embedding HTTP calls
    query_timeout_seconds: int   # max seconds for a single query
    graph_timeout: int = 600     # max seconds for a single graphify subprocess
    enrich_timeout: int = 180     # max seconds for LLM calls in graph enrichment
    graph_parallel_jobs: int = 1  # parallel graphify subprocesses (1 = sequential)
    # --- Bounded pipeline fields ---
    parser_workers: int = 3              # concurrent file-parsing processes
    embedding_batch_max_chars: int = 48000  # close embedding batch when total chars exceed this
    chunks_queue_max: int = 128          # max pending chunks between parser and embedder
    files_queue_max: int = 256           # max pending files between scanner and parser
    pause_memory_percent: int = 80       # pause pipeline when RAM% exceeds this
    abort_memory_percent: int = 90       # abort pipeline when RAM% exceeds this
    # --- Swap protection ---
    max_swap_percent: int = 40           # reduce when swap% exceeds this
    pause_swap_percent: int = 60         # pause when swap% exceeds this
    abort_swap_percent: int = 80         # abort when swap% exceeds this


@dataclass(frozen=True)
class Settings:
    paths: PathsConfig
    ollama: OllamaConfig
    chunking: ChunkingConfig
    retrieval: RetrievalConfig
    api: ApiConfig
    repos: ReposConfig
    graphify: GraphifyConfig
    router: RouterConfig
    reranker: RerankerConfig
    context_policy: ContextPolicyConfig
    debug: DebugConfig
    store: StoreConfig
    pipeline: PipelineConfig
    performance: PerformanceConfig
    sync: SyncConfig
    models: dict[str, bool] = field(default_factory=dict)


def load_settings() -> Settings:
    """Load settings from rag.toml with env var overrides."""
    raw = _load_toml()

    p = raw.get("paths", {})
    paths = PathsConfig(
        source_dir=_resolve_path(_env_override("paths", "source_dir", p.get("source_dir", "source"))),
        data_dir=_resolve_path(_env_override("paths", "data_dir", p.get("data_dir", "data/qdrant"))),
        vault_dir=_resolve_path(_env_override("paths", "vault_dir", p.get("vault_dir", "~/Obsidian/Vault"))),
    )

    o = raw.get("ollama", {})
    ollama = OllamaConfig(
        base_url=_env_override("ollama", "base_url", o.get("base_url", "http://localhost:11434")),
        embedding_model=_env_override("ollama", "embedding_model", o.get("embedding_model", "bge-m3")),
    )

    c = raw.get("chunking", {})
    chunking = ChunkingConfig(
        max_chars=_env_override("chunking", "max_chars", c.get("max_chars", 2000)),
        overlap_chars=_env_override("chunking", "overlap_chars", c.get("overlap_chars", 200)),
        min_chars=_env_override("chunking", "min_chars", c.get("min_chars", 50)),
        strip_frontmatter=_env_override("chunking", "strip_frontmatter", c.get("strip_frontmatter", True)),
        contextual_prefix=_env_override("chunking", "contextual_prefix", c.get("contextual_prefix", True)),
    )

    r = raw.get("retrieval", {})
    retrieval = RetrievalConfig(
        top_k=_env_override("retrieval", "top_k", r.get("top_k", 10)),
        score_threshold=_env_override("retrieval", "score_threshold", r.get("score_threshold", 0.45)),
        dynamic_threshold_ratio=_env_override("retrieval", "dynamic_threshold_ratio", r.get("dynamic_threshold_ratio", 0.75)),
        embedding_cache_size=_env_override("retrieval", "embedding_cache_size", r.get("embedding_cache_size", 128)),
        context_mode=_env_override("retrieval", "context_mode", r.get("context_mode", "auto")),
        token_budget=_env_override("retrieval", "token_budget", r.get("token_budget", 4000)),
        graph_max_neighbors=_env_override("retrieval", "graph_max_neighbors", r.get("graph_max_neighbors", 5)),
        graph_max_communities=_env_override("retrieval", "graph_max_communities", r.get("graph_max_communities", 3)),
        graph_cache_ttl=_env_override("retrieval", "graph_cache_ttl", r.get("graph_cache_ttl", 300)),
    )

    a = raw.get("api", {})
    api = ApiConfig(
        host=_env_override("api", "host", a.get("host", "127.0.0.1")),
        port=_env_override("api", "port", a.get("port", 8484)),
        query_top_k=_env_override("api", "query_top_k", a.get("query_top_k", 10)),
        api_key=_env_override("api", "api_key", a.get("api_key", "")),
        rate_limit=_env_override("api", "rate_limit", a.get("rate_limit", 60)),
        chat_rate_limit=_env_override("api", "chat_rate_limit", a.get("chat_rate_limit", 20)),
    )

    rp = raw.get("repos", {})
    rc = rp.get("chunking", {})
    repo_chunking = RepoChunkingConfig(
        strategy=_env_override("repos", "strategy", rc.get("strategy", "ast")),
        max_chars=_env_override("repos", "max_chars", rc.get("max_chars", 2000)),
        overlap_chars=_env_override("repos", "overlap_chars", rc.get("overlap_chars", 200)),
        min_chars=_env_override("repos", "min_chars", rc.get("min_chars", 80)),
        contextual_prefix=_env_override("repos", "contextual_prefix", rc.get("contextual_prefix", True)),
    )
    raw_repo_paths = _env_override("repos", "paths", rp.get("paths", []))
    if isinstance(raw_repo_paths, str):
        raw_repo_paths = [p.strip() for p in raw_repo_paths.split(",") if p.strip()]
    repos = ReposConfig(
        paths=tuple(_resolve_path(p) for p in raw_repo_paths),
        collection_name=_env_override("repos", "collection_name", rp.get("collection_name", "code_repos")),
        chunking=repo_chunking,
    )

    gf = raw.get("graphify", {})
    graphify = GraphifyConfig(
        enabled=_env_override("graphify", "enabled", gf.get("enabled", False)),
        backend=_env_override("graphify", "backend", gf.get("backend", "ollama")),
        model=_env_override("graphify", "model", gf.get("model", "")),
        output_dir=_resolve_path(_env_override("graphify", "output_dir", gf.get("output_dir", "data/graphify"))),
        graph_vault_dir=_resolve_path(_env_override("graphify", "graph_vault_dir", gf.get("graph_vault_dir", "~/Obsidian/knowledge-graphs"))),
        auto_update=_env_override("graphify", "auto_update", gf.get("auto_update", False)),
    )

    models = raw.get("models", {})

    rt = raw.get("router", {})
    router = RouterConfig(
        enabled=_env_override("router", "enabled", rt.get("enabled", True)),
        model=_env_override("router", "model", rt.get("model", "gemma3:4b")),
        timeout=_env_override("router", "timeout", rt.get("timeout", 15.0)),
    )

    rr = raw.get("reranker", {})
    reranker = RerankerConfig(
        enabled=_env_override("reranker", "enabled", rr.get("enabled", False)),
        model=_env_override("reranker", "model", rr.get("model", "gemma3:4b")),
        top_k_candidates=_env_override("reranker", "top_k_candidates", rr.get("top_k_candidates", 30)),
        min_score=_env_override("reranker", "min_score", rr.get("min_score", 0.3)),
    )

    cp = raw.get("context_policy", {})
    context_policy = ContextPolicyConfig(
        min_relevance_score=_env_override("context_policy", "min_relevance_score", cp.get("min_relevance_score", 0.50)),
        min_relevant_chunks=_env_override("context_policy", "min_relevant_chunks", cp.get("min_relevant_chunks", 1)),
        log_weak_context=_env_override("context_policy", "log_weak_context", cp.get("log_weak_context", True)),
    )

    db = raw.get("debug", {})
    debug = DebugConfig(
        enabled=_env_override("debug", "enabled", db.get("enabled", False)),
        log_to_file=_env_override("debug", "log_to_file", db.get("log_to_file", False)),
        log_level=_env_override("debug", "log_level", db.get("log_level", "INFO")),
        log_format=_env_override("debug", "log_format", db.get("log_format", "text")),
    )

    st = raw.get("store", {})
    store = StoreConfig(
        backend=_env_override("store", "backend", st.get("backend", "qdrant")),
        qdrant_url=_env_override("store", "qdrant_url", st.get("qdrant_url", "")),
        qdrant_api_key=_env_override("store", "qdrant_api_key", st.get("qdrant_api_key", "")),
    )

    pl = raw.get("pipeline", {})
    pipeline = PipelineConfig(
        max_workers=_env_override("pipeline", "max_workers", pl.get("max_workers", 4)),
        engine=_env_override("pipeline", "engine", pl.get("engine", "local")),
        dask_scheduler=_env_override("pipeline", "dask_scheduler", pl.get("dask_scheduler", "")),
    )

    # Sync — optional section, defaults to backend="direct" (cross-platform)
    sy = raw.get("sync", {})
    raw_excludes = _env_override("sync", "exclude_patterns", sy.get("exclude_patterns", list(_DEFAULT_EXCLUDE_PATTERNS)))
    if isinstance(raw_excludes, str):
        raw_excludes = [e.strip() for e in raw_excludes.split(",") if e.strip()]
    sync = SyncConfig(
        backend=_env_override("sync", "backend", sy.get("backend", "direct")),
        delete_missing=_env_override("sync", "delete_missing", sy.get("delete_missing", True)),
        follow_symlinks=_env_override("sync", "follow_symlinks", sy.get("follow_symlinks", False)),
        exclude_patterns=tuple(raw_excludes),
    )

    pf = raw.get("performance", {})
    performance = PerformanceConfig(
        auto_tune=_env_override("performance", "auto_tune", pf.get("auto_tune", True)),
        max_cpu_percent=_env_override("performance", "max_cpu_percent", pf.get("max_cpu_percent", 75)),
        max_memory_percent=_env_override("performance", "max_memory_percent", pf.get("max_memory_percent", 70)),
        max_parallel_jobs=_env_override("performance", "max_parallel_jobs", pf.get("max_parallel_jobs", 4)),
        embedding_batch_size=_env_override("performance", "embedding_batch_size", pf.get("embedding_batch_size", 30)),
        embedding_timeout=_env_override("performance", "embedding_timeout", pf.get("embedding_timeout", 120)),
        query_timeout_seconds=_env_override("performance", "query_timeout_seconds", pf.get("query_timeout_seconds", 30)),
        graph_timeout=_env_override("performance", "graph_timeout", pf.get("graph_timeout", 600)),
        enrich_timeout=_env_override("performance", "enrich_timeout", pf.get("enrich_timeout", 180)),
        graph_parallel_jobs=_env_override("performance", "graph_parallel_jobs", pf.get("graph_parallel_jobs", 1)),
        parser_workers=_env_override("performance", "parser_workers", pf.get("parser_workers", 1)),
        embedding_batch_max_chars=_env_override("performance", "embedding_batch_max_chars", pf.get("embedding_batch_max_chars", 48000)),
        chunks_queue_max=_env_override("performance", "chunks_queue_max", pf.get("chunks_queue_max", 64)),
        files_queue_max=_env_override("performance", "files_queue_max", pf.get("files_queue_max", 128)),
        pause_memory_percent=_env_override("performance", "pause_memory_percent", pf.get("pause_memory_percent", 80)),
        abort_memory_percent=_env_override("performance", "abort_memory_percent", pf.get("abort_memory_percent", 90)),
        max_swap_percent=_env_override("performance", "max_swap_percent", pf.get("max_swap_percent", 40)),
        pause_swap_percent=_env_override("performance", "pause_swap_percent", pf.get("pause_swap_percent", 60)),
        abort_swap_percent=_env_override("performance", "abort_swap_percent", pf.get("abort_swap_percent", 80)),
    )

    # Auto-tune: adjust limits based on detected hardware
    if performance.auto_tune:
        from obsidian_rag.tuning import auto_tune
        performance = auto_tune(performance)

    # Effective max_workers = min(pipeline setting, performance cap)
    effective_workers = min(pipeline.max_workers, performance.max_parallel_jobs)
    if effective_workers != pipeline.max_workers:
        pipeline = PipelineConfig(max_workers=effective_workers)

    return Settings(
        paths=paths,
        ollama=ollama,
        chunking=chunking,
        retrieval=retrieval,
        api=api,
        repos=repos,
        graphify=graphify,
        router=router,
        reranker=reranker,
        context_policy=context_policy,
        debug=debug,
        store=store,
        pipeline=pipeline,
        performance=performance,
        sync=sync,
        models=models,
    )


def config_exists() -> bool:
    """Check if rag.toml exists without loading it."""
    return (PROJECT_ROOT / "rag.toml").exists()


class _LazySettings:
    """Proxy that defers load_settings() until first attribute access.

    Allows ``from obsidian_rag.config import settings`` without crashing
    when rag.toml does not exist yet (e.g. before ``rag init``).
    """

    _instance: Settings | None = None

    def _load(self) -> Settings:
        if self._instance is None:
            self._instance = load_settings()
        return self._instance

    def __getattr__(self, name: str):
        return getattr(self._load(), name)

    def __repr__(self) -> str:
        if self._instance is None:
            return "<LazySettings: not loaded>"
        return repr(self._instance)


# Module-level singleton — lazy-loaded on first attribute access
settings = _LazySettings()
