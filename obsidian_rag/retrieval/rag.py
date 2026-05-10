"""Multi-strategy RAG retrieval and context builder.

Domain-agnostic design: context is only injected when the router
determines it's needed AND retrieval quality passes the relevance gate.
"""

import logging
import threading
import unicodedata

from obsidian_rag.config import settings
from obsidian_rag.embeddings.ollama import get_query_embedding
from obsidian_rag.prompts.templates import get_context_instruction
from obsidian_rag.retrieval.budget import allocate_budget, truncate_chunks, truncate_text
from obsidian_rag.retrieval.intent import detect_intent_full
from obsidian_rag.retrieval.observe import QueryTrace
from obsidian_rag.retrieval.router import _GRAPH_PATTERNS, _GRAPH_SIGNALS, ContextMode
from obsidian_rag.store.base import VectorStore, create_store

log = logging.getLogger("obsidian_rag")

_PT_STOP_WORDS = frozenset({
    "a", "ao", "aos", "as", "com", "da", "das", "de", "do", "dos", "e", "em",
    "eu", "já", "lhe", "me", "meu", "minha", "na", "nas", "no", "nos", "o",
    "os", "para", "pela", "pelo", "por", "que", "se", "seu", "são", "sua",
    "te", "tem", "tenho", "ter", "um", "uma", "uns", "vai", "à", "é", "há",
    "isso", "isto", "mais", "mas", "muito", "não", "ou", "ser", "como",
    "quando", "quais", "qual", "quem", "quero", "ver", "lista", "todos",
    "todas", "algum", "cada", "esse", "essa", "esses",
})

_EN_STOP_WORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "been", "but", "by", "can",
    "could", "did", "do", "does", "for", "from", "had", "has", "have", "he",
    "her", "him", "his", "how", "if", "in", "into", "is", "it", "its",
    "may", "me", "might", "must", "my", "not", "of", "on", "or", "our",
    "shall", "she", "should", "so", "some", "than", "that", "the", "their",
    "them", "then", "there", "these", "they", "this", "those", "to", "too",
    "us", "very", "was", "we", "were", "what", "when", "where", "which",
    "who", "whom", "why", "will", "with", "would", "you", "your",
})

_STOP_WORDS = _PT_STOP_WORDS | _EN_STOP_WORDS

_NAVIGATION_SECTIONS = frozenset({
    "Ficheiros", "Navegação", "Índice", "Navigation", "Files", "Conteúdo",
})


# === VectorStore singleton ===
_lock = threading.Lock()
_store: VectorStore | None = None


def _get_store(*, _override: VectorStore | None = None) -> VectorStore:
    """Lazy singleton for the configured vector store.

    Args:
        _override: inject a store for testing (bypasses singleton).
    """
    global _store
    if _override is not None:
        return _override
    if _store is None:
        with _lock:
            if _store is None:
                _store = create_store()
    return _store


def _reset_collections():
    """Reset singletons — for testing only."""
    global _store
    with _lock:
        _store = None


# === Helpers ===

def _is_navigation_chunk(meta: dict, doc: str) -> bool:
    """True if this chunk is navigation/index with low info value."""
    section = meta.get("section_header", "")
    if section in _NAVIGATION_SECTIONS:
        return True
    lines = [ln.strip() for ln in doc.strip().splitlines() if ln.strip()]
    if not lines:
        return True
    link_count = sum(1 for ln in lines if "[[" in ln and "]]" in ln and len(ln) < 80)
    return link_count / len(lines) > 0.6


def _extract_keywords(text: str) -> str:
    normalized = unicodedata.normalize("NFC", text)
    words = [w.strip(".,!?:;\"'()[]") for w in normalized.lower().split()]
    keywords = [w for w in words if w and w not in _STOP_WORDS and len(w) > 2]
    return " ".join(keywords) if keywords else text


def _estimate_complexity(query: str) -> str:
    """Estimate query complexity for adaptive top_k.

    Returns "simple" | "normal" | "complex".
    """
    q_lower = query.lower()
    words = [w for w in q_lower.split() if w.strip()]
    word_count = len(words)

    # Complex indicators
    has_graph = bool({w.strip(".,!?") for w in words} & _GRAPH_SIGNALS) or any(p in q_lower for p in _GRAPH_PATTERNS)
    has_boolean = any(op in q_lower for op in (" and ", " or ", " not ", " && ", " || "))
    multi_question = q_lower.count("?") > 1

    if has_graph or has_boolean or multi_question or word_count > 8:
        return "complex"
    if word_count <= 3:
        return "simple"
    return "normal"


