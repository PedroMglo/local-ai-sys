# PROJECT OVERVIEW — obsidian-rag

> **Versão:** 0.3.1  
> **Última atualização:** 2026-05-10  
> **Linguagem:** Python ≥ 3.11  
> **Licença:** A confirmar

---

## Índice

1. [Objetivo principal](#objetivo-principal)
2. [Problema que o projeto resolve](#problema-que-o-projeto-resolve)
3. [Casos de uso principais](#casos-de-uso-principais)
4. [Arquitetura geral](#arquitetura-geral)
5. [Estrutura de pastas e ficheiros](#estrutura-de-pastas-e-ficheiros)
6. [Fluxo de funcionamento](#fluxo-de-funcionamento)
7. [Componentes principais](#componentes-principais)
8. [Modelos de AI/LLMs utilizados](#modelos-de-aillms-utilizados)
9. [Integração com Ollama](#integração-com-ollama)
10. [APIs e endpoints](#apis-e-endpoints)
11. [CLI — Entry Points](#cli--entry-points)
12. [Dependências principais](#dependências-principais)
13. [Tecnologias usadas](#tecnologias-usadas)
14. [Como executar o projeto localmente](#como-executar-o-projeto-localmente)
15. [Como configurar o ambiente](#como-configurar-o-ambiente)
16. [Como testar funcionalidades](#como-testar-funcionalidades)
17. [Limitações conhecidas](#limitações-conhecidas)
18. [Estado atual do projeto](#estado-atual-do-projeto)
19. [Regra de manutenção da documentação](#regra-de-manutenção-da-documentação)

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
┌─────────────────┐     rsync      ┌───────────────┐
│  Obsidian Vault │───────────────►│   source/     │
└─────────────────┘                └──────┬────────┘
                                          │
                                   chunk_all_notes()
                                   (header-split + overlap)
                                          │
┌─────────────────┐                       │
│  Git Repos      │───► chunk_repo() ─────┤
│  (SPEECH-LAB,   │    (AST Python +      │
│   ApacheSpark,  │     Markdown fallback) │
│   obsidian-rag) │                       │
└────────┬────────┘                       │
         │                         embed_texts()
         │                         Ollama bge-m3 (1024d, cosine)
         │                                │
         │                        ┌───────▼────────┐
         │                        │   ChromaDB     │
         │                        │ (persistente)  │
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
├── pyproject.toml              # Package config, dependências, entry points
├── rag.toml                    # Configuração central (todas as opções)
├── requirements.txt            # Dependências mínimas
├── README.md                   # Documentação básica
├── Dockerfile                  # Multi-stage build (python:3.11-slim)
├── docker-compose.yml          # Serviço obsidian-rag + rede Ollama
├── docs/                       # Documentação técnica detalhada
│   ├── PROJECT_OVERVIEW.md     # Este ficheiro
│   └── IMPROVEMENTS_AND_RISKS.md
├── tests/                      # Testes automatizados (pytest)
│   ├── __init__.py
│   ├── conftest.py             # Fixtures partilhadas
│   ├── test_api.py             # Testes de auth middleware e /health
│   ├── test_budget.py          # Testes de alocação de token budget
│   ├── test_chunking_code.py   # Testes de chunking Python (AST)
│   ├── test_chunking_markdown.py # Testes de chunking Markdown
│   └── test_router.py          # Testes de heurística do router
├── .github/
│   ├── agents/                 # Agentes VS Code Copilot
│   │   └── doc-reviewer.agent.md
│   └── instructions/           # Instruções de manutenção
│       └── doc-maintenance.instructions.md
├── source/                     # Notas Obsidian sincronizadas (rsync do vault)
├── data/
│   ├── chroma/                 # ChromaDB persistente (chroma.sqlite3)
│   └── graphify/               # Grafos por repositório
│       ├── ApacheSpark-CD/graphify-out/
│       ├── obsidian-rag/graphify-out/
│       └── SPEECH-LAB/graphify-out/
├── obsidian_rag/               # Código principal
│   ├── __init__.py
│   ├── config.py               # Carregamento de rag.toml + env overrides + PipelineConfig + DebugConfig
│   ├── api/                    # FastAPI endpoints + CLIs
│   │   ├── app.py              # Aplicação FastAPI + lifespan
│   │   ├── schemas.py          # Modelos Pydantic (request/response)
│   │   ├── cli.py              # rag-query CLI
│   │   └── chat_cli.py         # rag-chat CLI (REPL interativo)
│   ├── chunking/               # Divisão de texto em chunks
│   │   ├── markdown.py         # Chunking por headers H1/H2/H3
│   │   └── code.py             # Chunking via ast.parse() (Python)
│   ├── embeddings/
│   │   └── ollama.py           # Embeddings via Ollama bge-m3
│   ├── graph/                  # Knowledge graph (Graphify + NetworkX)
│   │   ├── builder.py          # Wrapper para graphify extract
│   │   ├── query.py            # Queries ao grafo (NetworkX)
│   │   ├── cache.py            # Cache in-memory com TTL + file-stat
│   │   ├── enrich.py           # Community summaries, Mermaid, tags
│   │   └── obsidian_export.py  # Export para vault Obsidian
│   ├── pipeline/
│   │   ├── sync.py             # Pipeline de sincronização (rag-sync) — sync paralelo
│   │   ├── backup.py           # Backup ChromaDB com rotação (rag-backup)
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
│       └── chroma.py           # ChromaDB client + sync incremental
└── source/
    └── AI-context/             # Documentação contextual do sistema
        ├── local-ai/           # Setup Ollama, modelos, benchmarks
        ├── shell-linux/        # Configuração zsh, aliases, ferramentas
        ├── system-audit/       # Auditoria do sistema
        └── system-profile/     # Hardware, OS, GPU, ambiente dev
```

## Fluxo de funcionamento

### 1. Sincronização (`rag-sync`)

```
rag-sync -l:
  1. Copia notas do vault Obsidian → source/
  2. chunk_all_notes() — divide por headers H1/H2/H3, aplica overlap
  3. Gera SHA256 IDs para sync incremental (só chunks novos/alterados)
  4. embed_texts() — gera embeddings via Ollama bge-m3 (batches de 50)
  5. sync_to_chroma() — upsert na coleção "obsidian_vault"
  6. Para cada repo em [repos].paths:
     a. chunk_repo() — AST parse (Python) + markdown fallback
     b. sync_repo_to_chroma() — upsert na coleção "code_repos"

rag-sync -g:
  1. graphify extract — extrai grafo estrutural de cada repo
  2. Gera graph.json (node-link), GRAPH_REPORT.md, community_summaries.json
  3. export_all() — exporta grafos como notas Markdown para ~/Obsidian/knowledge-graphs/
  4. Invalida cache do grafo em memória

rag-sync --all:
  Executa -l seguido de -g
```

### 2. Query (`rag-query`, `/query`, `/query/code`)

```
1. Recebe query textual
2. get_query_embedding() — embedding da query (com cache LRU de 128 entradas)
3. ChromaDB.query() — pesquisa vetorial (cosine similarity)
4. Filtra por score mínimo
5. Devolve ChunkResults ordenados por relevância
```

### 3. Chat RAG-augmented (`rag-chat`, `/chat`)

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
5. Pesquisa multi-estratégia:
   a. Primária: vector search (notas + código)
   b. Secundária: keyword search (sem stop words PT)
   c. Terciária: title-based search
6. Deduplicação por (source_path, section_header, chunk_index)
7. Dynamic threshold: max(0.45, best_score × 0.75)
8. Reranker opcional (cross-encoder via gemma3:4b, disabled por defeito)
9. Relevance gate: contexto descartado se best score < 0.50 ou < 1 chunk
10. Token budget allocation: 4000 tokens, split 40/40/20 (notas/código/grafo)
11. Injeta contexto como system message → stream para Ollama → resposta ao utilizador
```

## Componentes principais

### Chunking (`obsidian_rag/chunking/`)

| Módulo        | Função                                                                                                                                                                                                                                                            |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `markdown.py` | Divide `.md` por headers H1/H2/H3. Sliding-window fallback com overlap. Strips YAML frontmatter. Filtra chunks de navegação (>60-70% wikilinks). Adiciona contextual prefix (`Note: {título} \| Section: {header}`)                                               |
| `code.py`     | Chunks Python via `ast.parse()` (zero deps externas). Um chunk por função/método, um por classe (signature summary), um por módulo (imports + constants). Ficheiros `.md/.yaml/.toml/.sh` em repos são delegados ao markdown chunker com `source_type="repo_doc"` |

### Embeddings (`obsidian_rag/embeddings/`)

| Módulo      | Função                                                                                            |
| ----------- | ------------------------------------------------------------------------------------------------- |
| `ollama.py` | Batch via `POST /api/embed`. `get_query_embedding()` com `@lru_cache(128)` para queries repetidas |

### Store (`obsidian_rag/store/`)

| Módulo      | Função                                                                                                                                                                                      |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `chroma.py` | `PersistentClient` com `hnsw:space=cosine`. Sync incremental: calcula IDs existentes, apaga chunks stale, embeds e upserts em batches de 50. Duas coleções: `obsidian_vault` e `code_repos` |

### Retrieval (`obsidian_rag/retrieval/`)

| Módulo             | Função                                                                                                                                                       |
| ------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `rag.py`           | `build_rag_context()` — entry point. Multi-estratégia: vector + keyword + title. Deduplicação, threshold dinâmico, relevance gate                            |
| `router.py`        | `ContextMode` enum (NO_CONTEXT, RAG_ONLY, GRAPH_ONLY, RAG_AND_GRAPH, CLARIFY). LLM router (gemma3:4b) com keyword heuristic fallback                         |
| `intent.py`        | Mapeia `ContextMode` → `QueryIntent(use_notes, use_code, use_graph)`                                                                                         |
| `budget.py`        | Alocação de token budget: 40/40/20 (notas/código/grafo), trunca por chunks inteiros. Tokenizer regex word-boundary com multiplicador 1.3×                    |
| `reranker.py`      | Cross-encoder opcional via Ollama. Score 0-10, combina 60% reranker + 40% vector. Disabled por defeito                                                       |
| `graph_context.py` | Constrói bloco de contexto do grafo: nós, comunidades, vizinhos (calls, imports_from, uses), god nodes                                                       |
| `observe.py`       | `QueryTrace` — captura toda a cadeia de decisão: routing, retrieval, scoring, timing. `_JsonFormatter` para logging JSON estruturado (ficheiro e/ou consola) |

### Graph (`obsidian_rag/graph/`)

| Módulo               | Função                                                                                                                                    |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `builder.py`         | Wrapper para `graphify extract` via `subprocess.run`. Injeta `OLLAMA_BASE_URL` e `OLLAMA_API_KEY=ollama`                                  |
| `query.py`           | Leitura de `graph.json` (node-link) com NetworkX. `load_graph()`, `get_report()`, `list_repos()`, `get_neighbors()`, NL `query_graph()`   |
| `cache.py`           | Cache in-memory `_RepoGraphData` com file-stat invalidation (mtime + size) e TTL (300s). Indexa nós por `(source_file, normalized_label)` |
| `enrich.py`          | Community summaries via Ollama (deepseek-r1:8b/qwen3:8b), cross-community links, diagramas Mermaid, tag inference. Cache JSON local       |
| `obsidian_export.py` | Exporta grafos como notas Obsidian-compatible para `~/Obsidian/knowledge-graphs/`                                                         |

### API (`obsidian_rag/api/`)

| Módulo        | Função                                                                                                                                                |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| `app.py`      | FastAPI com `lifespan` (preload ChromaDB, httpx pool). Middleware de autenticação via API key (`Bearer`). Todos os endpoints REST + streaming `/chat` |
| `schemas.py`  | Modelos Pydantic: QueryRequest, ChatRequest, ChunkResult, RepoInfo, etc.                                                                              |
| `cli.py`      | `rag-query` — one-shot semantic query, output stdout                                                                                                  |
| `chat_cli.py` | `rag-chat` — REPL interativo com history, `--debug`, `--no-rag`, `--mode`                                                                             |

| Módulo      | Função                                                                                                                                      |
| ----------- | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `sync.py`   | CLI `rag-sync`. Três modos: `-l` (notas + repos), `-g` (graphify), `--all`. Sync paralelo de repos com `ThreadPoolExecutor` (max_workers=4) |
| `backup.py` | CLI `rag-backup`. Backup timestamped do ChromaDB (`shutil.copytree`) com rotação (mantém últimas 3 cópias)                                  |

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
| `GET`  | `/stats`                         | Estatísticas das coleções ChromaDB                                        | Sim\* |
| `POST` | `/query`                         | Pesquisa semântica nas notas (obsidian_vault)                             | Sim\* |
| `POST` | `/query/code`                    | Pesquisa semântica no código (code_repos). Filtros: `repo`, `symbol_type` | Sim\* |
| `GET`  | `/repos`                         | Lista repos configurados com stats de chunks e grafos                     | Sim\* |
| `GET`  | `/graph/{repo}`                  | Devolve o GRAPH_REPORT.md de um repo                                      | Sim\* |
| `POST` | `/graph/{repo}/query`            | Query em linguagem natural ao knowledge graph                             | Sim\* |
| `GET`  | `/graph/{repo}/neighbors/{node}` | Vizinhos de um nó no grafo                                                | Sim\* |
| `POST` | `/chat`                          | Chat RAG-augmented com streaming (proxy Ollama)                           | Sim\* |

_\*Apenas quando `api_key` está definido em `rag.toml` ou via `RAG_API_API_KEY`._

## CLI — Entry Points

| Comando      | Módulo                 | Descrição                                                                                |
| ------------ | ---------------------- | ---------------------------------------------------------------------------------------- |
| `rag-sync`   | `pipeline.sync:main`   | Sincronização: `-l` (embeddings, paralelo), `-g` (grafos), `--all`, `--force`            |
| `rag-serve`  | `api.app:serve`        | Inicia FastAPI em `127.0.0.1:8484` (configurável via `rag.toml`)                         |
| `rag-query`  | `api.cli:main`         | Query one-shot ao ChromaDB (stdout)                                                      |
| `rag-chat`   | `api.chat_cli:main`    | REPL interativo com debug, `--no-rag`, `--mode {auto\|rag_only\|graph_only\|both\|none}` |
| `rag-backup` | `pipeline.backup:main` | Backup timestamped do ChromaDB com rotação automática (mantém últimas 3 cópias)          |

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

| Pacote              | Versão  | Função                                            |
| ------------------- | ------- | ------------------------------------------------- |
| `chromadb`          | ≥ 0.5   | Base de dados vetorial persistente (HNSW, cosine) |
| `fastapi`           | ≥ 0.110 | Framework REST API                                |
| `uvicorn[standard]` | ≥ 0.29  | Servidor ASGI                                     |
| `httpx`             | ≥ 0.27  | Cliente HTTP assíncrono (Ollama)                  |
| `networkx`          | ≥ 3.0   | Leitura e query de grafos (graph.json)            |

### Desenvolvimento

| Pacote           | Versão | Função                           |
| ---------------- | ------ | -------------------------------- |
| `pytest`         | ≥ 8.0  | Framework de testes              |
| `pytest-asyncio` | ≥ 0.23 | Suporte async para testes pytest |
| `coverage`       | ≥ 7.0  | Cobertura de código              |

### Opcionais

| Pacote      | Função                                                              |
| ----------- | ------------------------------------------------------------------- |
| `graphifyy` | CLI `graphify extract` — construção de knowledge graphs (AST + LLM) |

### Stdlib utilizada

| Módulo                       | Função                                                   |
| ---------------------------- | -------------------------------------------------------- |
| `ast`                        | Parsing de código Python para chunking por função/classe |
| `tomllib`                    | Leitura do `rag.toml` (Python 3.11+)                     |
| `hashlib`                    | SHA256 para IDs de chunks (sync incremental)             |
| `functools.lru_cache`        | Cache de embeddings de queries                           |
| `secrets`                    | Comparação timing-safe de API keys (`compare_digest`)    |
| `re`                         | Tokenizer regex word-boundary (`budget.py`)              |
| `concurrent.futures`         | ThreadPoolExecutor para sync paralelo de repos           |
| `shutil`                     | Cópia de diretórios ChromaDB para backup                 |
| `json` / `logging.Formatter` | Logging estruturado JSON (`observe.py`)                  |

## Tecnologias usadas

| Tecnologia       | Contexto                                           |
| ---------------- | -------------------------------------------------- |
| **Python 3.11+** | Linguagem principal                                |
| **Ollama**       | Runtime local de LLMs e embeddings                 |
| **ChromaDB**     | Vector store persistente (HNSW, cosine similarity) |
| **FastAPI**      | API REST assíncrona                                |
| **NetworkX**     | Análise e query de grafos                          |
| **Graphify**     | Extração de knowledge graphs de repositórios       |
| **Pydantic**     | Validação de schemas (API requests/responses)      |
| **systemd**      | Timer para sync diário às 04:00                    |

## Como executar o projeto localmente

### Pré-requisitos

- Python ≥ 3.11
- Ollama instalado e a correr em `localhost:11434`
- Modelo `bge-m3` disponível (`ollama pull bge-m3`)
- Vault Obsidian em `~/Obsidian/Vault` (configurável em `rag.toml`)

### Instalação

```bash
# Instalar o package
pip install -e .

# Opcional: suporte a knowledge graphs
pip install graphifyy
# ou
pip install -e ".[graphify]"
```

### Uso

```bash
# Sincronizar notas + repos (embeddings incrementais, sync paralelo)
rag-sync -l

# Construir knowledge graphs (requer graphifyy)
rag-sync -g
rag-sync -g --force   # rebuild completo

# Sincronizar tudo
rag-sync --all

# Backup ChromaDB (com rotação automática, mantém últimas 3 cópias)
rag-backup

# Iniciar API
rag-serve              # FastAPI em 127.0.0.1:8484

# Query one-shot
rag-query "como funciona o chunking?"
rag-query -n 10 "configurar aliases zsh"

# Chat interativo
rag-chat
rag-chat -m deepseek-r1-pt --debug
rag-chat --no-rag
rag-chat --mode graph_only
```

### Environment overrides

Qualquer opção de `rag.toml` pode ser sobreposta via variável de ambiente `RAG_{SECÇÃO}_{CHAVE}`:

```bash
RAG_RETRIEVAL_TOP_K=15 rag-serve
RAG_GRAPHIFY_AUTO_UPDATE=true rag-sync -g
RAG_DEBUG_ENABLED=true rag-serve
RAG_API_PORT=9000 rag-serve
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

O `docker-compose.yml` monta `./data` como volume e configura `extra_hosts: host.docker.internal:host-gateway` para aceder ao Ollama do host. A imagem usa multi-stage build com `python:3.11-slim` para manter o tamanho reduzido.

## Como configurar o ambiente

### Ficheiro principal: `rag.toml`

| Secção             | Opções-chave                                                                                                       |
| ------------------ | ------------------------------------------------------------------------------------------------------------------ |
| `[paths]`          | `source_dir`, `data_dir`, `vault_dir`                                                                              |
| `[ollama]`         | `base_url`, `embedding_model`                                                                                      |
| `[chunking]`       | `max_chars=2000`, `overlap_chars=200`, `min_chars=50`, `contextual_prefix=true`                                    |
| `[retrieval]`      | `top_k=10`, `score_threshold=0.45`, `dynamic_threshold_ratio=0.75`, `token_budget=4000`, `context_mode=auto`       |
| `[api]`            | `host=127.0.0.1`, `port=8484`, `api_key=""` (vazio = sem auth; override: `RAG_API_API_KEY`)                        |
| `[models]`         | Per-model RAG toggle (ex: `"coder-pt" = false`)                                                                    |
| `[router]`         | `enabled=true`, `model=gemma3:4b`, `timeout=15.0`                                                                  |
| `[reranker]`       | `enabled=false`, `model=gemma3:4b`, `top_k_candidates=30`                                                          |
| `[context_policy]` | `min_relevance_score=0.50`, `min_relevant_chunks=1`                                                                |
| `[debug]`          | `enabled=false`, `log_to_file=false`, `log_level=INFO`, `log_format="text"` (ou `"json"` para logging estruturado) |
| `[repos]`          | `paths=[...]`, `collection_name=code_repos`                                                                        |
| `[pipeline]`       | `max_workers=4` — número de threads para sync paralelo de repos                                                    |
| `[graphify]`       | `enabled=true`, `backend=ollama`, `model=deepseek-r1:8b`, `output_dir=data/graphify`                               |

### Scheduler (systemd)

O sync é agendado como timer systemd do utilizador, executando diariamente às 04:00.

## Como testar funcionalidades

### Testes manuais

```bash
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
rag-chat --debug -m qwen3-pt
```

### Testes automatizados

```bash
# Executar todos os testes
pytest

# Com cobertura
coverage run -m pytest && coverage report

# Testes de um módulo específico
pytest tests/test_chunking_markdown.py
pytest tests/test_api.py -v
```

**91 testes** em 6 ficheiros, sem dependências externas (Ollama, ChromaDB):

| Ficheiro                    | Testes | Cobertura                                                                                          |
| --------------------------- | ------ | -------------------------------------------------------------------------------------------------- |
| `test_chunking_markdown.py` | 17     | `_compute_hash`, `_strip_frontmatter`, `_is_navigation_content`, `_split_by_headers`, `chunk_note` |
| `test_chunking_code.py`     | 13     | `_split_if_long`, `_build_chunk`, `_chunk_python_source`, `_chunk_text_fallback`                   |
| `test_router.py`            | 13     | `_heuristic_route` com queries PT/EN, sinais de grafo/locais, edge cases                           |
| `test_budget.py`            | 16     | `estimate_tokens`, `allocate_budget`, `truncate_chunks`, `truncate_text`                           |
| `test_api.py`               | 7      | `/health`, middleware de auth (401 missing/wrong key, pass com key correcta)                       |
| `test_medium_features.py`   | 25     | Backup, sync paralelo, logging JSON, tokenizer regex, configurações pipeline/debug                 |

Fixtures partilhadas em `conftest.py`: `tmp_source_dir`, `sample_markdown_note`, `navigation_note`, `sample_python_source`.

## Limitações conhecidas

| Limitação                         | Descrição                                                                                                    |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| **Cobertura de testes parcial**   | 91 unit tests cobrindo chunking, router, budget, API auth e funcionalidades médias. Faltam integration tests |
| **Chunking AST só para Python**   | Repositórios com outras linguagens usam fallback textual (menos preciso)                                     |
| **Reranker disabled por defeito** | Adicionaria latência mas melhoraria precisão. Desativado por performance                                     |
| **Auth opcional na API**          | API key auth disponível (`Bearer`) mas desativada por defeito (campo `api_key` vazio)                        |
| **Graphify depende de LLM**       | A extração semântica de grafos requer chamadas ao Ollama, que pode ser lento                                 |
| **Single-user**                   | A arquitetura não suporta múltiplos utilizadores concorrentes de forma otimizada                             |
| **Stop words apenas em PT**       | A lista de stop words para keyword search é apenas em português                                              |

## Estado atual do projeto

| Aspeto               | Estado                                                                                                         |
| -------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Versão**           | 0.3.1                                                                                                          |
| **Maturidade**       | Funcional para uso pessoal. Containerizado com Docker. Não é production-ready para deployment multi-utilizador |
| **Pipeline RAG**     | Completo e funcional: chunking → embeddings → ChromaDB → retrieval multi-estratégia. Sync paralelo de repos    |
| **Knowledge graphs** | Funcional com Graphify. Enrichment com community summaries, Mermaid e export Obsidian                          |
| **API**              | 9 endpoints REST funcionais + streaming chat                                                                   |
| **CLI**              | 5 entry points (sync, serve, query, chat, backup) + helpers zsh                                                |
| **Router**           | LLM (gemma3:4b) + keyword heuristic fallback — funcional                                                       |
| **Reranker**         | Implementado mas desativado por defeito                                                                        |
| **Observabilidade**  | `QueryTrace` com decisões completas. Logging JSON estruturado (ficheiro/consola). Debug mode via `--debug`     |
| **Backup**           | `rag-backup` — backup timestamped do ChromaDB com rotação automática (3 cópias)                                |
| **Docker**           | `Dockerfile` multi-stage + `docker-compose.yml`. Porta 8000, volume `data/`, rede host Ollama                  |
| **Documentação**     | Este ficheiro + `IMPROVEMENTS_AND_RISKS.md`                                                                    |
| **Testes**           | 91 unit tests (pytest) — chunking, router, budget, API auth, medium features. Todos passam em <1s              |

---

## Regra de manutenção da documentação

> **Sempre que qualquer alteração for feita ao projeto** — código, configuração, modelos, prompts, arquitetura, dependências, novo agente, nova funcionalidade — **este documento e `docs/IMPROVEMENTS_AND_RISKS.md` devem ser atualizados obrigatoriamente.**
>
> Uma tarefa só é considerada concluída quando a documentação relevante tiver sido revista e atualizada.
