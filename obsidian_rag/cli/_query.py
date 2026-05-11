"""Thin wrapper — delegates query logic to obsidian_rag.api.cli."""

from __future__ import annotations

import json
import sys
from argparse import Namespace

import httpx

from obsidian_rag.config import settings


def run_query(args: Namespace) -> None:
    query = " ".join(args.query)
    api_url = f"http://localhost:{settings.api.port}"

    payload: dict = {"query": query, "top_k": args.top_k, "min_score": args.min_score}
    endpoint = "/query"

    repo = getattr(args, "repo", None)
    vault = getattr(args, "vault", None)
    if repo:
        endpoint = "/query/code"
        payload["repo"] = repo
    if vault:
        payload["vault"] = vault

    try:
        resp = httpx.post(
            f"{api_url}{endpoint}",
            json=payload,
            timeout=30.0,
        )
        resp.raise_for_status()
    except httpx.ConnectError:
        print(f"Erro: API não está a correr (localhost:{settings.api.port})", file=sys.stderr)
        print("Inicia com: rag up", file=sys.stderr)
        sys.exit(1)

    data = resp.json()

    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if not data["results"]:
        print("(sem resultados relevantes)", file=sys.stderr)
        sys.exit(0)

    for r in data["results"]:
        label = (
            f"[{r['note_title']} / {r['section_header']}]"
            if r["section_header"]
            else f"[{r['note_title']}]"
        )
        print(f"{label}  score={r['score']:.2f}")
        print(r["text"])
        print()
