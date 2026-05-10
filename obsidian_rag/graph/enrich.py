"""Pós-processamento de grafos Graphify para enriquecimento do vault Obsidian.

Funcionalidades:
  1. Resumos de comunidades via Ollama (com cache)
  2. Detecção de ficheiros partilhados entre comunidades (cross-links)
  3. Diagramas Mermaid de call-flow por comunidade
  4. Tags inferidas por path dos source_files
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from obsidian_rag.config import settings

# ---------------------------------------------------------------------------
# 1. Community summaries via Ollama
# ---------------------------------------------------------------------------

_SUMMARY_PROMPT = """\
Analisa esta comunidade de código e descreve o seu propósito em 2-3 frases em Português.

Repositório: {repo_name}
Comunidade: {community_id} ({member_count} membros)

Ficheiros principais:
{files_list}

Símbolos mais conectados (god nodes desta comunidade):
{top_symbols}

Relações internas (top edges):
{top_edges}

Responde APENAS com a descrição, sem título, sem bullet points, sem formatação Markdown."""


def _call_ollama(prompt: str, model: str | None = None) -> str:
    """Chama Ollama local via API HTTP (sem dependência openai)."""
    import urllib.error
    import urllib.request

    mdl = model or settings.graphify.model or "qwen3:8b"
    base = settings.ollama.base_url.rstrip("/")

    payload = json.dumps({
        "model": mdl,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 512, "temperature": 0.3},
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:  # nosec B310  # nosemgrep: python.lang.security.audit.dynamic-urllib-use-detected.dynamic-urllib-use-detected
            data = json.loads(resp.read())
            raw = data.get("response", "").strip()
            # deepseek-r1 wraps in <think>...</think> — strip it
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
            return raw
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        return f"(sumário indisponível: {e})"


def _load_cache(cache_path: Path) -> dict:  # type: ignore[type-arg]
    if cache_path.exists():
        try:
            with open(cache_path, encoding="utf-8") as f:
                data = json.load(f)
                return dict(data) if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_cache(cache_path: Path, data: dict) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache_path.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp.rename(cache_path)


def summarize_communities(
    graph_data: dict,
    analysis: dict,
    repo_name: str,
    cache_dir: Path,
    *,
    force: bool = False,
) -> dict[str, str]:
    """Gera resumos LLM para todas as comunidades com ≥ 5 membros.

    Retorna {community_id: summary_text}.
    Cache em cache_dir/community_summaries.json.
    """
    cache_path = cache_dir / "community_summaries.json"
    cache = {} if force else _load_cache(cache_path)

    communities: dict[str, list[str]] = analysis.get("communities", {})
    nodes_by_id = {n["id"]: n for n in graph_data.get("nodes", [])}
    links = graph_data.get("links", [])

    summaries: dict[str, str] = {}

    for cid, member_ids in communities.items():
        if len(member_ids) < 5:
            continue

        if cid in cache and not force:
            summaries[cid] = cache[cid]
            continue

        # Build context for prompt
        member_set = set(member_ids)
        files: dict[str, list[str]] = defaultdict(list)
        for mid in member_ids:
            node = nodes_by_id.get(mid, {})
            sf = node.get("source_file", "")
            label = node.get("label", mid)
            if sf:
                files[sf].append(label)

        files_list = "\n".join(
            f"  {f}: {', '.join(syms[:5])}" + (f" (+{len(syms)-5})" if len(syms) > 5 else "")
            for f, syms in sorted(files.items(), key=lambda x: -len(x[1]))[:10]
        )

        # Top connected nodes in this community
        degree: dict[str, int] = defaultdict(int)
        internal_edges: list[tuple[str, str, str]] = []
        for link in links:
            s, t = link["source"], link["target"]
            if s in member_set:
                degree[s] += 1
            if t in member_set:
                degree[t] += 1
            if s in member_set and t in member_set:
                internal_edges.append((
                    nodes_by_id.get(s, {}).get("label", s),
                    link.get("relation", "?"),
                    nodes_by_id.get(t, {}).get("label", t),
                ))

        top_nodes = sorted(degree.items(), key=lambda x: -x[1])[:5]
        top_symbols = "\n".join(
            f"  {nodes_by_id.get(nid, {}).get('label', nid)} (degree {d})"
            for nid, d in top_nodes
        )

        top_edges = "\n".join(
            f"  {src} --{rel}--> {tgt}"
            for src, rel, tgt in internal_edges[:10]
        )

        prompt = _SUMMARY_PROMPT.format(
            repo_name=repo_name,
            community_id=cid,
            member_count=len(member_ids),
            files_list=files_list or "  (sem ficheiros identificados)",
            top_symbols=top_symbols or "  (sem dados)",
            top_edges=top_edges or "  (sem edges internas)",
        )

        print(f"    [Enrich] Gerando sumário para Community-{cid}...")
        summary = _call_ollama(prompt)
        summaries[cid] = summary
        cache[cid] = summary

    _save_cache(cache_path, cache)
    return summaries


# ---------------------------------------------------------------------------
# 2. Cross-community links (shared files)
# ---------------------------------------------------------------------------

def detect_cross_community_links(
    graph_data: dict,
    analysis: dict,
) -> dict[str, list[dict[str, Any]]]:
    """Detecta comunidades relacionadas via ficheiros partilhados.

    Retorna {community_id: [{other_id, shared_files, shared_count}]}.
    """
    communities: dict[str, list[str]] = analysis.get("communities", {})
    nodes_by_id = {n["id"]: n for n in graph_data.get("nodes", [])}

    # Build community → source_files mapping
    community_files: dict[str, set[str]] = defaultdict(set)
    for cid, member_ids in communities.items():
        if len(member_ids) < 5:
            continue
        for mid in member_ids:
            sf = nodes_by_id.get(mid, {}).get("source_file", "")
            if sf:
                community_files[cid].add(sf)

    # Find pairs with shared files
    result: dict[str, list[dict]] = defaultdict(list)
    cids = sorted(community_files.keys(), key=int)
    for i, c1 in enumerate(cids):
        for c2 in cids[i + 1:]:
            common = community_files[c1] & community_files[c2]
            if common:
                entry = {
                    "shared_files": sorted(common),
                    "shared_count": len(common),
                }
                result[c1].append({"other_id": c2, **entry})
                result[c2].append({"other_id": c1, **entry})

    # Sort by shared_count desc
    for cid in result:
        result[cid].sort(key=lambda x: -x["shared_count"])

    return dict(result)


# ---------------------------------------------------------------------------
# 3. Mermaid call-flow diagrams
# ---------------------------------------------------------------------------

def _sanitize_mermaid_id(label: str) -> str:
    """Sanitize label for Mermaid node ids."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", label)


