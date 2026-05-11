"""Cache inteligente de graph data com invalidação por ficheiro.

Carrega graph.json, community_summaries.json e .graphify_analysis.json
por repo, mantém em memória, e invalida automaticamente quando os
ficheiros mudam (mtime + size) ou o TTL expira.

Usage:
    from obsidian_rag.graph.cache import graph_cache

    data = graph_cache.get_graph("SPEECH-LAB")
    node = graph_cache.lookup_node("SPEECH-LAB", "pipeline/main.py", "process_one")
    summaries = graph_cache.get_summaries("SPEECH-LAB")
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from obsidian_rag.config import settings

logger = logging.getLogger(__name__)


@dataclass
class _RepoGraphData:
    """Cached data for a single repo's graph."""
    graph_data: dict
    analysis: dict | None
    summaries: dict[str, str]
    nodes_by_id: dict[str, dict]
    # Index: (source_file, norm_label) → node dict
    nodes_index: dict[tuple[str, str], dict] = field(default_factory=dict)
    # File stat at load time
    mtime: float = 0.0
    size: int = 0
    loaded_at: float = 0.0


def _normalize_label(label: str) -> str:
    """Strip parens, dots, chunk suffixes, lowercase for fuzzy matching.

    Handles chunk section headers like "process_one (parte 2)" and
    graph labels like "process_one()".
    """
    import re
    s = label.lower().strip()
    # Strip chunk part suffixes: " (parte 1)", " (parte 2)", etc.
    s = re.sub(r"\s*\(parte\s+\d+\)$", "", s)
    # Strip module-level suffix: "main.py (module-level)"
    s = re.sub(r"\s*\(module-level\)$", "", s)
    # Strip trailing parens (function calls)
    s = s.rstrip("()")
    # Strip leading dots
    s = s.lstrip(".")
    return s


def _build_nodes_index(nodes: list[dict]) -> dict[tuple[str, str], dict]:
    """Build (source_file, norm_label) → node index."""
    index: dict[tuple[str, str], dict] = {}
    for node in nodes:
        sf = node.get("source_file", "")
        label = node.get("label", "")
        if sf and label:
            key = (sf, _normalize_label(label))
            index[key] = node
    return index


def _safe_json_load(path: Path) -> dict | None:  # type: ignore[type-arg]
    """Load JSON safely, returning None on any error."""
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
            return dict(data) if isinstance(data, dict) else None
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to load %s: %s", path, e)
        return None


def _file_stat(path: Path) -> tuple[float, int]:
    """Return (mtime, size) or (0, 0) if file doesn't exist."""
    try:
        st = os.stat(path)
        return (st.st_mtime, st.st_size)
    except OSError:
        return (0.0, 0)


