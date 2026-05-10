# Obsidian RAG — Pipeline Local v0.3.0

Pipeline de RAG (Retrieval-Augmented Generation) que transforma o Vault Obsidian **e repositórios Git** em embeddings pesquisáveis via API REST local. Integra opcionalmente o Graphify para navegação estrutural de código via knowledge graph.

## Arquitetura (DAG)

```
Obsidian Vault ──rsync──► source/
                                │
                         Chunking (Markdown)
                                │
                                ▼
Git Repos ──────────────► Chunking (AST Python)
                                │
                                ▼
                         Embeddings (Ollama bge-m3)
                                │
                                ▼
                    ChromaDB ──────────────────────────────► API REST :8484
                    ├── obsidian_vault (notas)               ├── POST /query
                    └── code_repos    (código)               ├── POST /query/code
                                                             ├── GET  /repos
                                                             ├── GET  /graph/{repo}
                                                             └── POST /chat (RAG proxy Ollama)

Git Repos ──────────────► Graphify extract ──► graph.json ──► GET /graph/{repo}/query
                          (AST local + Ollama)               GET /graph/{repo}/neighbors/{node}
```

## Stack

| Componente      | Tecnologia                                             |
| --------------- | ------------------------------------------------------ |
| Embeddings      | Ollama `bge-m3` (multilíngue, local)                   |
| Vector Store    | ChromaDB persistente (2 coleções: notas + código)      |
| Code Chunking   | `ast.parse()` stdlib — chunks por função/classe/módulo |
| Knowledge Graph | Graphify v7 com backend Ollama (opt-in)                |
| API             | FastAPI + uvicorn                                      |
| Graph Query     | NetworkX (leitura local de graph.json)                 |
| Scheduler       | systemd user timer (diário 04:00)                      |

## Comandos

| Comando                   | Descrição                                              |
| ------------------------- | ------------------------------------------------------ |
| `rag-sync -l`             | Embeddings: notas Obsidian + repos Git (só deltas)     |
| `rag-sync -g`             | Grafos Graphify para repos sem grafo ou desatualizados |
| `rag-sync --all`          | Tudo: embeddings + grafos (`-l` + `-g`)                |
| `rag-serve`               | Iniciar API REST (porta 8484)                          |
| `rag-query "texto"`       | Query semântica (notas + código)                       |
| `rag-query -n 10 "texto"` | Query com N resultados                                 |

## API Endpoints

| Método | Endpoint                         | Descrição                              |
| ------ | -------------------------------- | -------------------------------------- |
| `GET`  | `/health`                        | Health check + versão                  |
| `GET`  | `/stats`                         | Estatísticas (chunks notas + código)   |
| `POST` | `/query`                         | Busca semântica nas notas Obsidian     |
| `POST` | `/query/code`                    | Busca semântica no código dos repos    |
| `GET`  | `/repos`                         | Lista repos configurados + stats grafo |
| `GET`  | `/graph/{repo}`                  | GRAPH_REPORT.md de um repo             |
| `POST` | `/graph/{repo}/query`            | Query em linguagem natural ao grafo    |
| `GET`  | `/graph/{repo}/neighbors/{node}` | Vizinhos de um nó no grafo             |
| `POST` | `/chat`                          | Chat RAG-augmented proxy → Ollama      |

### Exemplos

```bash
# Query de notas
curl -s http://localhost:8484/query \
  -H "Content-Type: application/json" \
  -d '{"query": "como configurar aliases no zsh", "top_k": 5}'

# Query de código
curl -s http://localhost:8484/query/code \
  -H "Content-Type: application/json" \
  -d '{"query": "segment_window chunking strategy", "repo": "SPEECH-LAB"}'

# Stats (notas + código)
curl -s http://localhost:8484/stats

# Repos e status do grafo
curl -s http://localhost:8484/repos

# Relatório do grafo
curl -s http://localhost:8484/graph/SPEECH-LAB

# Query ao grafo
curl -s http://localhost:8484/graph/SPEECH-LAB/query \
  -H "Content-Type: application/json" \
  -d '{"query": "como o transcriber liga ao postprocess?"}'

# Vizinhos de um nó
curl -s http://localhost:8484/graph/SPEECH-LAB/neighbors/ChunkBuilder
```

## Configuração (`rag.toml`)

```toml
[paths]
source_dir = "source"          # notas Obsidian
data_dir = "data/chroma"       # ChromaDB
vault_dir = "~/Obsidian/Vault"

[ollama]
base_url = "http://localhost:11434"
embedding_model = "bge-m3"

[chunking]                     # notas Markdown
max_chars = 2000
min_chars = 50
contextual_prefix = true

[repos]                        # repositórios Git
paths = ["~/ai-local/SPEECH-LAB"]
collection_name = "code_repos"

[repos.chunking]               # chunking de código Python
strategy = "ast"               # ast.parse() — função/classe/módulo
max_chars = 2000
min_chars = 80

[graphify]                     # knowledge graph (opt-in)
enabled = true
backend = "ollama"             # local, sem API key
output_dir = "data/graphify"
auto_update = false            # true = rebuild incremental em cada sync
token_budget = 30000
max_concurrency = 2

[retrieval]
top_k = 10
score_threshold = 0.45
dynamic_threshold_ratio = 0.75

[models]                       # per-model RAG toggle
"qwen3-pt" = true
"deepseek-r1-pt" = true
"coder-pt" = false
```

