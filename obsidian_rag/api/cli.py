"""CLI para queries semânticas ao Obsidian RAG.

Uso:
    rag-query "texto da pergunta"
    rag-query -n 5 "texto"
"""

import argparse
import sys

import httpx

from obsidian_rag.config import settings

API_URL = f"http://localhost:{settings.api.port}"


def main():
    parser = argparse.ArgumentParser(prog="rag-query")
    parser.add_argument("query", nargs="+", help="Texto da pergunta")
    parser.add_argument("-n", "--top-k", type=int, default=5, metavar="N")
    parser.add_argument("--min-score", type=float, default=0.0, metavar="F")
    parser.add_argument("--json", action="store_true", help="Saída em JSON")
    args = parser.parse_args()

    query = " ".join(args.query)

    try:
        resp = httpx.post(
            f"{API_URL}/query",
            json={"query": query, "top_k": args.top_k, "min_score": args.min_score},
            timeout=30.0,
        )
        resp.raise_for_status()
    except httpx.ConnectError:
        print(f"Erro: API não está a correr (localhost:{settings.api.port})", file=sys.stderr)
        sys.exit(1)

    data = resp.json()

    if args.json:
        import json
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if not data["results"]:
        print("(sem resultados relevantes)", file=sys.stderr)
        sys.exit(0)

    for r in data["results"]:
        label = f"[{r['note_title']} / {r['section_header']}]" if r["section_header"] else f"[{r['note_title']}]"
        print(f"{label}  score={r['score']:.2f}")
        print(r["text"])
        print()


if __name__ == "__main__":
    main()