class GraphCache:
    """Per-repo graph cache with automatic file-based invalidation."""

    def __init__(self) -> None:
        self._repos: dict[str, _RepoGraphData] = {}

    def _graph_json_path(self, repo_name: str) -> Path | None:
        """Find graph.json path for a repo."""
        for repo_path in settings.repos.paths:
            p = Path(repo_path)
            if p.name == repo_name:
                gp = settings.graphify.output_dir / repo_name / "graphify-out" / "graph.json"
                return gp if gp.exists() else None
        return None

    def _analysis_path(self, repo_name: str) -> Path | None:
        """Find .graphify_analysis.json path for a repo."""
        for repo_path in settings.repos.paths:
            p = Path(repo_path)
            if p.name == repo_name:
                ap = settings.graphify.output_dir / repo_name / "graphify-out" / ".graphify_analysis.json"
                return ap if ap.exists() else None
        return None

    def _summaries_path(self, repo_name: str) -> Path | None:
        """Find community_summaries.json path for a repo."""
        for repo_path in settings.repos.paths:
            p = Path(repo_path)
            if p.name == repo_name:
                sp = settings.graphify.output_dir / repo_name / "graphify-out" / "community_summaries.json"
                return sp if sp.exists() else None
        return None

    def _is_stale(self, repo_name: str) -> bool:
        """Check if cached data is stale (file changed or TTL expired)."""
        cached = self._repos.get(repo_name)
        if cached is None:
            return True

        ttl = settings.retrieval.graph_cache_ttl
        now = time.time()

        # TTL check: only stat the file if TTL expired
        if now - cached.loaded_at < ttl:
            return False

        # File changed check
        gp = self._graph_json_path(repo_name)
        if gp is None:
            return True
        mtime, size = _file_stat(gp)
        return mtime != cached.mtime or size != cached.size

    def _load_repo(self, repo_name: str) -> _RepoGraphData | None:
        """Load all graph data for a repo from disk."""
        gp = self._graph_json_path(repo_name)
        if gp is None:
            return None

        graph_data = _safe_json_load(gp)
        if graph_data is None:
            return None

        mtime, size = _file_stat(gp)

        # Analysis
        ap = self._analysis_path(repo_name)
        analysis = _safe_json_load(ap) if ap is not None else None

        # Community summaries
        sp = self._summaries_path(repo_name)
        summaries = _safe_json_load(sp) if sp is not None else None
        if summaries is None:
            summaries = {}

        nodes = graph_data.get("nodes", [])
        nodes_by_id = {n["id"]: n for n in nodes}
        nodes_index = _build_nodes_index(nodes)

        return _RepoGraphData(
            graph_data=graph_data,
            analysis=analysis,
            summaries=summaries,
            nodes_by_id=nodes_by_id,
            nodes_index=nodes_index,
            mtime=mtime,
            size=size,
            loaded_at=time.time(),
        )

    def _ensure_loaded(self, repo_name: str) -> _RepoGraphData | None:
        """Ensure repo data is loaded and fresh."""
        if self._is_stale(repo_name):
            data = self._load_repo(repo_name)
            if data is not None:
                self._repos[repo_name] = data
                logger.info("GraphCache: loaded %s (%d nodes)", repo_name, len(data.nodes_by_id))
            elif repo_name in self._repos:
                del self._repos[repo_name]
            return data
        return self._repos.get(repo_name)

    # --- Public API ---

    def get_graph(self, repo_name: str) -> dict | None:
        """Return raw graph_data dict or None."""
        data = self._ensure_loaded(repo_name)
        return data.graph_data if data else None

    def get_summaries(self, repo_name: str) -> dict[str, str]:
        """Return {community_id: summary_text}."""
        data = self._ensure_loaded(repo_name)
        return data.summaries if data else {}

    def get_analysis(self, repo_name: str) -> dict | None:
        """Return parsed .graphify_analysis.json or None."""
        data = self._ensure_loaded(repo_name)
        return data.analysis if data else None

    def lookup_node(
        self, repo_name: str, source_file: str, symbol: str,
    ) -> dict | None:
        """Map (source_file, section_header) from chunk metadata to graph node.

        Uses normalized label matching: strips parens/dots, case-insensitive.
        Falls back to substring match if exact match fails.
        """
        data = self._ensure_loaded(repo_name)
        if data is None:
            return None

        norm = _normalize_label(symbol)

        # Exact match
        node = data.nodes_index.get((source_file, norm))
        if node is not None:
            return node

        # Try with just the filename (strip leading path components)
        # Handles: chunk has "app/pipeline/main.py", graph has "pipeline/main.py"
        for (sf, nlabel), n in data.nodes_index.items():
            if nlabel != norm:
                continue
            # Check if source_file ends with sf or sf ends with source_file
            if source_file.endswith(sf) or sf.endswith(source_file):
                return n

        # Fallback: substring match within same or similar source_file
        for (sf, nlabel), n in data.nodes_index.items():
            sf_match = sf == source_file or source_file.endswith(sf) or sf.endswith(source_file)
            if sf_match and (norm in nlabel or nlabel in norm):
                return n

        return None

    def get_node_by_id(self, repo_name: str, node_id: str) -> dict | None:
        """Get node dict by ID."""
        data = self._ensure_loaded(repo_name)
        if data is None:
            return None
        return data.nodes_by_id.get(node_id)

    def get_neighbors(
        self, repo_name: str, node_id: str, *, max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Get direct neighbors of a node from graph edges.

        Returns list of {id, label, relation, direction, source_file}.
        direction: "outgoing" or "incoming".
        """
        data = self._ensure_loaded(repo_name)
        if data is None:
            return []

        links = data.graph_data.get("links", [])
        neighbors: list[dict[str, Any]] = []
        seen: set[str] = set()

        for link in links:
            src, tgt = link["source"], link["target"]
            rel = link.get("relation", "related_to")

            if src == node_id and tgt not in seen:
                tgt_node = data.nodes_by_id.get(tgt, {})
                neighbors.append({
                    "id": tgt,
                    "label": tgt_node.get("label", tgt),
                    "relation": rel,
                    "direction": "outgoing",
                    "source_file": tgt_node.get("source_file", ""),
                })
                seen.add(tgt)
            elif tgt == node_id and src not in seen:
                src_node = data.nodes_by_id.get(src, {})
                neighbors.append({
                    "id": src,
                    "label": src_node.get("label", src),
                    "relation": rel,
                    "direction": "incoming",
                    "source_file": src_node.get("source_file", ""),
                })
                seen.add(src)

            if len(neighbors) >= max_results:
                break

        return neighbors

    def get_gods(self, repo_name: str) -> list[dict]:
        """Return god nodes list from analysis."""
        analysis = self.get_analysis(repo_name)
        if analysis is None:
            return []
        return list(analysis.get("gods", []))

    def list_graph_repos(self) -> list[str]:
        """List repo names that have a graph.json."""
        repos = []
        for repo_path in settings.repos.paths:
            name = Path(repo_path).name
            gp = settings.graphify.output_dir / name / "graphify-out" / "graph.json"
            if gp.exists():
                repos.append(name)
        return repos

    def invalidate(self, repo_name: str | None = None) -> None:
        """Force reload on next access.

        If repo_name is None, invalidates all repos.
        Called by rag-sync after graph rebuild.
        """
        if repo_name is None:
            self._repos.clear()
            logger.info("GraphCache: invalidated all repos")
        elif repo_name in self._repos:
            del self._repos[repo_name]
            logger.info("GraphCache: invalidated %s", repo_name)


# Module-level singleton
graph_cache = GraphCache()
