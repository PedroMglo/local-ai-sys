"""Thin wrapper — delegates chat logic from old chat_cli module."""

from __future__ import annotations

import re
import sys
from argparse import Namespace

import httpx

from obsidian_rag.config import settings


def run_chat(args: Namespace) -> None:
    api_url = f"http://localhost:{settings.api.port}"
    context_mode = "none" if args.no_rag else args.mode

    print(f"RAG Chat — modelo: {args.model} | modo: {context_mode}")
    print("Escreve a tua pergunta (Ctrl+C para sair)\n")

    history: list[dict] = []

    try:
        while True:
            try:
                query = input("Tu: ").strip()
            except EOFError:
                break

            if not query:
                continue
            if query.lower() in ("exit", "quit", "sair"):
                break

            history.append({"role": "user", "content": query})

            try:
                resp = httpx.post(
                    f"{api_url}/chat",
                    json={
                        "model": args.model,
                        "messages": history,
                        "stream": False,
                        "context_mode": context_mode,
                    },
                    timeout=120.0,
                )
                resp.raise_for_status()
            except httpx.ConnectError:
                print(f"\nErro: API não está a correr (localhost:{settings.api.port})", file=sys.stderr)
                print("Inicia com: rag up", file=sys.stderr)
                sys.exit(1)
            except httpx.HTTPStatusError as e:
                print(f"\nErro HTTP: {e}", file=sys.stderr)
                continue

            data = resp.json()

            if args.debug:
                route_mode = data.get("debug", {}).get("route_mode") or resp.headers.get("X-Route-Mode", "?")
                sources = data.get("sources_used", resp.headers.get("X-Sources-Used", "none"))
                debug = data.get("debug", {})

                print("\n── Debug ──")
                print(f"  Route: {route_mode}")
                if debug:
                    print(f"  Reason: {debug.get('route_reason', '?')}")
                    print(f"  Method: {debug.get('route_method', '?')}")
                    print(f"  Confidence: {debug.get('route_confidence', 0):.1f}")
                    if debug.get("notes_after_filter"):
                        print(f"  Notes: {debug['notes_after_filter']}/{debug.get('notes_retrieved', 0)} (best={debug.get('best_note_score', 0):.2f})")
                    if debug.get("code_after_filter"):
                        print(f"  Code: {debug['code_after_filter']}/{debug.get('code_retrieved', 0)} (best={debug.get('best_code_score', 0):.2f})")
                    if debug.get("context_rejected_reason"):
                        print(f"  Rejected: {debug['context_rejected_reason']}")
                    print(f"  Time: {debug.get('total_ms', 0):.0f}ms")
                print(f"  Sources: {sources}")
                print("────────────")

            content = data.get("message", {}).get("content", "")
            if not content:
                print("\n(sem resposta)", file=sys.stderr)
                continue

            clean = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            print(f"\n{clean}\n")
            history.append({"role": "assistant", "content": content})

    except KeyboardInterrupt:
        print("\n\nAdeus!")
        sys.exit(0)
