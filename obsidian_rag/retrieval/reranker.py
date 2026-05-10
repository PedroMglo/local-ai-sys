"""Optional cross-encoder reranker via Ollama.

Uses a fast LLM to score relevance of retrieved chunks against the
original query. Disabled by default (adds latency).
"""

from __future__ import annotations

import logging
import re

import httpx

from obsidian_rag.config import settings

log = logging.getLogger("obsidian_rag")

_THINK_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL)

_RERANK_PROMPT = (
    "Avalia a relevância do seguinte texto para responder à pergunta.\n"
    "Devolve APENAS um número de 0 a 10, onde:\n"
    "  0 = completamente irrelevante\n"
    "  10 = directamente responde à pergunta\n\n"
    "Pergunta: {query}\n\n"
    "Texto:\n{chunk}\n\n"
    "Score (0-10):"
)

_SCORE_PATTERN = re.compile(r"\b(\d{1,2})\b")


def rerank_chunks(
    chunks: list[tuple[str, dict, float]],
    query: str,
) -> list[tuple[str, dict, float]]:
    """Rerank chunks using LLM scoring.

    Args:
        chunks: list of (doc, metadata, vector_score)
        query: original user query

    Returns:
        Reranked list, filtered by min_score, sorted by reranker score.
    """
    cfg = settings.reranker
    if not cfg.enabled or not chunks:
        return chunks

    # Only evaluate top candidates
    candidates = chunks[:cfg.top_k_candidates]
    scored: list[tuple[str, dict, float]] = []

    for doc, meta, vec_score in candidates:
        display = meta.get("display_text", doc)
        # Truncate very long chunks for reranking
        text_for_scoring = display[:1500] if len(display) > 1500 else display

        score = _score_chunk(query, text_for_scoring, cfg.model)
        if score is not None and score >= cfg.min_score:
            # Combine: 60% reranker + 40% vector score (normalized)
            combined = 0.6 * score + 0.4 * vec_score
            scored.append((doc, meta, combined))
        elif score is None:
            # LLM scoring failed — keep with original score
            scored.append((doc, meta, vec_score))

    scored.sort(key=lambda x: x[2], reverse=True)
    log.info("Reranker: %d/%d chunks passed (min_score=%.1f)", len(scored), len(candidates), cfg.min_score)
    return scored


def _score_chunk(query: str, chunk_text: str, model: str) -> float | None:
    """Score a single chunk's relevance (0.0–1.0)."""
    prompt = _RERANK_PROMPT.format(query=query, chunk=chunk_text)
    try:
        resp = httpx.post(
            f"{settings.ollama.base_url}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.0, "num_predict": 8},
            },
            timeout=10.0,
        )
        resp.raise_for_status()
        raw = resp.json().get("response", "")
        clean = _THINK_PATTERN.sub("", raw).strip()

        match = _SCORE_PATTERN.search(clean)
        if match:
            val = int(match.group(1))
            return min(val, 10) / 10.0
    except Exception as exc:
        log.debug("Reranker scoring failed: %s", exc)

    return None