### Env var overrides

Qualquer valor pode ser sobreposto via env: `RAG_{SECÇÃO}_{CHAVE}`

```bash
RAG_REPOS_COLLECTION_NAME=test_code rag-sync -l
RAG_GRAPHIFY_AUTO_UPDATE=true rag-sync -g
RAG_RETRIEVAL_TOP_K=15 rag-serve
```

## Indexação de Repositórios Git

O chunker de código (`obsidian_rag/chunking/code.py`) usa `ast.parse()` — stdlib Python, zero dependências externas:

| Tipo de símbolo               | Chunk gerado                                                     |
| ----------------------------- | ---------------------------------------------------------------- |
| Função/método                 | decorators + docstring + corpo completo                          |
| Classe                        | sumário (docstring + assinaturas de métodos) + chunks por método |
| Módulo-level                  | imports + constants + module docstring                           |
| Docs no repo (`.md`, `.yaml`) | chunker Markdown com `source_type="repo_doc"`                    |

**Ignorados automaticamente**: `.git/`, `__pycache__/`, `logs/`, `models/`, `output/`, `.pyc`, imagens, binários.

**Sync incremental**: só re-embede chunks cujo conteúdo mudou (hash SHA256 do texto). Segunda execução não reprocessa código inalterado.

## Integração Graphify (opt-in)

```bash
# Instalar
pip install graphifyy
# ou com o extra incluído:
pip install -e ".[graphify]"
```

O Graphify cria um knowledge graph estrutural do repo (relações entre módulos, funções, classes):

```
data/graphify/SPEECH-LAB/graphify-out/
├── graph.json        # grafo completo (NetworkX node-link format)
├── GRAPH_REPORT.md   # god nodes, conexões surpreendentes, questões sugeridas
└── cache/            # cache SHA256 por ficheiro (rebuild incremental)
```

- **Código Python**: processado localmente via AST/tree-sitter (sem LLM, sem tokens)
- **Markdown/docs**: extraídos via Ollama (local, sem API key externa)
- **Rebuild incremental**: `auto_update = true` → só re-extrai ficheiros alterados

## Coleções ChromaDB

| Coleção          | Fonte                     | Metadata chave                               |
| ---------------- | ------------------------- | -------------------------------------------- |
| `obsidian_vault` | Notas Markdown            | `note_title`, `section_header`               |
| `code_repos`     | Código Python + docs repo | `repo_name`, `symbol_type`, `section_header` |

As coleções são independentes. O retrieval pesquisa ambas e devolve contexto separado ao LLM:

```
[CONTEXTO DAS NOTAS PESSOAIS]  ← notas Obsidian
...
[CONTEXTO DO CÓDIGO — SPEECH-LAB]  ← código do repo
...
```

## Retrieval — 4 Estratégias

1. **Primary** — vector search na query original (notas)
2. **Secondary** — variante keyword-only (ângulo de embedding diferente)
3. **Tertiary** — fetch directo por `note_title` para triggers de inventário
4. **Quaternary** — vector search na coleção de código (`code_repos`)

Dynamic threshold: `max(score_threshold, best_score × 0.75)` — auto-ajusta por dificuldade da query.

## Estrutura do Projecto

```
obsidian-rag/
├── rag.toml                         # Configuração central
├── obsidian_rag/
│   ├── config.py                    # Settings singleton (dataclasses)
│   ├── chunking/
│   │   ├── markdown.py              # Chunker Markdown (headers)
│   │   └── code.py                  # Chunker Python (ast.parse)
│   ├── embeddings/
│   │   └── ollama.py                # Embeddings via Ollama API
│   ├── store/
│   │   └── chroma.py                # ChromaDB multi-coleção
│   ├── pipeline/
│   │   └── sync.py                  # Orquestrador: notas + repos + graphify
│   ├── retrieval/
│   │   └── rag.py                   # Multi-strategy retrieval
│   ├── graph/
│   │   ├── builder.py               # Wrapper graphify CLI
│   │   └── query.py                 # NetworkX graph queries
│   └── api/
│       ├── app.py                   # FastAPI endpoints
│       ├── schemas.py               # Pydantic models
│       └── cli.py                   # CLI rag-query
├── source/                          # Notas Obsidian (rsync)
├── data/
│   ├── chroma/                      # ChromaDB storage
│   └── graphify/                    # Grafos por repo
└── requirements.txt
```

## Setup (já feito)

```bash
cd ~/ai-local/obsidian-rag
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

# Opcional — Graphify
pip install graphifyy

# Ativar services
systemctl --user daemon-reload
systemctl --user enable --now obsidian-rag-api.service
systemctl --user enable --now obsidian-rag-sync.timer
```

## Systemd Services

```bash
systemctl --user status obsidian-rag-api
systemctl --user restart obsidian-rag-api
systemctl --user start obsidian-rag-sync      # sync manual
journalctl --user -u obsidian-rag-api -f
journalctl --user -u obsidian-rag-sync --since today
```

## Notas Técnicas

- **Incremental**: só processa chunks cujo conteúdo mudou (hash SHA256)
- **Chunking Markdown**: divide por headers H1/H2/H3, max 2000 chars, overlap 200
- **Chunking código**: ast.parse() — função/classe/módulo; fallback texto para parse failures
- **Graphify**: código Python processado 100% local (AST); docs via Ollama
- **Performance**: ~37 chunks/s no embedding, queries <200ms
