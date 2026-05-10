"""Interactive terminal chat with RAG-augmented responses.

Usage:
    rag-chat                    # default model (qwen3-pt)
    rag-chat -m deepseek-r1-pt  # specific model
    rag-chat --debug            # show routing decisions
    rag-chat --no-rag           # disable RAG entirely
"""

import argparse
import sys

import httpx

from obsidian_rag.config import settings

API_URL = f"http://localhost:{settings.api.port}"


def main():
    parser = argparse.ArgumentParser(prog="rag-chat", description="Chat interativo com RAG local")
    parser.add_argument("-m", "--model", default="qwen3-pt", help="Modelo Ollama")
    parser.add_argument("--debug", action="store_true", help="Mostrar decisões do router e fontes")
    parser.add_argument("--no-rag", action="store_true", help="Desativar RAG (modo none)")
    parser.add_argument("--mode", choices=["auto", "rag_only", "graph_only", "both", "none"],
                        default="auto", help="Modo de contexto")
    args = parser.parse_args()

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
                    f"{API_URL}/chat",
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
                print("Inicia com: rag-serve", file=sys.stderr)
                sys.exit(1)
            except httpx.HTTPStatusError as e:
                print(f"\nErro HTTP: {e}", file=sys.stderr)
                continue

            data = resp.json()

            # Show debug info if requested
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
                    if debug.get('notes_after_filter'):
                        print(f"  Notes: {debug['notes_after_filter']}/{debug.get('notes_retrieved', 0)} (best={debug.get('best_note_score', 0):.2f})")
                    if debug.get('code_after_filter'):
                        print(f"  Code: {debug['code_after_filter']}/{debug.get('code_retrieved', 0)} (best={debug.get('best_code_score', 0):.2f})")
                    if debug.get('context_rejected_reason'):
                        print(f"  Rejected: {debug['context_rejected_reason']}")
                    print(f"  Time: {debug.get('total_ms', 0):.0f}ms")
                print(f"  Sources: {sources}")
                print("────────────")

            # Extract response
            content = data.get("message", {}).get("content", "")
            if not content:
                print("\n(sem resposta)", file=sys.stderr)
                continue

            # Strip <think>...</think> blocks for clean output
            import re
            clean = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()

            print(f"\n{clean}\n")
            history.append({"role": "assistant", "content": content})

    except KeyboardInterrupt:
        print("\n\nAdeus!")
        sys.exit(0)


if __name__ == "__main__":
    main()
