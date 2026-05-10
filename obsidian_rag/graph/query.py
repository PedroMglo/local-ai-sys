"""Interface Python para consultar grafos Graphify sem servidor MCP.

Lê graph.json via networkx (node-link format) e expõe funções de consulta
usadas pelo retrieval e pela API REST.

Dependência opcional: networkx>=3.0
Se não estiver instalado, as funções que precisam de networkx lançam ImportError
com mensagem clara.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from obsidian_rag.config import settings
from obsidian_rag.graph.builder import get_graph_json_path, get_report_path, _graphify_output_dir


def _require_networkx():
    try:
        import networkx as nx
        return nx
    except ImportError:
        raise ImportError(
            "networkx não está instalado. Instala com: pip install networkx"
        )


def load_graph(repo_name: str):
    """Carrega o graph.json de um repo como grafo NetworkX.

    Args:
        repo_name: nome do directório do repo (ex: "SPEECH-LAB")

    Raises:
        FileNotFoundError: se o graph.json não existir
        ImportError: se networkx não estiver instalado
    """
    nx = _require_networkx()
    graph_path = get_graph_json_path(repo_name)
    if graph_path is None:
        raise FileNotFoundError(
            f"Grafo não encontrado para '{repo_name}'. "
            f"Corre 'rag-sync -g' ou 'graphify extract' primeiro."
        )
    with open(graph_path, encoding="utf-8") as f:
        data = json.load(f)
    # Graphify uses "links" key; NetworkX >=3.0 defaults to "edges"
    return nx.node_link_graph(data, edges="links")


def get_report(repo_name: str) -> str:
    """Lê o relatório de análise de um repo como texto Markdown.

    Procura por ordem: GRAPH_REPORT.md → .graphify_analysis.json (Graphify v0.7+).
    Se só existir o JSON, gera um relatório Markdown a partir dos dados.

    Raises:
        FileNotFoundError: se nenhum dos dois existir
    """
    report_path = get_report_path(repo_name)
    if report_path is not None:
        return report_path.read_text(encoding="utf-8")

    # Fallback: gerar relatório a partir de .graphify_analysis.json
    analysis_path = _get_analysis_json_path(repo_name)
    if analysis_path is None:
        raise FileNotFoundError(
            f"Relatório não encontrado para '{repo_name}'. "
            f"Corre 'rag-sync -g' primeiro."
        )
    return _analysis_to_markdown(repo_name, analysis_path)


def _get_analysis_json_path(repo_name: str) -> Path | None:
    """Devolve o path para .graphify_analysis.json, ou None."""
    for repo_path in settings.repos.paths:
        p = Path(repo_path)
        if p.name == repo_name:
            ap = _graphify_output_dir(p) / ".graphify_analysis.json"
            return ap if ap.exists() else None
    return None


def _analysis_to_markdown(repo_name: str, path: Path) -> str:
    """Converte .graphify_analysis.json em relatório Markdown legível."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    lines = [f"# Graph Report — {repo_name}", ""]

    # God nodes
    gods = data.get("gods", [])
    if gods:
        lines.append("## God Nodes (mais conectados)")
        lines.append("")
        lines.append("| Node | Label | Degree |")
        lines.append("|------|-------|--------|")
        for g in gods:
            lines.append(f"| `{g.get('id', '')}` | {g.get('label', '')} | {g.get('degree', 0)} |")
        lines.append("")

    # Surprises
    surprises = data.get("surprises", [])
    if surprises:
        lines.append("## Conexões Surpreendentes")
        lines.append("")
        for s in surprises:
            src = s.get("source", "?")
            tgt = s.get("target", "?")
            rel = s.get("relation", "?")
            why = s.get("why", "")
            lines.append(f"- **{src}** → **{tgt}** ({rel})")
            if why:
                lines.append(f"  - {why}")
        lines.append("")

    # Communities
    communities = data.get("communities", {})
    if communities:
        lines.append(f"## Comunidades ({len(communities)} detectadas)")
        lines.append("")
        for cid, members in communities.items():
            lines.append(f"### Comunidade {cid} ({len(members)} membros)")
            # Show first 10 members
            shown = members[:10]
            lines.append(", ".join(f"`{m}`" for m in shown))
            if len(members) > 10:
                lines.append(f"  ... e mais {len(members) - 10}")
            lines.append("")

    # Tokens
    tokens = data.get("tokens", {})
    if tokens:
        lines.append("## Tokens")
        lines.append(f"- Input: {tokens.get('input', 0):,}")
        lines.append(f"- Output: {tokens.get('output', 0):,}")
        lines.append("")

    return "\n".join(lines)