def generate_community_mermaid(
    community_id: str,
    member_ids: list[str],
    graph_data: dict,
    *,
    max_edges: int = 12,
) -> str | None:
    """Gera diagrama Mermaid graph LR com os top call flows de uma comunidade.

    Retorna string Mermaid ou None se < 3 edges internas.
    """
    nodes_by_id = {n["id"]: n for n in graph_data.get("nodes", [])}
    member_set = set(member_ids)
    links = graph_data.get("links", [])

    # Collect internal edges (calls, imports_from, uses — skip contains/method/rationale)
    interesting_rels = {"calls", "imports_from", "uses"}
    internal: list[tuple[str, str, str, float]] = []
    for link in links:
        s, t = link["source"], link["target"]
        rel = link.get("relation", "?")
        if s in member_set and t in member_set and rel in interesting_rels:
            src_label = nodes_by_id.get(s, {}).get("label", s)
            tgt_label = nodes_by_id.get(t, {}).get("label", t)
            weight = link.get("weight", 1.0)
            internal.append((src_label, rel, tgt_label, weight))

    if len(internal) < 3:
        return None

    # Sort by weight desc, take top N
    internal.sort(key=lambda x: -x[3])
    top = internal[:max_edges]

    lines = ["graph LR"]
    seen_ids: dict[str, str] = {}
    for src, rel, tgt, _ in top:
        src_id = _sanitize_mermaid_id(src)
        tgt_id = _sanitize_mermaid_id(tgt)

        # First occurrence: define with label
        if src_id not in seen_ids:
            seen_ids[src_id] = src
        if tgt_id not in seen_ids:
            seen_ids[tgt_id] = tgt

        arrow = f"--{rel}-->" if rel != "calls" else "-->"
        lines.append(f"    {src_id}[\"{src}\"] {arrow} {tgt_id}[\"{tgt}\"]")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 4. Tags inferred from source file paths
# ---------------------------------------------------------------------------

_PATH_TAG_RULES: list[tuple[str, str]] = [
    ("tests/", "testing"),
    ("test_", "testing"),
    ("pipeline/chunk", "chunking"),
    ("pipeline/embed", "embedding"),
    ("pipeline/search", "search"),
    ("pipeline/agents", "agents"),
    ("pipeline/config", "config"),
    ("pipeline/models", "models"),
    ("pipeline/main", "pipeline-core"),
    ("pipeline/utils", "utils"),
    ("pipeline/logger", "logging"),
    ("pipeline/catalog", "catalog"),
    ("gpu_check", "gpu"),
    ("config", "config"),
]


def infer_community_tags(
    member_ids: list[str],
    nodes_by_id: dict[str, dict],
) -> list[str]:
    """Infere tags para uma comunidade com base nos source_file paths dos membros."""
    files = set()
    for mid in member_ids:
        sf = nodes_by_id.get(mid, {}).get("source_file", "")
        if sf:
            files.add(sf)

    tags = set()
    for f in files:
        for pattern, tag in _PATH_TAG_RULES:
            if pattern in f:
                tags.add(tag)

    return sorted(tags)


def infer_repo_tags(
    graph_data: dict,
    analysis: dict,
) -> dict[str, list[str]]:
    """Infere tags para todas as comunidades de um repo.

    Retorna {community_id: [tag1, tag2, ...]}.
    """
    communities = analysis.get("communities", {})
    nodes_by_id = {n["id"]: n for n in graph_data.get("nodes", [])}

    result = {}
    for cid, member_ids in communities.items():
        if len(member_ids) < 5:
            continue
        result[cid] = infer_community_tags(member_ids, nodes_by_id)

    return result
