# Obsidian RAG — Pipeline Local v0.4.0

> **Pipeline de RAG 100% local e privado.**  
> Indexa o teu Vault Obsidian e repositórios Git numa base de dados vetorial, expõe uma API REST local e funciona como proxy inteligente para o Ollama — injetando contexto relevante nas respostas do LLM apenas quando necessário. **Nenhum dado sai da tua máquina.**

---

## Instalação Rápida

```bash
git clone https://github.com/PedroMglo/local-ai-sys.git obsidian-rag
cd obsidian-rag
./install.sh
rag init
rag up
```

**Pré-requisitos:** Python 3.11+, Git, [Ollama](https://ollama.com) com `ollama pull bge-m3`.

---

## O que é

| Problema | Solução |
|---|---|
| Notas Obsidian e código Git isolados, sem pesquisa semântica | Indexa tudo em ChromaDB com embeddings `bge-m3` |
| LLMs genéricos não conhecem os teus projectos e notas | Proxy RAG injeta contexto local relevante em cada query |
| Soluções cloud enviam dados para fora | 100% local — Ollama + ChromaDB + FastAPI |

---

## Primeiro Uso

```bash
# Sincronizar notas e código
rag sync --all

# Pesquisa semântica
rag query "como configurar aliases no zsh"

# Chat interactivo com RAG
rag chat

# Diagnóstico do sistema
rag doctor
```

---

## Comandos

| Comando | Descrição |
|---|---|
| `rag init` | Configuração interactiva (gera `rag.toml`) |
| `rag up` | Verificar sistema e iniciar API |
| `rag doctor` | Diagnóstico completo com ✓/✗ |
| `rag sync -l` | Sync embeddings (notas + repos, incremental) |
| `rag sync -g` | Sync grafos Graphify |
| `rag sync --all` | Tudo: embeddings + grafos |
| `rag serve` | Iniciar API REST (porta 8484) |
| `rag query "texto"` | Pesquisa semântica nas notas |
| `rag query -n 10 "texto"` | Pesquisa com N resultados |
| `rag chat` | REPL interativo com RAG |
| `rag chat --debug` | Chat com info de routing |
| `rag backup` | Backup timestamped do ChromaDB |
| `rag graph build` | Construir knowledge graphs |
| `rag graph build --force` | Rebuild completo dos grafos |
| `rag graph status` | Estado dos grafos por repo |

**Makefile** disponível com atalhos: `make install`, `make up`, `make sync`, `make doctor`, `make test`.

---

## Configuração (`rag.toml`)

O `rag init` cria a configuração interactivamente. Para editar manualmente:

```toml
[paths]
source_dir = "source"           # notas copiadas do Vault
data_dir   = "data/chroma"      # ChromaDB persistente
vault_dir  = "~/Obsidian/Vault" # caminho do teu Vault

[ollama]
base_url        = "http://localhost:11434"
embedding_model = "bge-m3"

[chunking]
max_chars        = 2000
min_chars        = 50
contextual_prefix = true

[repos]
paths            = ["~/ai-local/SPEECH-LAB"]  # repos Git a indexar
collection_name  = "code_repos"

[repos.chunking]
strategy         = "ast"    # ast | text
max_chars        = 2000

[retrieval]
top_k            = 10
score_threshold  = 0.45
context_mode     = "auto"   # auto | rag_only | graph_only | both | none
token_budget     = 4000

[api]
host = "127.0.0.1"     # NUNCA usar 0.0.0.0 sem api_key
port = 8484
api_key = ""            # vazio = sem autenticação

[models]                # RAG por modelo (nome do modelo Ollama)
"qwen3:8b" = true
"deepseek-r1:8b" = true
"qwen2.5-coder" = false # sem RAG para código puro

[graphify]
enabled = false         # opt-in: corre com "rag graph build"
backend = "ollama"
```

**Override por variável de ambiente:**

```bash
RAG_RETRIEVAL_TOP_K=15 rag serve
RAG_API_API_KEY=minha-chave rag serve
```

---

## Graphify — Knowledge Graph

O Graphify analisa repositórios Git e cria um grafo estrutural de relações entre módulos, funções e classes. Está **instalado por defeito** mas só executa quando pedido.

```bash
# Construir grafos para todos os repos
rag graph build

# Forçar rebuild completo
rag graph build --force

# Repo específico
rag graph build --repo SPEECH-LAB

# Ver estado
rag graph status

# Consultar via API
curl -s http://localhost:8484/graph/SPEECH-LAB
curl -s http://localhost:8484/graph/SPEECH-LAB/neighbors/ChunkBuilder
```

**Processamento:** código Python via AST local (sem LLM); docs Markdown via Ollama local. Nenhum dado enviado para fora.

---

## API REST

| Método | Endpoint | Descrição |
|---|---|---|
| `GET` | `/health` | Health check + versão |
| `GET` | `/stats` | Estatísticas (chunks notas + código) |
| `POST` | `/query` | Pesquisa semântica nas notas |
| `POST` | `/query/code` | Pesquisa semântica no código |
| `GET` | `/repos` | Lista repos configurados + stats |
| `GET` | `/graph/{repo}` | GRAPH_REPORT.md de um repo |
| `POST` | `/graph/{repo}/query` | Query ao grafo em linguagem natural |
| `GET` | `/graph/{repo}/neighbors/{node}` | Vizinhos de um nó |
| `POST` | `/chat` | Chat RAG-augmented com streaming |

**Exemplos:**

```bash
curl http://localhost:8484/health

curl -s http://localhost:8484/query \
  -H "Content-Type: application/json" \
  -d '{"query": "como configurar aliases no zsh", "top_k": 5}'

curl -s http://localhost:8484/chat \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen3:8b", "messages": [{"role": "user", "content": "Explica o chunking"}]}'
```

---

## Docker

```bash
docker compose up -d
docker compose logs -f obsidian-rag
```

O Ollama deve correr no host. O container acede-lhe via `host.docker.internal:11434`.

---

## Segurança

- **Bind local:** API em `127.0.0.1` por defeito — recusa `0.0.0.0` sem `api_key`
- **Autenticação:** Bearer token via `api_key` em `rag.toml` (timing-safe)
- **Rate limiting:** configurável por minuto (global + `/chat`)
- **Validação de input:** Pydantic com limites em todos os endpoints
- **Paths seguros:** `rag init` recusa indexar `/`, `~`, `.ssh`, `.gnupg`
- **Exclusões automáticas:** `.git`, `.venv`, `node_modules`, `__pycache__`, binários
- **Sem telemetria:** ChromaDB com `anonymized_telemetry=False`
- **Sem dados externos:** todo o processamento é local (Ollama + AST stdlib)

---

## Troubleshooting

```bash
rag doctor
```

Verifica: Python, virtualenv, dependências, `rag.toml`, paths, Ollama, modelos, ChromaDB, permissões, Graphify.

---

<details>
<summary><strong>Detalhes por plataforma</strong></summary>

### Linux

```bash
git clone https://github.com/PedroMglo/local-ai-sys.git obsidian-rag
cd obsidian-rag
./install.sh
rag init
rag up
```

**Systemd (serviço automático):**

```ini
# ~/.config/systemd/user/obsidian-rag-api.service
[Unit]
Description=Obsidian RAG API
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/ai-local/obsidian-rag
ExecStart=%h/ai-local/obsidian-rag/.venv/bin/rag serve
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

```ini
# ~/.config/systemd/user/obsidian-rag-sync.service
[Unit]
Description=Obsidian RAG sync

[Service]
Type=oneshot
WorkingDirectory=%h/ai-local/obsidian-rag
ExecStart=%h/ai-local/obsidian-rag/.venv/bin/rag sync --all
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now obsidian-rag-api.service
```

### macOS

Processo idêntico ao Linux. Usa `launchd` em vez de systemd para serviço automático.

### Windows

**Recomendado:** WSL2 (`wsl --install -d Ubuntu`) e seguir instruções Linux.

**Nativo:** `python -m venv .venv && .venv\Scripts\activate && pip install -e .`

No `rag.toml`, usar barras normais: `vault_dir = "C:/Users/nome/Obsidian/Vault"`.

</details>

---

## Arquitectura

```
Obsidian Vault ──rsync──► source/
                               │
                        Chunking (Markdown)    ←── headers H1/H2/H3
                               │
                               ▼
Git Repos ──────────────► Chunking (AST Python) ←── função/classe/módulo
                               │
                               ▼
                        Embeddings (Ollama bge-m3, 1024d, cosine)
                               │
                               ▼
                    ┌─────────────────────┐
                    │      ChromaDB       │  (persistente em data/chroma/)
                    ├─────────────────────┤
                    │ obsidian_vault      │ ← notas
                    │ code_repos          │ ← código
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  FastAPI :8484      │
                    │  (127.0.0.1)        │
                    ├─────────────────────┤
                    │ /query              │ pesquisa notas
                    │ /query/code         │ pesquisa código
                    │ /chat               │ RAG-augmented proxy
                    │ /graph/{repo}       │ knowledge graph
                    └─────────────────────┘
```

| Componente | Tecnologia |
|---|---|
| Embeddings | Ollama `bge-m3` (multilíngue, 1024d, local) |
| Vector Store | ChromaDB persistente (cosine similarity) |
| Code Chunking | `ast.parse()` stdlib — zero dependências externas |
| Knowledge Graph | Graphify com backend Ollama (opt-in) |
| API | FastAPI + uvicorn |
| Graph Query | NetworkX (leitura local de `graph.json`) |