def get_neighbors(repo_name: str, node_label: str, max_results: int = 10) -> list[dict[str, Any]]:
    """Devolve os nós vizinhos de um conceito no grafo.

    Args:
        repo_name: nome do repo
        node_label: label do nó (ex: "segment_window", "ChunkBuilder")
        max_results: máximo de vizinhos a devolver

    Returns:
        Lista de dicts com {id, label, relation, confidence, source_file}
    """
    nx = _require_networkx()
    G = load_graph(repo_name)

    # Encontrar nó por label (case-insensitive partial match)
    target_node = None
    for node, data in G.nodes(data=True):
        label = data.get("label", str(node))
        if node_label.lower() in label.lower() or label.lower() in node_label.lower():
            target_node = node
            break

    if target_node is None:
        return []

    results = []
    for neighbor in G.neighbors(target_node):
        edge_data = G.get_edge_data(target_node, neighbor) or {}
        node_data = G.nodes[neighbor]
        results.append({
            "id": neighbor,
            "label": node_data.get("label", str(neighbor)),
            "file_type": node_data.get("file_type", ""),
            "source_file": node_data.get("source_file", ""),
            "relation": edge_data.get("relation", "related_to"),
            "confidence": edge_data.get("confidence", "EXTRACTED"),
        })

    return results[:max_results]


def query_graph(repo_name: str, query: str) -> str:
    """Executa uma query ao grafo via CLI graphify.

    Args:
        repo_name: nome do repo
        query: query em linguagem natural

    Returns:
        Output da query como texto
    """
    graph_path = get_graph_json_path(repo_name)
    if graph_path is None:
        return f"Grafo não encontrado para '{repo_name}'."

    try:
        result = subprocess.run(
            ["graphify", "query", query, "--graph", str(graph_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    except FileNotFoundError:
        return "Comando 'graphify' não encontrado. Instala com: pip install graphifyy"
    except subprocess.TimeoutExpired:
        return "Timeout na query ao grafo."


def shortest_path(repo_name: str, source_label: str, target_label: str) -> list[str]:
    """Devolve o caminho mais curto entre dois nós no grafo.

    Útil para perceber como dois módulos/conceitos estão ligados.

    Returns:
        Lista de labels dos nós no caminho, ou [] se não existir caminho
    """
    nx = _require_networkx()
    G = load_graph(repo_name)

    # Encontrar nós por label
    def find_node(label: str) -> str | None:
        for node, data in G.nodes(data=True):
            node_label = data.get("label", str(node))
            if label.lower() in node_label.lower():
                return node
        return None

    source = find_node(source_label)
    target = find_node(target_label)

    if source is None or target is None:
        return []

    try:
        path = nx.shortest_path(G, source=source, target=target)
        return [G.nodes[n].get("label", str(n)) for n in path]
    except nx.NetworkXNoPath:
        return []
    except nx.NodeNotFound:
        return []


def list_repos() -> list[dict[str, Any]]:
    """Lista todos os repos configurados com status do grafo."""
    result = []
    for repo_path in settings.repos.paths:
        from pathlib import Path as _Path
        p = _Path(repo_path)
        name = p.name
        graph_path = get_graph_json_path(name)
        report_path = get_report_path(name)

        entry: dict[str, Any] = {
            "name": name,
            "path": str(p),
            "exists": p.exists(),
            "graph_built": graph_path is not None,
            "graph_path": str(graph_path) if graph_path else None,
            "report_path": str(report_path) if report_path else None,
        }

        if graph_path is not None:
            try:
                nx = _require_networkx()
                G = load_graph(name)
                entry["node_count"] = G.number_of_nodes()
                entry["edge_count"] = G.number_of_edges()
            except Exception:
                entry["node_count"] = None
                entry["edge_count"] = None

        result.append(entry)
    return result
