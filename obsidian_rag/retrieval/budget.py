"""Gestão de budget de tokens para contexto RAG.

Distribui o budget total entre as fontes activas (notas, código, grafo)
e trunca contexto por chunks inteiros para caber no budget.
"""

from __future__ import annotations

import re

# Regex to split text into token-like units (words, punctuation, numbers)
_TOKEN_RE = re.compile(r"""\w+|[^\w\s]""", re.UNICODE)


def estimate_tokens(text: str) -> int:
    """Estimate token count using word-boundary heuristic.

    Uses regex tokenisation that splits on word boundaries and punctuation.
    More accurate than simple char/4 for multilingual text (PT + EN + code).
    Empirically ~1.3 tokens per word for LLaMA/BERT tokenizers.
    """
    if not text:
        return 0
    words = _TOKEN_RE.findall(text)
    # Most subword tokenizers produce ~1.3 tokens per whitespace-separated word.
    # For code, the ratio is slightly higher (~1.5) due to snake_case splitting.
    return max(1, int(len(words) * 1.3))


def allocate_budget(
    total: int,
    *,
    has_notes: bool,
    has_code: bool,
    has_graph: bool,
) -> dict[str, int]:
    """Distribui token budget entre fontes activas.

    Política:
      - Só notas: 100%
      - Só código: 100%
      - Só grafo: 100%
      - Notas + código: 50/50
      - Notas + código + grafo: 40/40/20
      - Código + grafo: 60/40
      - Notas + grafo: 60/40
    """
    active = sum([has_notes, has_code, has_graph])
    if active == 0:
        return {"notes": 0, "code": 0, "graph": 0}

    if active == 1:
        return {
            "notes": total if has_notes else 0,
            "code": total if has_code else 0,
            "graph": total if has_graph else 0,
        }

    if active == 3:
        return {
            "notes": int(total * 0.40),
            "code": int(total * 0.40),
            "graph": int(total * 0.20),
        }

    # active == 2
    if has_notes and has_code:
        return {"notes": total // 2, "code": total // 2, "graph": 0}
    if has_code and has_graph:
        return {"notes": 0, "code": int(total * 0.60), "graph": int(total * 0.40)}
    # has_notes and has_graph
    return {"notes": int(total * 0.60), "code": 0, "graph": int(total * 0.40)}


def truncate_chunks(
    chunks: list[tuple[str, dict, float]],
    budget: int,
) -> list[tuple[str, dict, float]]:
    """Trunca lista de chunks para caber no budget de tokens.

    Corta por chunks inteiros (nunca mid-chunk). Chunks já devem
    estar ordenados por score descendente.
    """
    result = []
    used = 0
    for doc, meta, score in chunks:
        display = meta.get("display_text", doc)
        tokens = estimate_tokens(display)
        if used + tokens > budget and result:
            break
        result.append((doc, meta, score))
        used += tokens
    return result


def truncate_text(text: str, budget: int) -> str:
    """Trunca texto para caber no budget, cortando por linhas."""
    if estimate_tokens(text) <= budget:
        return text
    lines = text.splitlines(keepends=True)
    result: list[str] = []
    used = 0
    for line in lines:
        tokens = estimate_tokens(line)
        if used + tokens > budget and result:
            break
        result.append(line)
        used += tokens
    return "".join(result).rstrip()
