# Obsidian RAG — Pipeline Local v0.5.3

> **Pipeline de RAG 100% local e privado.**
> Indexa o teu Vault Obsidian e repositórios Git numa base de dados vetorial, expõe uma API REST local e funciona como proxy inteligente para o Ollama — injetando contexto relevante nas respostas do LLM apenas quando necessário. **Nenhum dado sai da tua máquina.**

---

## Instalação Rápida

```bash
# Linux / macOS
git clone https://github.com/PedroMglo/local-ai-sys.git obsidian-rag
cd obsidian-rag
./install.sh
rag init
rag up
```

```powershell
# Windows (PowerShell)
git clone https://github.com/PedroMglo/local-ai-sys.git obsidian-rag
cd obsidian-rag
.\install.ps1
rag init
rag up
```

**Pré-requisitos:** Python 3.11+, Git, Docker (para Qdrant server mode), [Ollama](https://ollama.com) com `ollama pull bge-m3`.
**Plataformas:** Linux, macOS, Windows (nativo ou WSL2).

---

## O que é

| Problema                                                     | Solução                                                 |
| ------------------------------------------------------------ | ------------------------------------------------------- |
| Notas Obsidian e código Git isolados, sem pesquisa semântica | Indexa tudo em Qdrant com embeddings `bge-m3`           |
| LLMs genéricos não conhecem os teus projectos e notas        | Proxy RAG injeta contexto local relevante em cada query |
| Soluções cloud enviam dados para fora                        | 100% local — Ollama + Qdrant + FastAPI                  |

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

| Comando                   | Descrição                                                  |
| ------------------------- | ---------------------------------------------------------- |
| `rag init`                | Configuração interactiva (gera `rag.toml`)                 |
| `rag up`                  | Verificar sistema e iniciar API                            |
| `rag doctor`              | Diagnóstico completo com ✓/✗                               |
| `rag sync -l`             | Sync embeddings (notas + repos, incremental)               |
| `rag sync -g`             | Sync grafos Graphify                                       |
| `rag sync --all`          | Tudo: embeddings + grafos                                  |
| `rag sync --all --force`  | Rebuild completo forçado (ignora manifesto/cache)          |
| `rag serve`               | Iniciar API REST (porta 8484)                              |
| `rag query "texto"`       | Pesquisa semântica nas notas                               |
| `rag query -n 10 "texto"` | Pesquisa com N resultados                                  |
| `rag chat`                | REPL interativo com RAG                                    |
| `rag chat --debug`        | Chat com info de routing                                   |
| `rag backup`              | Backup timestamped do Qdrant                               |
| `rag schedule install`    | Instalar sync automático diário (systemd/launchd/schtasks) |
| `rag schedule remove`     | Remover sync automático                                    |
| `rag schedule status`     | Estado do agendamento                                      |
| `rag graph build`         | Construir knowledge graphs                                 |
| `rag graph build --force` | Rebuild completo dos grafos                                |
| `rag graph status`        | Estado dos grafos por repo                                 |

**Makefile** disponível com atalhos: `make install`, `make up`, `make sync`, `make doctor`, `make test`, `make qdrant`, `make qdrant-down`.

---

## Configuração (`rag.toml`)

O `rag init` cria a configuração interactivamente. Para editar manualmente:

```toml
[paths]
source_dir  = "source"                    # staging dir (usado quando sync.backend ≠ direct)
data_dir    = "data/qdrant"               # Qdrant embedded (ignorado em server mode)
vault_dirs  = ["~/Obsidian/Vault"]        # multi-vault (lista de paths)

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

[sync]
backend          = "direct" # direct | python | rsync | auto
delete_missing   = true     # remover ficheiros apagados no vault
follow_symlinks  = false
# exclude_patterns = [".obsidian", ".trash", ".git", ".DS_Store"]

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

[store]
backend    = "qdrant"
qdrant_url = "http://localhost:6333"  # vazio = embedded local

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

| Método | Endpoint                         | Descrição                            |
| ------ | -------------------------------- | ------------------------------------ |
| `GET`  | `/health`                        | Health check + versão                |
| `GET`  | `/stats`                         | Estatísticas (chunks notas + código) |
| `POST` | `/query`                         | Pesquisa semântica nas notas         |
| `POST` | `/query/code`                    | Pesquisa semântica no código         |
| `GET`  | `/repos`                         | Lista repos configurados + stats     |
| `GET`  | `/graph/{repo}`                  | GRAPH_REPORT.md de um repo           |
| `POST` | `/graph/{repo}/query`            | Query ao grafo em linguagem natural  |
| `GET`  | `/graph/{repo}/neighbors/{node}` | Vizinhos de um nó                    |
| `POST` | `/chat`                          | Chat RAG-augmented com streaming     |

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

## Docker / Qdrant Server Mode

Para concorrência real (múltiplos modelos a fazer queries RAG simultaneamente), usa o Qdrant em **server mode** via Docker:

```bash
# Arrancar Qdrant server (persiste entre reboots — restart: unless-stopped)
make qdrant
# equivalente a: docker compose --profile qdrant up -d

# Verificar healthcheck
curl -s http://localhost:6333/healthz

# Parar
make qdrant-down
```

Configura `qdrant_url = "http://localhost:6333"` em `rag.toml` — todos os comandos (`rag sync`, `rag serve`, `rag query`) passam a usar o server automaticamente.

**Rollback para embedded:** basta limpar o campo:
```toml
qdrant_url = ""  # volta ao modo embedded local
```

**Tuning de memória** (já configurado no `docker-compose.yml`):
- `mem_limit: 512m` — cap duro de RAM
- `QDRANT__STORAGE__ON_DISK_PAYLOAD=true` — metadata em disco
- `QDRANT__STORAGE__MMAP_THRESHOLD_KB=20480` — índice via mmap em idle

O Ollama deve correr no host. O container acede-lhe via `host.docker.internal:11434`.

---

## Segurança

- **Bind local:** API em `127.0.0.1` por defeito — recusa `0.0.0.0` sem `api_key`
- **Autenticação:** Bearer token via `api_key` em `rag.toml` (timing-safe)
- **Rate limiting:** configurável por minuto (global + `/chat`)
- **Validação de input:** Pydantic com limites em todos os endpoints
- **Paths seguros:** `rag init` recusa indexar `/`, `~`, `.ssh`, `.gnupg` e dirs de sistema (cross-platform)
- **Exclusões automáticas:** `.git`, `.venv`, `node_modules`, `__pycache__`, `.obsidian`, `.DS_Store`, binários
- **Sem telemetria:** Qdrant opera localmente sem telemetria externa
- **Sem dados externos:** todo o processamento é local (Ollama + AST stdlib)

---

## Troubleshooting

```bash
rag doctor
```

Verifica: Python, virtualenv, dependências, `rag.toml`, paths, Ollama, modelos, Qdrant, permissões, Graphify.

---

## CI/CD e validação multiplataforma

O projecto é automaticamente testado em cada PR e push para `main` via GitHub Actions:

| Plataforma | Python     | Testes | CLI | Lint |
| ---------- | ---------- | ------ | --- | ---- |
| Ubuntu     | 3.11, 3.12 | ✓      | ✓   | ✓    |
| macOS      | 3.11, 3.12 | ✓      | ✓   | —    |
| Windows    | 3.11, 3.12 | ✓      | ✓   | —    |

**Sem dependências externas em CI:** nenhum teste requer Ollama, modelos, GPU ou rsync.

**Workflows:**

- `ci.yml` — lint, testes com coverage, CLI smoke, config/vault_sync tests, auditoria de segurança, **test-server-mode** (Qdrant service container + testes de concorrência)
- `docker.yml` — Docker build + compose config + sanity check
- `release.yml` — build wheel/sdist + GitHub Release (em tags `v*`)

**Correr localmente:**

```bash
pip install -e ".[dev]"

# Tudo de uma vez
make ci

# Ou individualmente
make lint          # ruff check
make typecheck     # mypy
make test-cov      # pytest + coverage

# Docker / Qdrant
make docker-build  # docker build
make docker-check  # docker compose config
make qdrant        # arrancar Qdrant server
make qdrant-down   # parar Qdrant server

# Testes de concorrência (requer Qdrant server activo)
QDRANT_TEST_URL=http://localhost:6333 pytest tests/test_concurrency.py -v
```

---

<details>
<summary><strong>Detalhes por plataforma</strong></summary>

### Linux

```bash
./install.sh && rag init && rag up
```

**Sync automático:**

```bash
rag schedule install   # cria systemd user timer (daily 04:00)
rag schedule status
rag schedule remove
```

Ou manualmente via systemd — ver `rag schedule install` para os ficheiros gerados.

### macOS

```bash
./install.sh && rag init && rag up
```

`rag init` detecta automaticamente vaults em `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/`.

**Sync automático:** `rag schedule install` cria um plist LaunchAgent.

### Windows

```powershell
.\install.ps1
rag init
rag up
```

`rag init` detecta vaults em `~/Documents/` e repos em `~/source/repos/`.

**Sync automático:** `rag schedule install` cria uma tarefa no Task Scheduler.

No `rag.toml`, usar barras normais: `vault_dir = "C:/Users/nome/Obsidian/Vault"`.

**Alternativa:** WSL2 (`wsl --install -d Ubuntu`) e seguir instruções Linux.

</details>

---

## Arquitectura

```
Obsidian Vault ──sync──► [source/ ou leitura directa]
        (direct|python|rsync|auto)
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
                    ┌─────────────────────────────┐
                    │          Qdrant              │
                    │  embedded: data/qdrant/      │
                    │  server:   Docker :6333      │ ← recomendado para concorrência
                    ├─────────────────────────────┤
                    │ obsidian_vault               │ ← notas
                    │ code_repos                  │ ← código
                    └──────────┬──────────────────┘
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

| Componente      | Tecnologia                                                                              |
| --------------- | --------------------------------------------------------------------------------------- |
| Embeddings      | Ollama `bge-m3` (multilíngue, 1024d, local)                                             |
| Vector Store    | Qdrant — embedded (single-user) ou server mode Docker (concorrência multi-modelo)       |
| Vault Sync      | direct (leitura in-place) / python (incremental) / rsync (Linux/macOS)                 |
| Code Chunking   | `ast.parse()` stdlib — zero dependências externas                                       |
| Knowledge Graph | Graphify com backend Ollama (opt-in)                                                    |
| API             | FastAPI + uvicorn — singleton `get_store()` thread-safe, retry com exponential backoff  |
| Graph Query     | NetworkX (leitura local de `graph.json`)                                                |
