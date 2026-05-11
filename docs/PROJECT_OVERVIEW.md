# PROJECT OVERVIEW — obsidian-rag

> **Versão:** 0.5.0
> **Última atualização:** 2026-05-11
> **Linguagem:** Python ≥ 3.11
> **Licença:** A confirmar

---

## Índice

- [PROJECT OVERVIEW — obsidian-rag](#project-overview--obsidian-rag)
  - [Índice](#índice)
  - [Objetivo principal](#objetivo-principal)
  - [Problema que o projeto resolve](#problema-que-o-projeto-resolve)
  - [Casos de uso principais](#casos-de-uso-principais)
  - [Arquitetura geral](#arquitetura-geral)
  - [Estrutura de pastas e ficheiros](#estrutura-de-pastas-e-ficheiros)
  - [Fluxo de funcionamento](#fluxo-de-funcionamento)
    - [1. Sincronização (`rag sync`)](#1-sincronização-rag-sync)
    - [2. Query (`rag query`, `/query`, `/query/code`)](#2-query-rag-query-query-querycode)
    - [3. Chat RAG-augmented (`rag chat`, `/chat`)](#3-chat-rag-augmented-rag-chat-chat)
  - [Componentes principais](#componentes-principais)
    - [Chunking (`obsidian_rag/chunking/`)](#chunking-obsidian_ragchunking)
    - [Embeddings (`obsidian_rag/embeddings/`)](#embeddings-obsidian_ragembeddings)
    - [Store (`obsidian_rag/store/`)](#store-obsidian_ragstore)
    - [Retrieval (`obsidian_rag/retrieval/`)](#retrieval-obsidian_ragretrieval)
    - [Graph (`obsidian_rag/graph/`)](#graph-obsidian_raggraph)
    - [API (`obsidian_rag/api/`)](#api-obsidian_ragapi)
    - [CLI unificado (`obsidian_rag/cli/`) — v0.4.0](#cli-unificado-obsidian_ragcli--v040)
    - [Pipeline (`obsidian_rag/pipeline/`)](#pipeline-obsidian_ragpipeline)
    - [Auto-tuning (`obsidian_rag/tuning.py`)](#auto-tuning-obsidian_ragtuningpy)
    - [Prompts (`obsidian_rag/prompts/`)](#prompts-obsidian_ragprompts)
  - [Modelos de AI/LLMs utilizados](#modelos-de-aillms-utilizados)
  - [Integração com Ollama](#integração-com-ollama)
  - [APIs e endpoints](#apis-e-endpoints)
  - [CLI — Comando unificado `rag`](#cli--comando-unificado-rag)
    - [Shell helpers (zsh)](#shell-helpers-zsh)
  - [Dependências principais](#dependências-principais)
    - [Obrigatórias](#obrigatórias)
    - [Desenvolvimento](#desenvolvimento)
    - [Stdlib utilizada](#stdlib-utilizada)
  - [Tecnologias usadas](#tecnologias-usadas)
  - [Como executar o projeto localmente](#como-executar-o-projeto-localmente)
    - [Pré-requisitos](#pré-requisitos)
    - [Instalação](#instalação)
    - [Configuração inicial](#configuração-inicial)
    - [Uso](#uso)
    - [Makefile (atalhos)](#makefile-atalhos)
    - [Environment overrides](#environment-overrides)
    - [Execução com Docker](#execução-com-docker)
  - [Como configurar o ambiente](#como-configurar-o-ambiente)
    - [Ficheiro principal: `rag.toml`](#ficheiro-principal-ragtoml)
    - [Scheduler (cross-platform)](#scheduler-cross-platform)
  - [Como testar funcionalidades](#como-testar-funcionalidades)
    - [Testes manuais](#testes-manuais)
    - [Testes automatizados](#testes-automatizados)
  - [Limitações conhecidas](#limitações-conhecidas)
  - [Estado atual do projeto](#estado-atual-do-projeto)
  - [Regra de manutenção da documentação](#regra-de-manutenção-da-documentação)

---

## Objetivo principal

O **obsidian-rag** é um pipeline de RAG (Retrieval-Augmented Generation) 100% local e privado. Indexa um vault Obsidian e repositórios Git numa base de dados vetorial, expõe uma API REST, e serve como proxy inteligente para o Ollama — injetando contexto local relevante nas respostas do LLM apenas quando necessário.

## Problema que o projeto resolve

- **Fragmentação do conhecimento pessoal:** Notas Obsidian e código em repositórios Git ficam isolados e difíceis de pesquisar semanticamente.
- **Falta de contexto local nos LLMs:** Modelos de linguagem genéricos não conhecem o conteúdo das notas nem a arquitetura dos projetos pessoais.
- **Privacidade:** Soluções cloud enviam dados para servidores externos. Este projeto mantém tudo local — sem APIs externas, sem dados a sair da máquina.

## Casos de uso principais

| Caso de uso                        | Descrição                                                                       |
| ---------------------------------- | ------------------------------------------------------------------------------- |
| **Pesquisa semântica no vault**    | Consultar notas Obsidian por semelhança semântica (não apenas texto exato)      |
| **Pesquisa de código**             | Encontrar funções, classes e módulos em repositórios Git indexados              |
| **Chat aumentado com contexto**    | Conversar com um LLM local que injeta automaticamente notas e código relevantes |
| **Exploração de grafos de código** | Consultar relações estruturais entre módulos (dependências, chamadas, imports)  |
| **Onboarding em projetos**         | Compreender rapidamente a arquitetura de um repositório via grafos e relatórios |
| **Terminal AI integrado**          | Usar o comando `ol` no terminal para queries rápidas via RAG proxy              |

## Arquitetura geral

```
┌─────────────────┐   sync_vault()  ┌───────────────┐
│  Obsidian Vault │────────────────►│   source/     │  (python/rsync)
└─────────────────┘    │            └──────┬────────┘
                       │                   │
                       │ (direct backend)  │
                       └───────────────────┤
                                           │
                                   chunk_all_notes()
                                   (header-split + overlap)
                                           │
┌─────────────────┐                       │
│  Git Repos      │                       │
│  (SPEECH-LAB,   │                       │
│   ApacheSpark,  │                       │
│   obsidian-rag, │                       │
│   ...)          │                       │
└────────┬────────┘                       │
         │                                │
         │  ┌── Bounded Ingest Pipeline (Phase 1+2) ───────────────┐
         │  │                                                     │
         │  │  Scanner Thread    Parser Pool     Embed Batcher    │
         │  │  (iter_repo_files) (ProcessPool    (micro-batches:  │
         │  │       │            Executor ou      24 count,       │
         │  │       │            DaskParserPool,  48k chars,      │
         │  │       │            max_tasks=100)   1s timeout)     │
         │  │       ▼                ▼                ▼           │
         │  │  files_queue(256) → chunks_queue(128) → write_q(4) │
         │  │       ║                ║                ║           │
         │  │  backpressure     backpressure     backpressure    │
         │  │                                                     │
         │  │  ┌─────────────────────────────────────────┐        │
         │  │  │ ResourceGovernor (Phase 2)               │        │
         │  │  │  daemon thread: psutil sample every 1s  │        │
         │  │  │  check() → CONTINUE|REDUCE|PAUSE|ABORT  │        │
         │  │  │  wait_until_safe(timeout) — blocks       │        │
         │  │  │  JSONL metrics (optional post-mortem)    │        │
         │  │  └─────────────────────────────────────────┘        │
         │  │                                                     │
         │  │  ┌─────────────────────────────────────────┐        │
         │  │  │ SQLite Manifest (WAL)                   │        │
         │  │  │  files | chunks | ingest_runs           │        │
         │  │  │  → crash recovery / incremental resume  │        │
         │  │  └─────────────────────────────────────────┘        │
         │  └─────────────────────────────────────────────────────┘
         │                                │
         │                         embed_texts()
         │                         Ollama bge-m3 (1024d, cosine)
         │                                │
         │                        ┌───────▼────────┐
         │                        │ VectorStore    │
         │                        │ Protocol       │
         │                        ├────────────────┤
         │                        │ ChromaDB  (def)│ ◄── persistente
         │                        │ Qdrant (opt)   │ ◄── embedded/server
         │                        ├────────────────┤
         │                        │ obsidian_vault │ ◄── notas
         │                        │ code_repos     │ ◄── código
         │                        └───────┬────────┘
         │                                │
         │                        ┌───────▼────────┐
         │                        │  FastAPI :8484 │
         │                        │ (127.0.0.1)   │
         │                        ├────────────────┤
         │                        │ /query         │ pesquisa notas
         │                        │ /query/code    │ pesquisa código
         │                        │ /repos         │ lista repos
         │                        │ /graph/{repo}  │ relatório do grafo
         │                        │ /graph/.../query│ NL graph query
         │                        │ /chat          │ RAG-augmented proxy
         │                        │ Auth: Bearer   │ API key (opcional)
         │                        └────────────────┘
         │
         │   graphify extract
         └──────────────────────► graph.json (NetworkX node-link)
              (AST local + Ollama)  ├── GRAPH_REPORT.md
                                    ├── community_summaries.json
                                    └── .graphify_analysis.json
```

## Estrutura de pastas e ficheiros

```
obsidian-rag/
├── pyproject.toml              # Package config, dependências, entry point único `rag`
├── rag.toml                    # Configuração central (todas as opções, incl. [performance])
├── requirements.txt            # Dependências mínimas
├── README.md                   # Documentação (reescrito em v0.4.0)
├── Makefile                    # Atalhos: make install, init, up, serve, sync, test, etc.
├── install.sh                  # Instalador Linux/macOS: cria venv, instala deps, valida comandos
├── install.ps1                 # Instalador Windows (PowerShell): cria venv, instala deps, valida
├── Dockerfile                  # Multi-stage build (python:3.11-slim), apt-get upgrade + remoção de build tools no runtime, CMD ["rag", "serve"]
├── docker-compose.yml          # Serviço obsidian-rag + rede Ollama + Qdrant (profile)
├── docs/                       # Documentação técnica detalhada
│   ├── PROJECT_OVERVIEW.md     # Este ficheiro
│   └── IMPROVEMENTS_AND_RISKS.md
├── tests/                      # Testes automatizados (pytest) — 329 testes (18 skipped)
│   ├── __init__.py
│   ├── conftest.py             # Fixtures partilhadas
│   ├── test_api.py             # Testes de auth middleware e /health
│   ├── test_budget.py          # Testes de alocação de token budget
│   ├── test_chunking_code.py   # Testes de chunking Python (AST) + dispatch tree-sitter
│   ├── test_chunking_treesitter.py # Testes de chunking multi-linguagem (tree-sitter, 22 testes)
│   ├── test_chunking_markdown.py # Testes de chunking Markdown
│   ├── test_cli_dispatch.py    # Testes do CLI dispatcher (rag <subcommand>)
│   ├── test_init.py            # Testes do wizard rag init (path validation, etc.)
│   ├── test_router.py          # Testes de heurística do router
│   ├── test_security.py        # Testes de segurança (bind validation, _EXCLUDED_DIRS, etc.)
│   ├── test_medium_features.py # Backup, logging JSON, config, tokenizer
│   ├── test_performance.py     # PerformanceConfig, auto_tune, throttle (patches governor.psutil), workers capping
│   ├── test_adaptive_topk.py   # Complexidade de queries, adaptive top_k scaling
│   ├── test_manifest.py        # IngestManifest: SQLite CRUD, crash recovery (25 testes)
│   ├── test_ingest_pipeline.py # IngestPipeline: 4-stage bounded pipeline (10 testes)
│   ├── test_dask_engine.py     # DaskParserPool: factory local/dask, import error, IngestPipeline integration
│   ├── test_governor.py        # ResourceGovernor: thresholds, lifecycle, wait, metrics, tuning compat (21 testes)
│   ├── test_integration.py     # Integration tests: endpoints + ChromaDB in-memory
│   ├── test_low_priority.py    # Thread safety, Unicode, __all__, reranker cache, stop words bilíngues
│   ├── test_vector_store.py    # VectorStore protocol: Chroma/Qdrant parametrizado, factory, collection isolation
│   └── test_vault_sync.py
├── .github/
│   ├── agents/                 # Agentes VS Code Copilot
│   │   └── doc-reviewer.agent.md
│   ├── instructions/           # Instruções de manutenção
│   │   └── doc-maintenance.instructions.md
│   └── workflows/              # CI/CD GitHub Actions
│       ├── ci.yml              # Lint + test matrix + CLI smoke + security audit
│       ├── docker.yml          # Docker build + compose config
│       ├── release.yml         # Build wheel/sdist + GitHub Release
│       ├── release-gate.yml    # Docker build + Trivy image scan + OWASP ZAP baseline
│       └── security-scheduled.yml # Scans semanais: source (Trivy fs, pip-audit) + container (Trivy image)
├── scripts/
│   ├── monitor_rag.sh          # Monitor de recursos em tempo real (RAM, CPU, disco, GPU, processos RAG/Ollama)
│   └── rag-cgroup.sh           # systemd-run wrapper: executa rag-sync --all com MemoryMax e CPUQuota
├── source/                     # Notas Obsidian sincronizadas (rsync do vault)
├── data/
│   ├── chroma/                 # ChromaDB persistente (chroma.sqlite3)
│   └── graphify/               # Grafos por repositório
│       ├── ApacheSpark-CD/graphify-out/
│       ├── obsidian-rag/graphify-out/
│       └── SPEECH-LAB/graphify-out/
├── obsidian_rag/               # Código principal
│   ├── __init__.py
│   ├── config.py               # _LazySettings proxy, config_exists(), env overrides, dataclasses (incl. PerformanceConfig, StoreConfig)
│   ├── tuning.py               # Auto-tuning: detect_resources(), auto_tune(), should_throttle() (thin wrapper do governor)
│   ├── cli/                    # CLI unificado (v0.4.0)
│   │   ├── __init__.py
│   │   ├── main.py             # Dispatcher `rag` — argparse com subcommands
│   │   ├── init_cmd.py         # `rag init` — wizard interactivo, gera rag.toml
│   │   ├── up_cmd.py           # `rag up` — pre-flight checks + start API
│   │   ├── doctor_cmd.py       # `rag doctor` — diagnóstico ✓/✗ do sistema
│   │   ├── graph_cmd.py        # `rag graph build|status`
│   │   ├── _query.py           # `rag query` — wrapper do cli.py original
│   │   ├── _chat.py            # `rag chat` — wrapper do chat_cli.py original
│   │   ├── _backup.py          # `rag backup` — wrapper do backup.py original
│   │   ├── schedule_cmd.py     # `rag schedule install|remove|status` — cross-platform scheduler
│   │   └── migrate_cmd.py      # `rag migrate --from X --to Y` — migração entre vector stores
│   ├── api/                    # FastAPI endpoints
│   │   ├── app.py              # Aplicação FastAPI + lifespan + serve() com bind validation
│   │   ├── schemas.py          # Modelos Pydantic (request/response)
│   │   ├── cli.py              # Lógica de query one-shot (usada por `rag query`)
│   │   └── chat_cli.py         # REPL interativo (usado por `rag chat`)
│   ├── chunking/               # Divisão de texto em chunks
│   │   ├── markdown.py         # Chunking por headers H1/H2/H3 + _EXCLUDED_DIRS
│   │   ├── code.py             # Chunking via ast.parse() (Python) + dispatch tree-sitter
│   │   └── treesitter.py       # Chunking multi-linguagem via tree-sitter (10 linguagens)
│   ├── embeddings/
│   │   └── ollama.py           # Embeddings via Ollama bge-m3
│   ├── graph/                  # Knowledge graph (Graphify + NetworkX)
│   │   ├── builder.py          # Wrapper para graphify extract
│   │   ├── query.py            # Queries ao grafo (NetworkX)
│   │   ├── cache.py            # Cache in-memory com TTL + file-stat
│   │   ├── enrich.py           # Community summaries, Mermaid, tags
│   │   └── obsidian_export.py  # Export para vault Obsidian
│   ├── pipeline/
│   │   ├── sync.py             # Pipeline de sincronização — notas sequenciais, repos via bounded pipeline (VectorStore protocol)
│   │   ├── ingest.py           # IngestPipeline: 4 estágios bounded (scanner→parser→embedder→writer) via VectorStore
│   │   ├── dask_engine.py      # DaskParserPool + create_parser_pool() factory (local/dask engine)
│   │   ├── manifest.py         # SQLite manifest para tracking incremental (files, chunks, runs)
│   │   ├── vault_sync.py       # Sync backends: direct, python, rsync, auto
│   │   ├── backup.py           # Backup vector store com rotação (backup_store())
│   │   └── __main__.py
│   ├── prompts/
│   │   └── templates.py        # Templates de prompts (PT-PT)
│   ├── retrieval/              # Motor de retrieval multi-estratégia
│   │   ├── rag.py              # build_rag_context() — entry point
│   │   ├── router.py           # LLM router + heurística keyword
│   │   ├── intent.py           # Mapeamento ContextMode → QueryIntent
│   │   ├── budget.py           # Alocação de token budget
│   │   ├── reranker.py         # Cross-encoder opcional via Ollama
│   │   ├── graph_context.py    # Contexto estrutural do grafo
│   │   └── observe.py          # QueryTrace — observabilidade
│   └── store/
│       ├── base.py             # VectorStore Protocol + QueryResult + create_store() factory
│       ├── chroma_store.py     # ChromaVectorStore — ChromaDB behind VectorStore protocol
│       └── qdrant_store.py     # QdrantVectorStore — Qdrant (embedded/server) behind VectorStore protocol
└── source/
    └── AI-context/             # Documentação contextual do sistema
        ├── local-ai/           # Setup Ollama, modelos, benchmarks
        ├── shell-linux/        # Configuração zsh, aliases, ferramentas
        ├── system-audit/       # Auditoria do sistema
        └── system-profile/     # Hardware, OS, GPU, ambiente dev
```

## Fluxo de funcionamento

### 1. Sincronização (`rag sync`)

```
rag sync -l:
  1. sync_vault() — backend configurável:
     ├── direct: lê vault_dir directamente (sem cópia, cross-platform, default)
     ├── python: cópia incremental vault_dir → source/ (shutil, cross-platform)
     ├── rsync: rsync vault_dir → source/ (Linux/macOS, mais rápido)
     └── auto: rsync se disponível, senão python
  2. Resource check via ResourceGovernor — aborta se disco cheio ou RAM crítica, pausa se sistema sob pressão
  3. chunk_all_notes() — divide por headers H1/H2/H3, aplica overlap
     (exclui .obsidian, .trash, .git, .DS_Store, Thumbs.db, node_modules, .venv, etc.)
  4. Gera SHA256 IDs para sync incremental (só chunks novos/alterados)
  5. embed_texts() — gera embeddings via Ollama bge-m3 (batches configuráveis via embedding_batch_size)
  6. _sync_chunks_to_store() — sync incremental via VectorStore protocol (upsert novos, delete stale) na coleção "obsidian_vault"
  7. _wait_for_resources() — verifica recursos via ResourceGovernor na transição notas→repos
  8. Repos processados via **Bounded Ingest Pipeline** (Phase 1+2):
     a. Scanner thread — iter_repo_files()/iter_note_files() descobre ficheiros alterados
        (verifica mtime/size/SHA256 contra SQLite manifest para skip incremental)
     b. Parser pool — via create_parser_pool() factory:
        ProcessPoolExecutor (engine="local", default) ou DaskParserPool (engine="dask", opcional)
        parse paralelo de ficheiros em chunks (isolamento de memória por processo)
     c. Embedding batcher — acumula micro-batches (≤24 chunks, ≤48k chars, ou ≥1s)
        chama embed_texts() e envia para write queue
        usa governor.check() / governor.wait_until_safe() para throttle
     d. Writer thread — upsert na coleção "code_repos" com embeddings pré-calculados
        atualiza manifest SQLite para crash recovery
     e. Backpressure: files_queue(256) → chunks_queue(128) → write_queue(4)
        Queues bounded previnem crescimento ilimitado de memória
     f. ResourceGovernor (Phase 2) — daemon thread monitora psutil cada 1s;
        check() retorna GovernorAction (CONTINUE|REDUCE|PAUSE|ABORT) sem blocking;
        governor partilhado entre sync_repos() e IngestPipeline
     g. Stale cleanup: remove chunks de ficheiros apagados via manifest
     h. gc.collect() após conclusão do pipeline

rag sync -g:
  1. graphify extract — extrai grafo estrutural de cada repo
     (com timeout configurável: graph_timeout=600s)
     (throttle check antes de cada repo em build_graphs())
  2. Gera graph.json (node-link), GRAPH_REPORT.md, community_summaries.json
  3. export_all() — exporta grafos como notas Markdown para ~/Obsidian/knowledge-graphs/
  4. Invalida cache do grafo em memória

rag sync --all:
  Executa -l seguido de -g
  _wait_for_resources() — verifica recursos via ResourceGovernor na transição local→graphify
  os.nice(10) — processo corre com prioridade inferior (desktop responsivo)
  Proteção de recursos em 4 camadas:
    1. Auto-tune no arranque — deteta hardware e ajusta batch sizes/workers (conservativo)
    2. Transições de fase — ResourceGovernor verifica recursos entre notas→repos e local→graphify
    3. ResourceGovernor contínuo — daemon thread no pipeline (check() + wait_until_safe())
    4. cgroup externo (opcional) — scripts/rag-cgroup.sh aplica MemoryMax e CPUQuota via systemd
  Repos processados via bounded ingest pipeline com backpressure (Phase 1+2)
  Opcional: `scripts/rag-cgroup.sh` executa rag-sync --all dentro de systemd scope com limites de RAM/CPU
```

### 2. Query (`rag query`, `/query`, `/query/code`)

```
1. Recebe query textual
2. get_query_embedding() — embedding da query (com cache LRU de 128 entradas)
3. VectorStore.query() — pesquisa vetorial (cosine similarity) via protocolo abstracto
4. Filtra por score mínimo
5. Devolve ChunkResults ordenados por relevância
```

### 3. Chat RAG-augmented (`rag chat`, `/chat`)

```
1. Recebe mensagem + histórico de conversa
2. should_use_rag() — verifica se o modelo tem RAG habilitado ([models])
3. detect_intent_full() — router decide o modo:
   ├── NO_CONTEXT → resposta direta sem contexto
   ├── RAG_ONLY → pesquisa vectorial em notas + código
   ├── GRAPH_ONLY → contexto estrutural do grafo
   ├── RAG_AND_GRAPH → ambos
   └── CLARIFY → pede esclarecimento ao utilizador
4. Router: 2 camadas — LLM (gemma3:4b, 15s timeout) → keyword heuristic fallback
5. Adaptive top_k:
   - `_estimate_complexity(query)` classifica a query como "simple" | "normal" | "complex"
   - simple → top_k // 3 (mín. 3); normal → top_k inalterado; complex → top_k × 2 (máx. 20)
   - Registado em `QueryTrace.query_complexity` e `QueryTrace.effective_top_k`
6. Pesquisa multi-estratégia:
   a. Primária: vector search (notas + código)
   b. Secundária: keyword search (sem stop words PT+EN)
   c. Terciária: title-based search
7. Deduplicação por (source_path, section_header, chunk_index)
8. Dynamic threshold: max(0.45, best_score × 0.75)
9. Reranker (cross-encoder via gemma3:4b, enabled por defeito, LRU cache)
10. Relevance gate: contexto descartado se best score < 0.50 ou < 1 chunk
11. Token budget allocation: 4000 tokens, split 40/40/20 (notas/código/grafo)
12. Injeta contexto como system message → stream para Ollama → resposta ao utilizador
```

## Componentes principais

### Chunking (`obsidian_rag/chunking/`)

| Módulo          | Função                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `markdown.py`   | Divide `.md` por headers H1/H2/H3. Sliding-window fallback com overlap. Strips YAML frontmatter. Filtra chunks de navegação (>60-70% wikilinks). Adiciona contextual prefix (`Note: {título} \| Section: {header}`). Exclui dirs: `.git`, `.venv`, `node_modules`, `__pycache__`, `.cache`, `dist`, `build`, `.obsidian`. `iter_note_files()` — generator para descoberta streaming de ficheiros `.md` (usado pelo scanner do bounded pipeline)                                                                                                                                                                                                                                                                          |
| `code.py`       | Chunks Python via `ast.parse()` (zero deps externas). Um chunk por função/método, um por classe (signature summary), um por módulo (imports + constants). Ficheiros `.md/.yaml/.toml/.sh` em repos são delegados ao markdown chunker com `source_type="repo_doc"`. Dispatch para tree-sitter: extensões JS/TS/Java/Go/Rust/C/C++/C#/Ruby → `chunk_treesitter()`. `iter_repo_files()` — generator para descoberta streaming de ficheiros em repos (agora inclui extensões tree-sitter)                                                                                                                                                                                                                                    |
| `treesitter.py` | Chunking semântico multi-linguagem via tree-sitter. 10 linguagens: JavaScript (.js/.jsx/.mjs), TypeScript (.ts/.tsx), Java (.java), Go (.go), Rust (.rs), C (.c/.h), C++ (.cpp/.cxx/.cc/.hpp/.hxx), C# (.cs), Ruby (.rb). Extrai definições (funções, classes, métodos, structs, interfaces, enums, traits, impls, namespaces) como chunks individuais. Métodos de classes/structs/impls extraídos separadamente. Código module-level (imports, constants) como chunk separado. Lazy loading via `importlib.import_module()`. Fallback para text chunking se tree-sitter não instalado. `is_available()` / `supported_extensions()` para feature detection. Dependência opcional: `pip install obsidian-rag[treesitter]` |

### Embeddings (`obsidian_rag/embeddings/`)

| Módulo      | Função                                                                                            |
| ----------- | ------------------------------------------------------------------------------------------------- |
| `ollama.py` | Batch via `POST /api/embed`. `get_query_embedding()` com `@lru_cache(128)` para queries repetidas |

### Store (`obsidian_rag/store/`)

| Módulo       | Função                                                                                                                                                                                                                                                                                                 |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| _(removido)_ | O módulo legacy `chroma.py` foi **eliminado na Phase 3.1** (v0.5.0). Toda a funcionalidade de sync incremental (upsert, delete stale, get existing IDs) foi absorvida pelo `VectorStore` protocol em `chroma_store.py`/`qdrant_store.py` e pelo helper `_sync_chunks_to_store()` em `pipeline/sync.py` |

### Retrieval (`obsidian_rag/retrieval/`)

| Módulo             | Função                                                                                                                                                                                                                                                               |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `rag.py`           | `build_rag_context()` — entry point. Usa `VectorStore` protocol via `_get_store()` singleton. Adaptive top_k (`_estimate_complexity`). Multi-estratégia: vector + keyword + title. Deduplicação, threshold dinâmico, relevance gate. Sem imports diretos de ChromaDB |
| `router.py`        | `ContextMode` enum (NO_CONTEXT, RAG_ONLY, GRAPH_ONLY, RAG_AND_GRAPH, CLARIFY). LLM router (gemma3:4b) com keyword heuristic fallback                                                                                                                                 |
| `intent.py`        | Mapeia `ContextMode` → `QueryIntent(use_notes, use_code, use_graph)`                                                                                                                                                                                                 |
| `budget.py`        | Alocação de token budget: 40/40/20 (notas/código/grafo), trunca por chunks inteiros. Tokenizer regex word-boundary com multiplicador 1.3×                                                                                                                            |
| `reranker.py`      | Cross-encoder via Ollama. Score 0-10, combina 60% reranker + 40% vector. Enabled por defeito, `@lru_cache` em `_score_chunk()`                                                                                                                                       |
| `graph_context.py` | Constrói bloco de contexto do grafo: nós, comunidades, vizinhos (calls, imports_from, uses), god nodes                                                                                                                                                               |
| `observe.py`       | `QueryTrace` — captura toda a cadeia de decisão: routing, retrieval, scoring, timing, `query_complexity`, `effective_top_k`. `_JsonFormatter` para logging JSON estruturado                                                                                          |

### Graph (`obsidian_rag/graph/`)

| Módulo               | Função                                                                                                                                                                                                                                           |
| -------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `builder.py`         | Wrapper para `graphify extract` via `subprocess.run` com timeout configurável (`graph_timeout`). Throttle check antes de cada repo em `build_graphs()`. Injeta `OLLAMA_BASE_URL` e `OLLAMA_API_KEY=ollama`. Trata `TimeoutExpired` graciosamente |
| `query.py`           | Leitura de `graph.json` (node-link) com NetworkX. `load_graph()`, `get_report()`, `list_repos()`, `get_neighbors()`, NL `query_graph()`                                                                                                          |
| `cache.py`           | Cache in-memory `_RepoGraphData` com file-stat invalidation (mtime + size) e TTL (300s). Indexa nós por `(source_file, normalized_label)`                                                                                                        |
| `enrich.py`          | Community summaries via Ollama (deepseek-r1:8b/qwen3:8b), cross-community links, diagramas Mermaid, tag inference. Cache JSON local                                                                                                              |
| `obsidian_export.py` | Exporta grafos como notas Obsidian-compatible para `~/Obsidian/knowledge-graphs/`                                                                                                                                                                |

### API (`obsidian_rag/api/`)

| Módulo        | Função                                                                                                                                                                                                                                            |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app.py`      | FastAPI com `lifespan` (preload VectorStore, httpx pool). Middleware de autenticação via API key (`Bearer`). `serve()` recusa `0.0.0.0` sem `api_key`. Endpoints REST + `/chat`. Usa `_get_store()` / `_query_store()` via `VectorStore` protocol |
| `schemas.py`  | Modelos Pydantic: QueryRequest, ChatRequest, ChunkResult, RepoInfo, etc.                                                                                                                                                                          |
| `cli.py`      | Lógica de query one-shot (usado internamente por `rag query`)                                                                                                                                                                                     |
| `chat_cli.py` | REPL interativo com history, `--debug`, `--no-rag`, `--mode` (usado por `rag chat`)                                                                                                                                                               |

### CLI unificado (`obsidian_rag/cli/`) — v0.4.0

| Módulo            | Função                                                                                                                                                                     |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `main.py`         | Dispatcher `rag` — argparse com subcommands. Imports lazy para não carregar `settings` desnecessariamente                                                                  |
| `init_cmd.py`     | `rag init` — wizard interactivo: gera `rag.toml`, detecta vault/Git (cross-platform), lista modelos Ollama, valida paths perigosos (Windows/macOS/Linux)                   |
| `up_cmd.py`       | `rag up` — pre-flight checks (Ollama, modelos, vector store, disco) + `serve()`. Recusa iniciar com <500MB livres. Mostra backend e contagens via `create_store().count()` |
| `doctor_cmd.py`   | `rag doctor` — diagnóstico ✓/✗ (Python, deps, config, paths, Ollama, Vector Store, Graphify, Recursos, Performance, Sync backend). Usa `create_store().count()`            |
| `graph_cmd.py`    | `rag graph build [--force] [--repo]` + `rag graph status`. `--force` ignora cache incremental                                                                              |
| `schedule_cmd.py` | `rag schedule install\|remove\|status` — agenda sync diário cross-platform (systemd/launchd/schtasks)                                                                      |
| `_query.py`       | `rag query` — wrapper delegando a `api.cli`                                                                                                                                |
| `_chat.py`        | `rag chat` — wrapper delegando a `api.chat_cli`                                                                                                                            |
| `_backup.py`      | `rag backup` — wrapper delegando a `pipeline.backup.backup_store()`                                                                                                        |
| `migrate_cmd.py`  | `rag migrate --from X --to Y --collections ...` — migração entre backends de vector store com re-embedding                                                                 |

### Pipeline (`obsidian_rag/pipeline/`)

| Módulo           | Função                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `sync.py`        | Três modos: `-l` (notas + repos), `-g` (graphify), `--all`. Notas processadas sequencialmente (chunk_all_notes → `_sync_chunks_to_store()` via VectorStore protocol). Repos processados via **bounded ingest pipeline** (`IngestPipeline`) — 4 estágios conectados por queues bounded com backpressure. `os.nice(10)` no arranque para não bloquear o desktop/OS. Proteção de recursos em 4 camadas: auto-tune no arranque, ResourceGovernor nas verificações entre fases (`_wait_for_resources()`), ResourceGovernor contínuo no pipeline (partilhado com IngestPipeline), e cgroup externo opcional (`rag-cgroup.sh`). `KeyboardInterrupt` tratado graciosamente — imprime mensagem de aviso e sai com código 130. Desde Phase 3.1: sem imports de `store.chroma` — usa `create_store()` para todas as operações                                                                                                       |
| `governor.py`    | `ResourceGovernor` — daemon thread que amostra `psutil` a cada 1s (intervalo configurável). `check()` retorna `GovernorAction` (CONTINUE/REDUCE/PAUSE/ABORT) sem blocking (lê snapshot em cache). `wait_until_safe(timeout)` bloqueia até recursos libertarem. `ResourceSnapshot` dataclass com ram_percent, ram_available_gb, cpu_percent, disk_free_gb, timestamp. Três thresholds RAM: `max_memory_percent` → REDUCE, `pause_memory_percent` → PAUSE, `abort_memory_percent` → ABORT. Disco <1GB → ABORT. CPU > max+10% → REDUCE. Ficheiro JSONL de métricas opcional (`metrics_path`) para análise post-mortem. Thread-safe via `threading.Lock`                                                                                                                                                                                                                                                                     |
| `manifest.py`    | SQLite-backed manifest para tracking incremental de ingest. Tabelas: `files` (path, repo, mtime, size, sha256), `chunks` (chunk_id, file_path, vector_status), `ingest_runs` (run_id, status, timestamps). WAL mode para leitura concorrente segura. `threading.Lock` para escrita thread-safe. Permite crash recovery — syncs interrompidos retomam do último checkpoint em vez de reprocessar tudo                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| `dask_engine.py` | `DaskParserPool` — drop-in replacement para `ProcessPoolExecutor` usando Dask distributed. Suporta cluster local (auto-criado) ou scheduler remoto. Factory `create_parser_pool(pipeline_config)`: retorna `ProcessPoolExecutor` quando `engine="local"` (default) ou `DaskParserPool` quando `engine="dask"`. Dependência opcional: `pip install obsidian-rag[dask]`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| `ingest.py`      | `IngestPipeline` — pipeline paralelo bounded com 4 estágios: (1) scanner thread descobre ficheiros alterados via `iter_repo_files()`/`iter_note_files()`, (2) parser pool via `create_parser_pool()` factory (ProcessPoolExecutor ou DaskParserPool conforme `engine` config) parse ficheiros em chunks com isolamento de memória, (3) embedding batcher acumula micro-batches (count ≤24, chars ≤48k, ou timeout ≥1s) e chama `embed_texts()` com governor.check()/wait_until_safe(), (4) writer thread upserts via `VectorStore.upsert_batch()` com embeddings pré-calculados. Construtor aceita `store` (VectorStore) + `collection_name` + `pipeline_config` opcional (para selecção de engine). Aceita `governor` opcional — cria um automaticamente se não fornecido. Stale cleanup via `store.get_existing_ids()` + `store.delete_ids()`. Backpressure via `Queue(maxsize=...)`. `IngestResult` sumariza métricas |
| `vault_sync.py`  | 4 backends de sync do vault: `direct` (leitura in-place, default), `python` (cópia incremental shutil), `rsync` (Linux/macOS), `auto` (escolhe melhor). Exclusão por padrões configuráveis. Incremental via mtime+size                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| `backup.py`      | Backup timestamped do vector store (`shutil.copytree`) com rotação (mantém últimas 3 cópias). Função renomeada para `backup_store()` (era `backup_chroma()`). Ficheiros de backup nomeados `store_backup_*` (era `chroma_backup_*`)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |

### Auto-tuning (`obsidian_rag/tuning.py`)

| Função                  | Descrição                                                                                                                                                                                                                                                                                |
| ----------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `detect_resources()`    | Detecta RAM (total/disponível/%), CPU (cores/%), disco (GB livres), GPU (nvidia-smi) via `psutil`                                                                                                                                                                                        |
| `auto_tune(perf)`       | Ajusta `max_parallel_jobs`, `embedding_batch_size`, `parser_workers` e passa `graph_timeout` com base no hardware. Valores conservativos: ≥16GB→batch 50, 8-16GB→batch 25, <8GB→batch 15; workers capped a `cpu_cores//6` (máx. 4). Chamado em `load_settings()` quando `auto_tune=True` |
| `should_throttle(perf)` | **Thin wrapper backward-compatible:** cria um `ResourceGovernor`, toma uma amostra, e mapeia `GovernorAction` para `ThrottleAdvice`. Delega toda a lógica de decisão ao governor                                                                                                         |

### Prompts (`obsidian_rag/prompts/`)

| Módulo         | Função                                                                                                                                                                        |
| -------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `templates.py` | `SYSTEM_GENERAL` (PT-PT), `ROUTER_SYSTEM` + `ROUTER_USER_TEMPLATE` (6 exemplos), `REWRITE_SYSTEM`, `RAG_CONTEXT_INSTRUCTION`, `FALLBACK_WEAK_CONTEXT`, `GRAPH_CONTEXT_HEADER` |

## Modelos de AI/LLMs utilizados

| Modelo                              | Papel                                            | Velocidade | GPU      |
| ----------------------------------- | ------------------------------------------------ | ---------- | -------- |
| `bge-m3`                            | Embeddings (1024 dimensões, multilingue, cosine) | batch      | 100% GPU |
| `qwen3:8b` / `qwen3-pt`             | Chat geral + enrichment de grafos                | ~44 tok/s  | 100% GPU |
| `deepseek-r1:8b` / `deepseek-r1-pt` | Chain-of-thought reasoning, extração de grafos   | ~45 tok/s  | 100% GPU |
| `qwen2.5-coder:7b` / `coder-pt`     | Chat especializado em código (RAG desativado)    | ~43 tok/s  | 100% GPU |
| `gemma3:4b` / `gemma3-pt`           | Router + reranker (ultra-rápido)                 | ~77 tok/s  | 100% GPU |

As variantes `*-pt` são Modelfiles customizados com system prompt em português de Portugal, `num_ctx=16384`, e temperatura ajustada (0.3–0.7).

**Hardware:** RTX 4060 Max-Q 8GB VRAM, 24 threads CPU, 32GB RAM, Zorin OS 18.1 (Ubuntu Noble).

## Integração com Ollama

O projeto comunica com o Ollama exclusivamente via HTTP REST (localhost:11434):

| Endpoint             | Uso no projeto                                                                         |
| -------------------- | -------------------------------------------------------------------------------------- |
| `POST /api/embed`    | Embeddings batch (`embed_texts()` em `ollama.py`)                                      |
| `POST /api/generate` | Router LLM (`router.py`), reranker (`reranker.py`), enrichment de grafos (`enrich.py`) |
| `POST /api/chat`     | Chat streaming no endpoint `/chat` (`app.py`)                                          |

Não há dependência de APIs externas. Todo o processamento é local.

## APIs e endpoints

**Base URL:** `http://127.0.0.1:8484`

> **Autenticação:** Quando `api_key` está configurado em `rag.toml`, todos os endpoints (exceto `/health`, `/docs`, `/openapi.json`, `/redoc`) requerem header `Authorization: Bearer <key>`. Quando vazio (defeito), a auth é desativada para retrocompatibilidade.

| Método | Endpoint                         | Descrição                                                                 | Auth  |
| ------ | -------------------------------- | ------------------------------------------------------------------------- | ----- |
| `GET`  | `/health`                        | Health check (`{"status": "ok"}`)                                         | Não   |
| `GET`  | `/stats`                         | Estatísticas das coleções do vector store                                 | Sim\* |
| `POST` | `/query`                         | Pesquisa semântica nas notas (obsidian_vault)                             | Sim\* |
| `POST` | `/query/code`                    | Pesquisa semântica no código (code_repos). Filtros: `repo`, `symbol_type` | Sim\* |
| `GET`  | `/repos`                         | Lista repos configurados com stats de chunks e grafos                     | Sim\* |
| `GET`  | `/graph/{repo}`                  | Devolve o GRAPH_REPORT.md de um repo                                      | Sim\* |
| `POST` | `/graph/{repo}/query`            | Query em linguagem natural ao knowledge graph                             | Sim\* |
| `GET`  | `/graph/{repo}/neighbors/{node}` | Vizinhos de um nó no grafo                                                | Sim\* |
| `POST` | `/chat`                          | Chat RAG-augmented com streaming (proxy Ollama)                           | Sim\* |

_\*Apenas quando `api_key` está definido em `rag.toml` ou via `RAG_API_API_KEY`._

## CLI — Comando unificado `rag`

Desde a v0.4.0, todos os 5 entry points antigos (`rag-sync`, `rag-serve`, `rag-query`, `rag-chat`, `rag-backup`) foram substituídos por um único comando `rag` com subcomandos. Entry point definido em `pyproject.toml`: `rag = "obsidian_rag.cli.main:main"`.

| Comando                                                  | Descrição                                                                                                                                                |
| -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `rag init`                                               | Wizard interactivo: gera `rag.toml`, detecta vault Obsidian e repos Git, lista modelos Ollama, valida paths perigosos, força `api_key` se bind `0.0.0.0` |
| `rag up`                                                 | Pre-flight checks (Ollama, modelos, vector store, disco ≥500MB) → inicia API. Avisa com <1GB livres. Mostra backend e contagens                          |
| `rag doctor`                                             | Diagnóstico do sistema com output ✓/✗ (Python, deps, config, paths, Ollama, Vector Store, Graphify, Recursos, Performance)                               |
| `rag sync -l`                                            | Sincroniza embeddings de notas (sequencial) + repos (bounded pipeline paralelo com backpressure)                                                         |
| `rag sync -g [--force]`                                  | Constrói knowledge graphs via Graphify                                                                                                                   |
| `rag sync --all`                                         | Executa `-l` seguido de `-g` (também executável via `scripts/rag-cgroup.sh` com limites de cgroup)                                                       |
| `rag serve`                                              | Inicia FastAPI em `127.0.0.1:8484` (recusa `0.0.0.0` sem `api_key`)                                                                                      |
| `rag query "texto" [-n N]`                               | Pesquisa semântica one-shot (stdout ou `--json`)                                                                                                         |
| `rag chat [-m modelo] [--debug] [--no-rag] [--mode ...]` | Chat interactivo com RAG                                                                                                                                 |
| `rag backup [destino]`                                   | Backup timestamped do vector store com rotação automática (mantém últimas 3 cópias). Ficheiros nomeados `store_backup_*`                                 |
| `rag migrate --from X --to Y [--collections ...]`        | Migrar dados entre backends de vector store (Chroma → Qdrant ou vice-versa) com re-embedding                                                             |
| `rag graph build [--force] [--repo NOME]`                | Construir knowledge graphs (um repo ou todos)                                                                                                            |
| `rag graph status`                                       | Mostrar estado dos grafos por repositório                                                                                                                |

### Shell helpers (zsh)

| Comando    | Função                                                |
| ---------- | ----------------------------------------------------- |
| `ol`       | Proxy para `:8484/chat` com fallback direto ao Ollama |
| `aicode`   | Chat com modelo coder-pt                              |
| `aiask`    | Query rápida                                          |
| `aimodels` | Lista modelos Ollama disponíveis                      |
| `aistatus` | Status do serviço RAG                                 |
| `aiembed`  | Re-sync de embeddings                                 |

## Dependências principais

### Obrigatórias

| Pacote              | Versão   | Função                                                                                                                                                           |
| ------------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `chromadb`          | ≥ 0.5    | Base de dados vetorial persistente (HNSW, cosine)                                                                                                                |
| `qdrant-client`     | ≥ 1.9    | Cliente Qdrant — **dependência opcional** (`pip install obsidian-rag[qdrant]`). Modo embedded ou server                                                          |
| `dask[distributed]` | ≥ 2024.1 | Dask distributed — **dependência opcional** (`pip install obsidian-rag[dask]`). Engine alternativo para parser pool (cluster local ou remoto)                    |
| `tree-sitter`       | ≥ 0.23   | Parser multi-linguagem — **dependência opcional** (`pip install obsidian-rag[treesitter]`). Inclui 9 grammar packages (JS, TS, Java, Go, Rust, C, C++, C#, Ruby) |
| `fastapi`           | ≥ 0.110  | Framework REST API                                                                                                                                               |
| `uvicorn[standard]` | ≥ 0.29   | Servidor ASGI                                                                                                                                                    |
| `httpx`             | ≥ 0.27   | Cliente HTTP assíncrono (Ollama)                                                                                                                                 |
| `networkx`          | ≥ 3.0    | Leitura e query de grafos (graph.json)                                                                                                                           |
| `slowapi`           | ≥ 0.1.9  | Rate limiting na API                                                                                                                                             |
| `psutil`            | ≥ 5.9    | Detecção de recursos (RAM, CPU, disco) para auto-tuning e throttling                                                                                             |
| `graphifyy`         | —        | Knowledge graphs (AST + LLM). Pure Python (`py3-none-any`). Opt-in na execução (`enabled = false` por defeito)                                                   |

> **Nota (v0.4.0):** `graphifyy` foi promovido de dependência opcional a obrigatória. É um pacote pure Python leve, instalado sempre, mas a execução de grafos continua opt-in via `[graphify] enabled` em `rag.toml`.

### Desenvolvimento

| Pacote           | Versão | Função                           |
| ---------------- | ------ | -------------------------------- |
| `pytest`         | ≥ 8.0  | Framework de testes              |
| `pytest-asyncio` | ≥ 0.23 | Suporte async para testes pytest |
| `pytest-cov`     | ≥ 5.0  | Coverage integrado com pytest    |
| `coverage`       | ≥ 7.0  | Cobertura de código              |
| `mypy`           | ≥ 1.10 | Type checking                    |
| `ruff`           | ≥ 0.4  | Linter e formatter               |
| `types-requests` | ≥ 2.31 | Type stubs para requests         |

### Stdlib utilizada

| Módulo                       | Função                                                                                       |
| ---------------------------- | -------------------------------------------------------------------------------------------- |
| `ast`                        | Parsing de código Python para chunking por função/classe                                     |
| `tomllib`                    | Leitura do `rag.toml` (Python 3.11+)                                                         |
| `hashlib`                    | SHA256 para IDs de chunks e ficheiros (sync incremental + manifest)                          |
| `functools.lru_cache`        | Cache de embeddings de queries e reranker scores                                             |
| `secrets`                    | Comparação timing-safe de API keys (`compare_digest`)                                        |
| `threading`                  | Lock para singletons thread-safe (double-checked locking) + ResourceGovernor daemon thread   |
| `importlib.metadata`         | Versão centralizada via `version("obsidian-rag")`                                            |
| `importlib`                  | Lazy loading de grammar modules tree-sitter via `import_module()`                            |
| `unicodedata`                | Normalização NFC em `_extract_keywords()`                                                    |
| `re`                         | Tokenizer regex word-boundary (`budget.py`)                                                  |
| `sqlite3`                    | Manifest de ingest (ficheiros, chunks, runs) com WAL mode                                    |
| `queue`                      | `Queue(maxsize=...)` para backpressure no bounded pipeline                                   |
| `concurrent.futures`         | `ProcessPoolExecutor` (spawn) para parsing paralelo (via `dask_engine.create_parser_pool()`) |
| `multiprocessing`            | `get_context("spawn")` para isolamento de memória (via `dask_engine.create_parser_pool()`)   |
| `gc`                         | Garbage collection explícito após pipeline run                                               |
| `os`                         | `os.nice(10)` para prioridade inferior do processo sync                                      |
| `shutil.disk_usage`          | Verificação de espaço em disco (`rag up`, `tuning.py`)                                       |
| `shutil`                     | Cópia de diretórios do vector store para backup + sync python                                |
| `platform`                   | Detecção de OS (Linux/Darwin/Windows) para cross-platform                                    |
| `fnmatch`                    | Matching de exclude patterns no vault_sync                                                   |
| `json` / `logging.Formatter` | Logging estruturado JSON (`observe.py`)                                                      |

## Tecnologias usadas

| Tecnologia       | Contexto                                                              |
| ---------------- | --------------------------------------------------------------------- |
| **Python 3.11+** | Linguagem principal                                                   |
| **Ollama**       | Runtime local de LLMs e embeddings                                    |
| **ChromaDB**     | Vector store persistente (HNSW, cosine similarity) — backend default  |
| **Qdrant**       | Vector store alternativo (embedded/server, cosine) — backend opcional |
| **FastAPI**      | API REST assíncrona                                                   |
| **NetworkX**     | Análise e query de grafos                                             |
| **Graphify**     | Extração de knowledge graphs de repositórios                          |
| **Pydantic**     | Validação de schemas (API requests/responses)                         |
| **systemd**      | Timer para sync diário (Linux)                                        |
| **launchd**      | Agent para sync diário (macOS)                                        |
| **schtasks**     | Scheduled Task para sync diário (Windows)                             |

## Como executar o projeto localmente

### Pré-requisitos

- Python ≥ 3.11
- Ollama instalado e a correr em `localhost:11434`
- Modelo `bge-m3` disponível (`ollama pull bge-m3`)
- Vault Obsidian em `~/Obsidian/Vault` (configurável em `rag.toml`)
- **Plataformas suportadas:** Linux, macOS, Windows

### Instalação

```bash
# Linux / macOS — instalador automatizado (cria venv, instala deps, valida)
./install.sh

# Windows — PowerShell (cria venv, instala deps, valida)
.\install.ps1

# Ou manualmente (qualquer plataforma):
pip install -e .
```

### Configuração inicial

```bash
# Wizard interactivo — gera rag.toml
rag init

# Diagnóstico do sistema
rag doctor
```

### Uso

```bash
# Sincronizar notas + repos (notas sequenciais, repos via bounded pipeline)
rag sync -l

# Construir knowledge graphs
rag sync -g
rag sync -g --force   # rebuild completo

# Sincronizar tudo
rag sync --all

# Backup vector store (com rotação automática, mantém últimas 3 cópias)
rag backup

# Iniciar API (com pre-flight checks)
rag up

# Ou directamente:
rag serve              # FastAPI em 127.0.0.1:8484

# Query one-shot
rag query "como funciona o chunking?"
rag query -n 10 "configurar aliases zsh"
rag query --json "configurar aliases zsh"

# Chat interativo
rag chat
rag chat -m deepseek-r1-pt --debug
rag chat --no-rag
rag chat --mode graph_only

# Knowledge graphs
rag graph build
rag graph build --force --repo SPEECH-LAB
rag graph status
```

### Makefile (atalhos)

```bash
make install    # ./install.sh
make init       # rag init
make up         # rag up
make serve      # rag serve
make sync       # rag sync --all
make graph      # rag graph build
make doctor     # rag doctor
make test       # pytest
make backup     # rag backup
make clean      # limpar __pycache__, .pytest_cache, .egg-info

# Targets CI (usam Python do PATH — compatíveis com CI e venv activado)
make lint       # ruff check
make typecheck  # mypy
make test-cov   # pytest + coverage (fail-under 30%)
make ci         # lint + typecheck + test-cov
make docker-build  # docker build
make docker-check  # docker compose config
```

### Environment overrides

Qualquer opção de `rag.toml` pode ser sobreposta via variável de ambiente `RAG_{SECÇÃO}_{CHAVE}`:

```bash
RAG_RETRIEVAL_TOP_K=15 rag serve
RAG_GRAPHIFY_AUTO_UPDATE=true rag sync -g
RAG_DEBUG_ENABLED=true rag serve
RAG_API_PORT=9000 rag serve
```

### Execução com Docker

```bash
# Build e arranque (liga-se ao Ollama do host)
docker compose up -d

# A API fica disponível em http://localhost:8000
curl http://localhost:8000/health

# Logs
docker compose logs -f obsidian-rag

# Parar
docker compose down
```

O `docker-compose.yml` monta `./data` como volume e configura `extra_hosts: host.docker.internal:host-gateway` para aceder ao Ollama do host. A imagem usa multi-stage build com `python:3.11-slim`, com `apt-get upgrade` em ambos os stages (builder e runtime) para patches OS-level e remoção de `pip`, `setuptools` e `wheel` do runtime stage (ferramentas de build não necessárias em runtime que continham CVE-2026-23949 e CVE-2026-24049) — necessário para passar os scans Trivy nos workflows `release-gate.yml` e `security-scheduled.yml`. O `CMD` é `["rag", "serve"]`.

**Qdrant (opcional):** O `docker-compose.yml` inclui um serviço `qdrant` (qdrant/qdrant:v1.13.2) nas portas 6333/6334, ativado via profile: `docker compose --profile qdrant up`. Para usar Qdrant como backend, configurar `[store] backend = "qdrant"` e `qdrant_url = "http://localhost:6333"` em `rag.toml`.

### Monitorização durante sync

O script `scripts/monitor_rag.sh` permite monitorizar recursos em tempo real durante `rag sync`:

```bash
# Monitor com intervalo padrão de 3 segundos
bash scripts/monitor_rag.sh

# Intervalo personalizado (ex: 5 segundos)
bash scripts/monitor_rag.sh 5
```

Mostra: RAM (`free -h`), CPU (`top`), disco (partição `data/`), processos RAG/Ollama/Graphify activos e GPU (se `nvidia-smi` disponível). Termina com Ctrl+C.

## Como configurar o ambiente

### Ficheiro principal: `rag.toml`

| Secção             | Opções-chave                                                                                                                                                                                                                                                                                                                                                                                              |
| ------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `[paths]`          | `source_dir`, `data_dir`, `vault_dir`                                                                                                                                                                                                                                                                                                                                                                     |
| `[sync]`           | `backend=direct` (direct\|python\|rsync\|auto), `delete_missing=true`, `follow_symlinks=false`, `exclude_patterns=[...]`                                                                                                                                                                                                                                                                                  |
| `[ollama]`         | `base_url`, `embedding_model`                                                                                                                                                                                                                                                                                                                                                                             |
| `[chunking]`       | `max_chars=2000`, `overlap_chars=200`, `min_chars=50`, `contextual_prefix=true`                                                                                                                                                                                                                                                                                                                           |
| `[retrieval]`      | `top_k=10`, `score_threshold=0.45`, `dynamic_threshold_ratio=0.75`, `token_budget=4000`, `context_mode=auto`                                                                                                                                                                                                                                                                                              |
| `[api]`            | `host=127.0.0.1`, `port=8484`, `api_key=""` (vazio = sem auth; override: `RAG_API_API_KEY`)                                                                                                                                                                                                                                                                                                               |
| `[models]`         | Per-model RAG toggle (ex: `"coder-pt" = false`)                                                                                                                                                                                                                                                                                                                                                           |
| `[router]`         | `enabled=true`, `model=gemma3:4b`, `timeout=15.0`                                                                                                                                                                                                                                                                                                                                                         |
| `[reranker]`       | `enabled=true`, `model=gemma3:4b`, `top_k_candidates=30`                                                                                                                                                                                                                                                                                                                                                  |
| `[context_policy]` | `min_relevance_score=0.50`, `min_relevant_chunks=1`                                                                                                                                                                                                                                                                                                                                                       |
| `[debug]`          | `enabled=false`, `log_to_file=false`, `log_level=INFO`, `log_format="text"` (ou `"json"` para logging estruturado)                                                                                                                                                                                                                                                                                        |
| `[repos]`          | `paths=[...]`, `collection_name=code_repos`                                                                                                                                                                                                                                                                                                                                                               |
| `[store]`          | `backend="chroma"` (chroma\|qdrant), `qdrant_url`, `qdrant_api_key`. Factory `create_store()` lê esta secção. Desde Phase 3.1, controla o backend para **leituras e escritas** (pipeline sync, ingest, backup)                                                                                                                                                                                            |
| `[pipeline]`       | `max_workers=4` — **efectivamente dead code** desde Phase 1; `PerformanceConfig.parser_workers` é o controlo real de paralelismo. Mantido por retrocompatibilidade                                                                                                                                                                                                                                        |
| `[performance]`    | `auto_tune=true`, `max_cpu_percent=75`, `max_memory_percent=80`, `max_parallel_jobs=4`, `embedding_batch_size=50`, `query_timeout_seconds=30`, `graph_timeout=600`, **`parser_workers=3`** (ProcessPoolExecutor), **`embedding_batch_max_chars=48000`**, **`chunks_queue_max=128`**, **`files_queue_max=256`**, **`pause_memory_percent=75`**, **`abort_memory_percent=85`** (bounded pipeline Phase 1+2) |
| `[graphify]`       | `enabled=true`, `backend=ollama`, `model=deepseek-r1:8b`, `output_dir=data/graphify`                                                                                                                                                                                                                                                                                                                      |

### Scheduler (cross-platform)

O sync pode ser agendado automaticamente via `rag schedule install`, executando `rag sync --all` diariamente às 04:00:

| Plataforma | Mecanismo                     | Ficheiro                                             |
| ---------- | ----------------------------- | ---------------------------------------------------- |
| Linux      | systemd user timer            | `~/.config/systemd/user/obsidian-rag-sync.*`         |
| macOS      | launchd user agent (plist)    | `~/Library/LaunchAgents/com.obsidian-rag.sync.plist` |
| Windows    | schtasks.exe (Scheduled Task) | `ObsidianRAGSync`                                    |

## Como testar funcionalidades

### Testes manuais

```bash
# Diagnóstico completo do sistema
rag doctor

# Verificar que o Ollama está acessível
curl http://localhost:11434/api/tags

# Verificar que a API está a correr
curl http://localhost:8484/health

# Testar query de notas
curl -X POST http://localhost:8484/query \
  -H "Content-Type: application/json" \
  -d '{"query": "como configurar aliases"}'

# Testar chat
curl -X POST http://localhost:8484/chat \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen3-pt", "messages": [{"role": "user", "content": "Olá"}]}'

# Testar via CLI com debug
rag chat --debug -m qwen3-pt
```

### Testes automatizados

```bash
# Executar todos os testes
pytest

# Com cobertura (igual ao CI)
pytest tests/ -q --cov=obsidian_rag --cov-report=term-missing --cov-fail-under=30

# CI completo local (lint + typecheck + testes + coverage)
make ci

# Testes de um módulo específico
pytest tests/test_chunking_markdown.py
pytest tests/test_api.py -v
```

**CI/CD (GitHub Actions):** 5 workflows em `.github/workflows/`:

| Workflow                 | Trigger                  | Jobs                                                                                |
| ------------------------ | ------------------------ | ----------------------------------------------------------------------------------- |
| `ci.yml`                 | push/PR → main           | lint, test matrix (3 OS × 2 Python), CLI smoke (3 OS), config tests, security audit |
| `docker.yml`             | push/PR → main           | Docker build, compose config, sanity check                                          |
| `release.yml`            | tag `v*`                 | CI → build wheel/sdist → GitHub Release → Docker image                              |
| `release-gate.yml`       | PR → main, workflow_call | Docker build, non-root check, health endpoint, Trivy image scan, OWASP ZAP baseline |
| `security-scheduled.yml` | cron (semanal)           | Source scan (pre-commit, pip-audit, Trivy fs), Container scan (Trivy image)         |

**329 testes** (18 skipped) em 20 ficheiros, sem dependências externas (Ollama, ChromaDB):

| Ficheiro                      | Testes | Cobertura                                                                                                                                                                                                                                                                                             |
| ----------------------------- | ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_chunking_markdown.py`   | 17     | `_compute_hash`, `_strip_frontmatter`, `_is_navigation_content`, `_split_by_headers`, `chunk_note`                                                                                                                                                                                                    |
| `test_chunking_code.py`       | 13     | `_split_if_long`, `_build_chunk`, `_chunk_python_source`, `_chunk_text_fallback`, dispatch tree-sitter                                                                                                                                                                                                |
| `test_chunking_treesitter.py` | 22     | Tree-sitter: availability, JS (function/class/methods/metadata/prefix), TS (interface/function/export class), Java (class/constructor/methods), Go (function/type), Rust (impl/methods/name), C (function), dispatch (.js/.ts/.go), edge cases (empty/syntax error/min_chars/long split/module-level) |
| `test_router.py`              | 13     | `_heuristic_route` com queries PT/EN, sinais de grafo/locais, edge cases                                                                                                                                                                                                                              |
| `test_budget.py`              | 16     | `estimate_tokens`, `allocate_budget`, `truncate_chunks`, `truncate_text`                                                                                                                                                                                                                              |
| `test_api.py`                 | 7      | `/health`, middleware de auth (401 missing/wrong key, pass com key correcta)                                                                                                                                                                                                                          |
| `test_cli_dispatch.py`        | —      | Dispatcher `rag`, subcommands, argparse                                                                                                                                                                                                                                                               |
| `test_init.py`                | —      | `rag init`: validação de paths perigosos, geração de rag.toml                                                                                                                                                                                                                                         |
| `test_security.py`            | —      | Bind validation (`0.0.0.0` sem key), `_EXCLUDED_DIRS`, sanitização de paths                                                                                                                                                                                                                           |
| `test_medium_features.py`     | 25     | Backup, sync paralelo, logging JSON, tokenizer regex, configurações pipeline/debug                                                                                                                                                                                                                    |
| `test_performance.py`         | 10     | `PerformanceConfig` defaults, `auto_tune` logic, `should_throttle` (patches governor.psutil), workers capping, retrocompat                                                                                                                                                                            |
| `test_adaptive_topk.py`       | 16     | `_estimate_complexity`, adaptive top_k scaling (simple/normal/complex)                                                                                                                                                                                                                                |
| `test_integration.py`         | 16     | `/query`, `/query/code`, `/stats` com ChromaDB in-memory via `ChromaVectorStore` + `_get_store` mock, validação Pydantic (422)                                                                                                                                                                        |
| `test_manifest.py`            | 25     | `IngestManifest` SQLite CRUD: files, chunks, runs, crash recovery, stale detection, `needs_reindex`, `file_sha256`, WAL mode                                                                                                                                                                          |
| `test_ingest_pipeline.py`     | 10     | `IngestPipeline`: 4 estágios bounded, backpressure, abort, embed fn injection, stale cleanup, `IngestResult` metrics                                                                                                                                                                                  |
| `test_governor.py`            | 21     | `ResourceGovernor`: `_evaluate` thresholds (9), lifecycle start/stop (4), `wait_until_safe` (3), JSONL metrics (2), `should_throttle` backward compat (3)                                                                                                                                             |
| `test_low_priority.py`        | 27     | Thread-safe singletons (`_store`), Unicode normalization, `__all__` exports, reranker LRU cache, stop words bilíngues, embedding timeout, `clear_embed_cache()`                                                                                                                                       |
| `test_vault_sync.py`          | 42     | Sync backends (direct/python/rsync/auto), exclusão de padrões, incremental copy, delete_missing, cross-platform path validation, symlinks                                                                                                                                                             |
| `test_dask_engine.py`         | 6      | `create_parser_pool` factory (local engine, unknown engine error, dask import error), DaskParserPool integration (skipped se dask não instalado), IngestPipeline engine config integration                                                                                                            |
| `test_vector_store.py`        | 34     | VectorStore protocol: parametrizado Chroma/Qdrant (19 pass, 15 skip sem qdrant-client). upsert, count, get_existing_ids, delete, query, collection isolation, cosine similarity, factory `create_store()`                                                                                             |

Fixtures partilhadas em `conftest.py`: `tmp_source_dir`, `sample_markdown_note`, `navigation_note`, `sample_python_source`. Testes tree-sitter usam `pytest.importorskip("tree_sitter")` — 22 testes skipped se tree-sitter não instalado.

## Limitações conhecidas

| Limitação                         | Descrição                                                                                                                                                                                                                                                                                                      |
| --------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Cobertura de testes parcial**   | 329 testes (18 skipped, unit + integration) cobrindo chunking (markdown + code + tree-sitter), router, budget, API auth, CLI, segurança, performance, adaptive top_k, vault_sync, cross-platform, manifest, ingest pipeline, ResourceGovernor, VectorStore protocol e Dask engine. Faltam e2e tests com Ollama |
| **Chunking tree-sitter opcional** | Tree-sitter chunking (JS/TS/Java/Go/Rust/C/C++/C#/Ruby) requer instalação explícita: `pip install obsidian-rag[treesitter]`. Sem tree-sitter, estas linguagens usam fallback textual                                                                                                                           |
| **Dask engine opcional**          | Engine Dask distribuído (`engine = "dask"` em `[pipeline]`) requer `pip install obsidian-rag[dask]`. Default é `local` (ProcessPoolExecutor)                                                                                                                                                                   |
| **Auth opcional na API**          | API key auth disponível (`Bearer`) mas desativada por defeito (campo `api_key` vazio)                                                                                                                                                                                                                          |
| **Graphify depende de LLM**       | A extração semântica de grafos requer chamadas ao Ollama, que pode ser lento                                                                                                                                                                                                                                   |
| **Single-user**                   | A arquitetura não suporta múltiplos utilizadores concorrentes de forma otimizada                                                                                                                                                                                                                               |
| **rsync só em Linux/macOS**       | O backend `rsync` não funciona nativamente no Windows (fallback automático para `python` ou usar backend `direct`)                                                                                                                                                                                             |

## Estado atual do projeto

| Aspeto               | Estado                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Versão**           | 0.5.0                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   |
| **Maturidade**       | Funcional para uso pessoal. Cross-platform (Linux, macOS, Windows). Containerizado com Docker. Não é production-ready para deployment multi-utilizador                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| **Pipeline RAG**     | Completo e funcional: sync (4 backends) → chunking (Markdown headers + Python AST + tree-sitter multi-linguagem) → embeddings → VectorStore (Chroma default / Qdrant opcional) → retrieval multi-estratégia com adaptive top_k. Notas processadas sequencialmente. **Repos processados via bounded ingest pipeline** (Phase 1+2): 4 estágios (scanner → parser pool → embedding batcher → writer) conectados por queues bounded com backpressure. **Parser pool via factory `create_parser_pool()`** (Phase 5): `ProcessPoolExecutor` (default, `engine="local"`) ou `DaskParserPool` distribuído (`engine="dask"`, requer `pip install obsidian-rag[dask]`). `ResourceGovernor` (Phase 2) monitoriza recursos continuamente via daemon thread. SQLite manifest para crash recovery e ingest incremental. `os.nice(10)` para não bloquear o desktop. Proteção de recursos ao nível do OS via `rag-cgroup.sh` (opcional). **VectorStore Protocol** (Phase 3): abstração `VectorStore` com factory `create_store()`, permitindo trocar entre ChromaDB e Qdrant via configuração. Comando `rag migrate` para migração entre backends. **Phase 3.1**: Todas as operações de escrita (sync, ingest, backup) migradas para o protocolo VectorStore. Módulo legacy `store/chroma.py` eliminado |
| **Knowledge graphs** | Funcional com Graphify (agora dep obrigatória, opt-in na execução). Enrichment + Mermaid + export Obsidian                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| **API**              | 9 endpoints REST funcionais + streaming chat. Bind validation de segurança em `serve()`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| **CLI**              | Comando unificado `rag` com 15 subcomandos (init, up, doctor, sync, serve, query, chat, backup, migrate, graph build/status, schedule install/remove/status) + helpers zsh                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| **DX**               | `install.sh` (Linux/macOS) + `install.ps1` (Windows) + `Makefile` + `rag init` wizard + `rag doctor` diagnóstico + `rag up` pre-flight                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| **Plataformas**      | Linux, macOS e Windows nativamente suportados. Sync, scheduler, instalação e path validation cross-platform                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| **Config**           | `_LazySettings` proxy — config só carrega no primeiro acesso. `rag init` e `rag doctor` funcionam sem `rag.toml`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |
| **Router**           | LLM (gemma3:4b) + keyword heuristic fallback — funcional                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| **Reranker**         | Habilitado por defeito com LRU cache em `_score_chunk()`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |
| **Observabilidade**  | `QueryTrace` com decisões completas + `query_complexity`/`effective_top_k`. Logging JSON. Auto-tune logging. Debug mode `--debug`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |
| **Backup**           | `rag backup` — backup timestamped do vector store com rotação automática (3 cópias). Ficheiros `store_backup_*`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| **Docker**           | `Dockerfile` multi-stage + `docker-compose.yml`. User não-root (UID 1000). `HEALTHCHECK` Python stdlib. Bind `127.0.0.1` por defeito. Volume `data/`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| **Segurança**        | `SECURITY.md`, bind validation, path validation cross-platform, API key + rate limiting, CodeQL, Dependabot (pip + actions + docker)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |
| **Sync**             | 4 backends: `direct` (default, cross-platform), `python`, `rsync`, `auto`. Configurável em `[sync]`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| **Documentação**     | Este ficheiro + `IMPROVEMENTS_AND_RISKS.md`                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |
| **Testes**           | 329 testes (18 skipped) em 20 ficheiros com pytest. Todos passam sem deps externas. Cobertura: 61%                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| **CI/CD**            | 4 workflows GitHub Actions: `ci.yml` (matrix 3 OS × 2 Python + lint + security), `docker.yml`, `release.yml`, `codeql.yml`. Sem Ollama/GPU em CI                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |

---

## Regra de manutenção da documentação

> **Sempre que qualquer alteração for feita ao projeto** — código, configuração, modelos, prompts, arquitetura, dependências, novo agente, nova funcionalidade — **este documento e `docs/IMPROVEMENTS_AND_RISKS.md` devem ser atualizados obrigatoriamente.**
>
> Uma tarefa só é considerada concluída quando a documentação relevante tiver sido revista e atualizada.