def _search_chroma(store: VectorStore, query_text: str, n: int, *, collection: str = "obsidian_vault") -> list[tuple[str, dict, float]]:
    """Vector search via the VectorStore protocol."""
    embedding = get_query_embedding(query_text)
    results = store.query(embedding, n=min(n * 3, 50), collection=collection)
    return [(r.document, r.metadata, r.score) for r in results]


def _deduplicate(chunks: list[tuple[str, dict, float]]) -> list[tuple[str, dict, float]]:
    """Deduplicate chunks by composite key, keeping highest score."""
    seen: dict[str, tuple[str, dict, float]] = {}
    for doc, meta, score in chunks:
        key = f"{meta.get('source_path', '')}:{meta.get('section_header', '')}:{meta.get('chunk_index', 0)}"
        if key not in seen or score > seen[key][2]:
            seen[key] = (doc, meta, score)
    return list(seen.values())


def _apply_threshold(
    chunks: list[tuple[str, dict, float]],
    score_threshold: float,
    dynamic_ratio: float,
) -> list[tuple[str, dict, float]]:
    """Apply dynamic threshold filtering."""
    if not chunks:
        return []
    chunks.sort(key=lambda x: x[2], reverse=True)
    best = chunks[0][2]
    threshold = max(score_threshold, best * dynamic_ratio)
    return [(d, m, s) for d, m, s in chunks if s >= threshold]


def _passes_relevance_gate(
    notes: list[tuple[str, dict, float]],
    code: list[tuple[str, dict, float]],
    graph_str: str,
    trace: QueryTrace,
) -> bool:
    """Check if retrieved context meets the relevance policy.

    Returns True if context quality is sufficient for injection.
    """
    policy = settings.context_policy
    all_chunks = notes + code
    if not all_chunks and not graph_str:
        trace.context_rejected_reason = "Nenhum chunk ou contexto de grafo encontrado."
        return False

    if all_chunks:
        best_score = max(s for _, _, s in all_chunks)
        if best_score < policy.min_relevance_score:
            trace.context_rejected_reason = (
                f"Melhor score ({best_score:.2f}) abaixo do mínimo ({policy.min_relevance_score:.2f})."
            )
            return False

        if len(all_chunks) < policy.min_relevant_chunks:
            trace.context_rejected_reason = (
                f"Apenas {len(all_chunks)} chunk(s) — mínimo é {policy.min_relevant_chunks}."
            )
            return False

    return True


# === Main entry point ===

