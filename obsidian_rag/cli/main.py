"""Unified ``rag`` CLI dispatcher.

Usage:
    rag init              Configuração interactiva inicial
    rag up                Verificar dependências e iniciar API
    rag doctor            Diagnóstico do sistema
    rag sync --all        Sincronizar embeddings + grafos
    rag serve             Iniciar API REST
    rag query "texto"     Pesquisa semântica
    rag chat              Chat interactivo com RAG
    rag backup            Backup do Qdrant
    rag graph build       Construir knowledge graphs
    rag graph status      Estado dos grafos
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="rag",
        description="Obsidian RAG — pipeline local de RAG para Obsidian e repositórios Git.",
    )
    sub = parser.add_subparsers(dest="command", help="Subcomando")

    # --- rag init ---
    p_init = sub.add_parser("init", help="Configuração interactiva inicial")
    p_init.add_argument("--vault", metavar="PATH", help="Caminho do Vault Obsidian")
    p_init.add_argument("--repos", metavar="PATH,...", help="Repos Git (separados por vírgula)")
    p_init.add_argument("--ollama-url", metavar="URL", help="URL do Ollama")
    p_init.add_argument("--yes", "-y", action="store_true", help="Aceitar defaults sem perguntar")

    # --- rag up ---
    sub.add_parser("up", help="Verificar dependências e iniciar API")

    # --- rag doctor ---
    sub.add_parser("doctor", help="Diagnóstico do sistema")

    # --- rag sync ---
    p_sync = sub.add_parser("sync", help="Sincronizar embeddings e/ou grafos")
    sync_group = p_sync.add_mutually_exclusive_group(required=True)
    sync_group.add_argument("-l", "--local", action="store_true", help="Embeddings de notas + repos (deltas)")
    sync_group.add_argument("-g", "--graph", action="store_true", help="Grafos Graphify")
    sync_group.add_argument("--all", action="store_true", dest="run_all", help="Tudo: embeddings + grafos")
    p_sync.add_argument("--force", action="store_true", help="Rebuild completo do grafo")
    p_sync.add_argument("--vault", metavar="NAME", help="Sincronizar apenas este vault (nome do directório)")

    # --- rag serve ---
    sub.add_parser("serve", help="Iniciar API REST (porta 8484)")

    # --- rag query ---
    p_query = sub.add_parser("query", help="Pesquisa semântica")
    p_query.add_argument("query", nargs="+", help="Texto da pergunta")
    p_query.add_argument("-n", "--top-k", type=int, default=5, metavar="N")
    p_query.add_argument("--min-score", type=float, default=0.0, metavar="F")
    p_query.add_argument("--repo", type=str, default=None, metavar="REPO", help="Filtrar por repo_name")
    p_query.add_argument("--vault", type=str, default=None, metavar="NAME", help="Filtrar por vault")
    p_query.add_argument("--json", action="store_true", help="Saída em JSON")

    # --- rag chat ---
    p_chat = sub.add_parser("chat", help="Chat interactivo com RAG")
    p_chat.add_argument("-m", "--model", default="qwen3-pt", help="Modelo Ollama")
    p_chat.add_argument("--debug", action="store_true", help="Mostrar decisões do router")
    p_chat.add_argument("--no-rag", action="store_true", help="Desativar RAG")
    p_chat.add_argument(
        "--mode",
        choices=["auto", "rag_only", "graph_only", "both", "none"],
        default="auto",
        help="Modo de contexto",
    )

    # --- rag backup ---
    p_backup = sub.add_parser("backup", help="Backup do Qdrant")
    p_backup.add_argument("dest", nargs="?", default=None, help="Directório de destino")

    # --- rag graph ---
    p_graph = sub.add_parser("graph", help="Knowledge graph (Graphify)")
    graph_sub = p_graph.add_subparsers(dest="graph_command", help="Subcomando do graph")
    p_graph_build = graph_sub.add_parser("build", help="Construir grafos")
    p_graph_build.add_argument("--force", action="store_true", help="Rebuild completo (ignora cache incremental)")
    p_graph_build.add_argument("--changed-only", action="store_true", default=True,
                               help="Só processar ficheiros alterados (default — graphify detecta via manifest)")
    p_graph_build.add_argument("--repo", metavar="NOME", help="Repo específico")
    graph_sub.add_parser("status", help="Estado dos grafos")

    # --- rag schedule ---
    p_schedule = sub.add_parser("schedule", help="Agendamento automático de sync (systemd/launchd/schtasks)")
    schedule_sub = p_schedule.add_subparsers(dest="schedule_command", help="Subcomando do schedule")
    schedule_sub.add_parser("install", help="Instalar sync diário automático")
    schedule_sub.add_parser("remove", help="Remover agendamento")
    schedule_sub.add_parser("status", help="Estado do agendamento")

    # --- rag migrate ---
    from obsidian_rag.cli.migrate_cmd import add_migrate_parser
    add_migrate_parser(sub)

    # --- Parse ---
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    # Dispatch — imports lazy para não carregar settings desnecessariamente
    if args.command == "init":
        from obsidian_rag.cli.init_cmd import run_init
        run_init(args)

    elif args.command == "doctor":
        from obsidian_rag.cli.doctor_cmd import run_doctor
        run_doctor()

    elif args.command == "up":
        from obsidian_rag.cli.up_cmd import run_up
        run_up()

    elif args.command == "sync":
        from obsidian_rag.pipeline.sync import sync_graphify, sync_local
        vault = getattr(args, "vault", None)
        if args.local:
            sync_local(vault_filter=vault)
        elif args.graph:
            sync_graphify(force=args.force)
        elif args.run_all:
            sync_local(vault_filter=vault)
            print()
            sync_graphify(force=args.force)

    elif args.command == "serve":
        from obsidian_rag.api.app import serve
        serve()

    elif args.command == "query":
        from obsidian_rag.cli._query import run_query
        run_query(args)

    elif args.command == "chat":
        from obsidian_rag.cli._chat import run_chat
        run_chat(args)

    elif args.command == "backup":
        from obsidian_rag.cli._backup import run_backup
        run_backup(args)

    elif args.command == "graph":
        from obsidian_rag.cli.graph_cmd import run_graph
        run_graph(args)

    elif args.command == "schedule":
        from obsidian_rag.cli.schedule_cmd import run_schedule
        run_schedule(args)

    elif args.command == "migrate":
        from obsidian_rag.cli.migrate_cmd import run_migrate
        run_migrate(args)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
