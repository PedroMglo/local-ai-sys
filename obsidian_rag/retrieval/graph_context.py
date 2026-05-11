"""Constrói contexto de grafo para injecção no prompt RAG.

Para cada chunk de código relevante, procura o nó correspondente no
knowledge graph e enriquece com:
  - Sumário da comunidade
  - Vizinhos directos (calls, imports, uses)
  - Flags de god node
"""

from __future__ import annotations

import logging
from collections import defaultdict

from obsidian_rag.pipeline.graph.cache import graph_cache
from obsidian_rag.retrieval.budget import estimate_tokens

log = logging.getLogger("obsidian_rag")

# Relações interessantes para contexto (skip contains, method, rationale_for)
_INTERESTING_RELS = {"calls", "imports_from", "uses"}


def build_graph_context(
    code_chunks: list[tuple[str, dict, float]],
    query: str,
    *,
    max_neighbors: int = 5,
    max_communities: int = 3,
    token_budget: int = 1000,
) -> str:
    """Constrói bloco de contexto estrutural a partir de code chunks relevantes.

    Para cada chunk que tem match no knowledge graph:
      1. Identifica o nó e a sua comunidade
      2. Busca sumário da comunidade (pré-computado por enrich.py)
      3. Busca vizinhos directos (outgoing/incoming)
      4. Marca god nodes

    Args:
        code_chunks: lista de (doc, metadata, score) — chunks de código relevantes
        query: texto da query original (para futuro ranking contextual)
        max_neighbors: máx vizinhos por nó
        max_communities: máx comunidades com sumário no output
        token_budget: tokens máximos para este bloco

    Returns:
        String formatada para injecção, ou "" se sem dados.
    """
    # Agrupar chunks por repo
    by_repo: dict[str, list[tuple[str, dict, float]]] = defaultdict(list)
    for doc, meta, score in code_chunks:
        repo = meta.get("repo_name", "")
        if repo:
            by_repo[repo].append((doc, meta, score))

    if not by_repo:
        return ""

    output_parts: list[str] = []
    total_tokens = 0
    total_nodes_matched = 0
    total_communities = 0

    for repo_name, repo_chunks in by_repo.items():
        # Check if this repo has a graph
        graph_data = graph_cache.get_graph(repo_name)
        if graph_data is None:
            log.debug("Graph: no graph data for repo %s", repo_name)
            continue

        summaries = graph_cache.get_summaries(repo_name)
        gods_list = graph_cache.get_gods(repo_name)
        god_ids = {g["id"] for g in gods_list}

        # Track which communities we've already summarized
        summarized_communities: set[str] = set()
        seen_nodes: set[str] = set()
        repo_lines: list[str] = []

        for _doc, meta, _score in repo_chunks:
            source_file = meta.get("source_path", "")
            section_header = meta.get("section_header", "")

            if not source_file or not section_header:
                continue

            # Lookup node in graph
            node = graph_cache.lookup_node(repo_name, source_file, section_header)
            if node is None:
                continue

            node_id = node["id"]
            if node_id in seen_nodes:
                continue
            seen_nodes.add(node_id)
            node_label = node.get("label", section_header)
            community = str(node.get("community", ""))
            is_god = node_id in god_ids

            # Community summary (max N communities)
            if community and community in summaries and community not in summarized_communities:
                if len(summarized_communities) < max_communities:
                    summary = summaries[community]
                    repo_lines.append(f"Comunidade {community}: {summary}")
                    summarized_communities.add(community)

            # Node info with neighbors
            god_tag = " [god-node]" if is_god else ""
            node_line = f"{node_label} ({source_file}){god_tag}:"

            # Get neighbors
            neighbors = graph_cache.get_neighbors(
                repo_name, node_id, max_results=max_neighbors * 2,
            )

            outgoing: list[str] = []
            incoming: list[str] = []
            for nb in neighbors:
                rel = nb["relation"]
                if rel not in _INTERESTING_RELS:
                    continue
                label = nb["label"]
                if nb["direction"] == "outgoing":
                    outgoing.append(f"{label} ({rel})")
                else:
                    incoming.append(f"{label} ({rel})")

            if not outgoing and not incoming:
                continue

            total_nodes_matched += 1
            repo_lines.append(node_line)
            if outgoing:
                repo_lines.append(f"  chama/usa: {', '.join(outgoing[:max_neighbors])}")
            if incoming:
                repo_lines.append(f"  chamado por: {', '.join(incoming[:max_neighbors])}")

        if not repo_lines:
            continue

        block = f"[CONTEXTO ESTRUTURAL — {repo_name}]\n"
        block += "\n".join(repo_lines)
        block += f"\n[/CONTEXTO ESTRUTURAL — {repo_name}]"

        block_tokens = estimate_tokens(block)
        if total_tokens + block_tokens > token_budget and output_parts:
            log.debug("Graph: budget exceeded, stopping at repo %s", repo_name)
            break

        output_parts.append(block)
        total_tokens += block_tokens
        total_communities += len(summarized_communities)

    log.info(
        "Graph context: %d nodes matched, %d communities, %d tokens across %d repos",
        total_nodes_matched, total_communities, total_tokens, len(output_parts),
    )

    return "\n\n".join(output_parts)