def build_rag_context(
    query: str,
    *,
    context_mode: str | None = None,
    trace: QueryTrace | None = None,
) -> tuple[str, bool, str]:
    """Multi-strategy search with optional graph augmentation.

    Now integrates with the router to skip retrieval entirely for
    general questions (NO_CONTEXT mode).

    Returns (context_string, was_relevant, sources_used).
    sources_used: "none" | "rag" | "graph" | "rag+graph"
    """
    cfg = settings.retrieval
    mode = context_mode or cfg.context_mode

    # Create trace if not provided
    if trace is None:
        trace = QueryTrace(query=query)

    # Get routing decision (LLM or heuristic)
    intent, decision = detect_intent_full(query, mode)
    trace.route_mode = decision.mode.value
    trace.route_reason = decision.reason
    trace.route_method = decision.method
    trace.route_confidence = decision.confidence
    trace.route_latency_ms = decision.latency_ms

    # NO_CONTEXT: skip all retrieval
    if decision.mode == ContextMode.NO_CONTEXT:
        trace.context_accepted = False
        trace.context_rejected_reason = "Router: pergunta geral, sem necessidade de contexto local."
        trace.sources_used = "none"
        trace.log_summary()
        return "", False, "none"

    # CLARIFY: also skip retrieval, let the LLM ask for clarification
    if decision.mode == ContextMode.CLARIFY:
        trace.context_accepted = False
        trace.context_rejected_reason = "Router: pergunta ambígua, a pedir esclarecimento."
        trace.sources_used = "none"
        trace.log_summary()
        return "", False, "none"

    notes_relevant: list[tuple[str, dict, float]] = []
    code_relevant: list[tuple[str, dict, float]] = []
    graph_context_str = ""

    # --- Adaptive top_k ---
    complexity = _estimate_complexity(query)
    trace.query_complexity = complexity
    if complexity == "simple":
        effective_k = max(3, cfg.top_k // 3)
    elif complexity == "complex":
        effective_k = min(cfg.top_k * 2, 20)
    else:
        effective_k = cfg.top_k
    trace.effective_top_k = effective_k

    # Strategies 1-2: Notas Obsidian (vector search + keyword variant)
    if intent.use_notes:
        try:
            store = _get_store()

            # 1. Primary search
            primary = _search_chroma(store, query, effective_k, collection="obsidian_vault")
            trace.notes_retrieved += len(primary)

            # 2. Keyword variant
            keywords = _extract_keywords(query)
            secondary = []
            if keywords != query.lower().strip() and len(keywords) > 3:
                secondary = _search_chroma(store, keywords, effective_k, collection="obsidian_vault")
                trace.notes_retrieved += len(secondary)

            # Deduplicate + filter navigation + threshold
            all_notes = _deduplicate(primary + secondary)
            all_notes = [
                (doc, meta, score) for doc, meta, score in all_notes
                if not _is_navigation_chunk(meta, doc)
            ]
            notes_relevant = _apply_threshold(all_notes, cfg.score_threshold, cfg.dynamic_threshold_ratio)
            notes_relevant = notes_relevant[:effective_k]

            trace.notes_after_filter = len(notes_relevant)
            if notes_relevant:
                trace.best_note_score = notes_relevant[0][2]
                trace.note_sources = [
                    m.get("note_title", m.get("source_path", "?"))
                    for _, m, _ in notes_relevant[:5]
                ]

        except Exception as exc:
            log.warning("Notes search failed: %s", exc)
            notes_relevant = []

    # Strategy 3: Code repo search
    if intent.use_code and settings.repos.paths:
        try:
            store = _get_store()
            code_col_name = settings.repos.collection_name
            code_results = _search_chroma(store, query, effective_k, collection=code_col_name)
            trace.code_retrieved += len(code_results)

            # Keyword variant para código
            keywords = _extract_keywords(query)
            if keywords != query.lower().strip() and len(keywords) > 3:
                code_kw = _search_chroma(store, keywords, effective_k, collection=code_col_name)
                code_results = code_results + code_kw
                trace.code_retrieved += len(code_kw)

            # Deduplicate + threshold
            code_dedup = _deduplicate(code_results)
            code_relevant = _apply_threshold(code_dedup, cfg.score_threshold, cfg.dynamic_threshold_ratio)
            code_relevant = code_relevant[:effective_k]

            trace.code_after_filter = len(code_relevant)
            if code_relevant:
                trace.best_code_score = code_relevant[0][2]
                trace.code_sources = [
                    f"{m.get('repo_name', '?')}:{m.get('source_path', '?')}"
                    for _, m, _ in code_relevant[:5]
                ]

        except Exception as exc:
            log.warning("Code search failed: %s", exc)
            code_relevant = []

    # Strategy 4: Graph context
    if intent.use_graph and code_relevant:
        try:
            from obsidian_rag.retrieval.graph_context import build_graph_context

            budget = allocate_budget(
                cfg.token_budget,
                has_notes=bool(notes_relevant),
                has_code=bool(code_relevant),
                has_graph=True,
            )

            graph_context_str = build_graph_context(
                code_relevant,
                query,
                max_neighbors=cfg.graph_max_neighbors,
                max_communities=cfg.graph_max_communities,
                token_budget=budget["graph"],
            )
        except Exception as exc:
            log.warning("Graph context failed: %s", exc)
            graph_context_str = ""

    # Graph-only mode (no code chunks needed)
    if intent.use_graph and not code_relevant and not intent.use_code:
        try:
            from obsidian_rag.graph.cache import graph_cache
            from obsidian_rag.retrieval.graph_context import build_graph_context

            synthetic_chunks: list[tuple[str, dict, float]] = []
            for repo_name in graph_cache.list_graph_repos():
                summaries = graph_cache.get_summaries(repo_name)
                if summaries:
                    gods = graph_cache.get_gods(repo_name)
                    for god in gods[:5]:
                        node = graph_cache.get_node_by_id(repo_name, god["id"])
                        if node:
                            synthetic_chunks.append(("", {
                                "repo_name": repo_name,
                                "source_path": node.get("source_file", ""),
                                "section_header": node.get("label", ""),
                            }, 0.5))

            if synthetic_chunks:
                graph_context_str = build_graph_context(
                    synthetic_chunks,
                    query,
                    max_neighbors=cfg.graph_max_neighbors,
                    max_communities=cfg.graph_max_communities,
                    token_budget=cfg.token_budget,
                )
        except Exception as exc:
            log.warning("Graph-only context failed: %s", exc)
            graph_context_str = ""

    # ── Relevance gate ──────────────────────────────────────────────────
    if not _passes_relevance_gate(notes_relevant, code_relevant, graph_context_str, trace):
        trace.context_accepted = False
        trace.sources_used = "none"
        if settings.context_policy.log_weak_context:
            log.info(
                "Context rejected for query: %s — %s",
                query[:80], trace.context_rejected_reason,
            )
        trace.log_summary()
        return "", False, "none"

    trace.context_accepted = True

    # Budget allocation
    budget = allocate_budget(
        cfg.token_budget,
        has_notes=bool(notes_relevant),
        has_code=bool(code_relevant),
        has_graph=bool(graph_context_str),
    )

    # Apply budget truncation
    if notes_relevant:
        notes_relevant = truncate_chunks(notes_relevant, budget["notes"])
    if code_relevant:
        code_relevant = truncate_chunks(code_relevant, budget["code"])
    if graph_context_str and budget["graph"]:
        graph_context_str = truncate_text(graph_context_str, budget["graph"])

    context_parts: list[str] = []

    # Notes block
    if notes_relevant:
        lines = ["[CONTEXTO DAS NOTAS PESSOAIS]"]
        for doc, meta, score in notes_relevant:
            display = meta.get("display_text", doc)
            title = meta.get("note_title", "")
            section = meta.get("section_header", "")
            label = f"[{title} / {section}]" if section else f"[{title}]"
            lines.append(f"{label}  score={score:.2f}")
            lines.append(display)
            lines.append("")
        lines.append("[/CONTEXTO DAS NOTAS]")
        context_parts.append("\n".join(lines))

    # Code block
    if code_relevant:
        by_repo: dict[str, list[tuple[str, dict, float]]] = {}
        for doc, meta, score in code_relevant:
            repo = meta.get("repo_name", "repo")
            by_repo.setdefault(repo, []).append((doc, meta, score))

        for repo_name, repo_chunks in by_repo.items():
            lines = [f"[CONTEXTO DO CÓDIGO — {repo_name}]"]
            for doc, meta, score in repo_chunks:
                display = meta.get("display_text", doc)
                symbol = meta.get("section_header", "")
                fpath = meta.get("source_path", "")
                label = f"[{fpath} / {symbol}]" if symbol else f"[{fpath}]"
                lines.append(f"{label}  score={score:.2f}")
                lines.append(display)
                lines.append("")
            lines.append(f"[/CONTEXTO DO CÓDIGO — {repo_name}]")
            context_parts.append("\n".join(lines))

    # Graph block
    if graph_context_str:
        context_parts.append(graph_context_str)

    full_context = "\n\n".join(context_parts)

    # Determine sources used
    sources: set[str] = set()
    if notes_relevant or code_relevant:
        sources.add("rag")
    if graph_context_str:
        sources.add("graph")
    sources_used = "+".join(sorted(sources)) or "none"
    trace.sources_used = sources_used

    # Append context-aware instruction (domain-neutral)
    instruction = get_context_instruction(sources_used)
    if instruction:
        full_context += "\n\n" + instruction

    trace.log_summary()
    return full_context, True, sources_used


def should_use_rag(model: str) -> bool:
    """Check if model has RAG enabled in config."""
    return bool(settings.models.get(model, False))
