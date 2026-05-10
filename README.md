# Obsidian RAG — Pipeline Local v0.3.0

> **Pipeline de RAG (Retrieval-Augmented Generation) 100% local e privado.**  
> Indexa o teu Vault Obsidian e repositórios Git numa base de dados vetorial, expõe uma API REST local e funciona como proxy inteligente para o Ollama — injetando contexto relevante nas respostas do LLM apenas quando necessário. **Nenhum dado sai da tua máquina.**

---

## Índice

- [O que é](#o-que-é)
- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
  - [Linux](#linux)
  - [macOS](#macos)
  - [Windows](#windows)
- [Configuração](#configuração-ragtoml)
- [Primeiro Uso](#primeiro-uso)
- [Comandos CLI](#comandos-cli)
- [API REST](#api-rest)
- [Docker (todas as plataformas)](#docker-todas-as-plataformas)
- [Graphify — Knowledge Graph (opt-in)](#graphify--knowledge-graph-opt-in)
- [Arquitetura](#arquitetura)

---

## O que é

O **obsidian-rag** resolve três problemas:

| Problema                                                     | Solução                                                 |
| ------------------------------------------------------------ | ------------------------------------------------------- |
| Notas Obsidian e código Git isolados, sem pesquisa semântica | Indexa tudo em ChromaDB com embeddings `bge-m3`         |
| LLMs genéricos não conhecem os teus projectos e notas        | Proxy RAG injeta contexto local relevante em cada query |
| Soluções cloud enviam dados para fora                        | 100% local — Ollama + ChromaDB + FastAPI na tua máquina |

**Casos de uso:**

- Pesquisa semântica nas notas Obsidian ("encontra tudo sobre X")
- Pesquisa de código por intenção ("onde está a lógica de chunking?")
- Chat com LLM local enriquecido com contexto dos teus projectos
- Exploração estrutural de código via knowledge graph (Graphify)

---

## Pré-requisitos

Necessário em **todas as plataformas**:

| Requisito  | Versão mínima | Notas                                                     |
| ---------- | ------------- | --------------------------------------------------------- |
| **Python** | 3.11+         | [python.org/downloads](https://www.python.org/downloads/) |
| **Ollama** | qualquer      | [ollama.com](https://ollama.com) — corre localmente       |
| **Git**    | qualquer      | para clonar o projecto                                    |

Após instalar o Ollama, descarrega os modelos necessários:

```bash
ollama pull bge-m3          # embeddings (obrigatório)
ollama pull gemma3:4b       # router/reranker (recomendado)
ollama pull qwen3:8b        # chat geral (recomendado)
```

---

## Instalação

### Linux

```bash
# 1. Clonar o repositório
git clone https://github.com/PedroMglo/local-ai-sys.git obsidian-rag
cd obsidian-rag

# 2. Criar e activar virtualenv
python3 -m venv .venv
source .venv/bin/activate

# 3. Instalar dependências
pip install -r requirements.txt
pip install -e .

# 4. (Opcional) Instalar Graphify para knowledge graphs
pip install -e ".[graphify]"

# 5. Verificar instalação
rag-serve --help
rag-query --help
```

**Systemd (serviço automático no Linux):**

Cria os ficheiros de serviço em `~/.config/systemd/user/`:

<details>
<summary>obsidian-rag-api.service</summary>

```ini
[Unit]
Description=Obsidian RAG API
After=network.target

[Service]
Type=simple
WorkingDirectory=%h/ai-local/obsidian-rag
ExecStart=%h/ai-local/obsidian-rag/.venv/bin/rag-serve
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

</details>

<details>
<summary>obsidian-rag-sync.timer (sync diário às 04:00)</summary>

```ini
[Unit]
Description=Obsidian RAG sync timer

[Timer]
OnCalendar=*-*-* 04:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```ini
# obsidian-rag-sync.service
[Unit]
Description=Obsidian RAG sync

[Service]
Type=oneshot
WorkingDirectory=%h/ai-local/obsidian-rag
ExecStart=%h/ai-local/obsidian-rag/.venv/bin/rag-sync --all
```

</details>

```bash
# Activar serviços
systemctl --user daemon-reload
systemctl --user enable --now obsidian-rag-api.service
systemctl --user enable --now obsidian-rag-sync.timer

# Ver estado e logs
systemctl --user status obsidian-rag-api
journalctl --user -u obsidian-rag-api -f
```

---

### macOS

O processo é idêntico ao Linux, mas sem systemd. Usa `launchd` ou simplesmente corre em terminal.

```bash
# 1. Instalar dependências do sistema (Homebrew recomendado)
brew install python@3.11 git

# 2. Clonar o repositório
git clone https://github.com/PedroMglo/local-ai-sys.git obsidian-rag
cd obsidian-rag

# 3. Criar e activar virtualenv
python3.11 -m venv .venv
source .venv/bin/activate

# 4. Instalar dependências
pip install -r requirements.txt
pip install -e .

# 5. (Opcional) Graphify
pip install -e ".[graphify]"
```

**Iniciar manualmente (macOS):**

```bash
# Terminal 1 — API
source .venv/bin/activate && rag-serve

# Terminal 2 — sync inicial
source .venv/bin/activate && rag-sync --all
```

**Serviço automático com launchd (macOS):**

```bash
# Criar ~/Library/LaunchAgents/com.obsidian-rag.api.plist
cat > ~/Library/LaunchAgents/com.obsidian-rag.api.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.obsidian-rag.api</string>
  <key>ProgramArguments</key>
  <array>
    <string>/Users/YOUR_USER/obsidian-rag/.venv/bin/rag-serve</string>
  </array>
  <key>WorkingDirectory</key>
  <string>/Users/YOUR_USER/obsidian-rag</string>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
</dict>
</plist>
EOF

# Substituir YOUR_USER pelo teu username
# Activar
launchctl load ~/Library/LaunchAgents/com.obsidian-rag.api.plist
```

---

### Windows

> **Recomendado:** usar **WSL2** (Windows Subsystem for Linux) para experiência idêntica ao Linux.  
> **Alternativa:** instalação nativa com Python para Windows.

#### Opção A — WSL2 (recomendada)

```powershell
# PowerShell (como Administrador) — instalar WSL2 com Ubuntu
wsl --install -d Ubuntu
```

Depois de reiniciar e configurar o utilizador Ubuntu, abre o terminal WSL e segue as instruções da secção **Linux** acima.

O Ollama deve correr em Windows nativo; o WSL acede-lhe em `http://host.docker.internal:11434` ou `http://$(ip route show | grep default | awk '{print $3}'):11434`.

Ajusta `rag.toml`:

```toml
[ollama]
base_url = "http://172.x.x.x:11434"  # IP do Windows host a partir do WSL
```

#### Opção B — Python nativo no Windows

```powershell
# 1. Clonar
git clone https://github.com/PedroMglo/local-ai-sys.git obsidian-rag
cd obsidian-rag

# 2. Criar e activar virtualenv
python -m venv .venv
.venv\Scripts\activate

# 3. Instalar dependências
pip install -r requirements.txt
pip install -e .

# 4. (Opcional) Graphify
pip install -e ".[graphify]"
```

**Iniciar em Windows (nativo):**

```powershell
# Terminal 1 — API
.venv\Scripts\activate
rag-serve

# Terminal 2 — sync inicial
.venv\Scripts\activate
rag-sync --all
```

**Notas Windows:**

- O caminho para o Vault Obsidian usa formato Windows: `C:\Users\nome\Documents\Obsidian\Vault`  
  No `rag.toml`, usa barras normais ou escapa: `vault_dir = "C:/Users/nome/Documents/Obsidian/Vault"`
- O `rsync` não existe nativamente em Windows — o sync das notas usa cópia directa via Python; o campo `vault_dir` em `rag.toml` deve apontar directamente para o vault.
- Para serviço automático no Windows, usa o **Task Scheduler** (Agendador de Tarefas) para correr `rag-serve` e `rag-sync --all`.

---

## Configuração (`rag.toml`)

Copia e edita `rag.toml` na raiz do projecto:

```toml
[paths]
source_dir = "source"           # notas Obsidian copiadas aqui
data_dir   = "data/chroma"      # ChromaDB persistente
vault_dir  = "~/Obsidian/Vault" # caminho para o teu Vault Obsidian
                                # Windows: "C:/Users/nome/Obsidian/Vault"

[ollama]
base_url        = "http://localhost:11434"  # WSL→Windows: ver acima
embedding_model = "bge-m3"

[chunking]        # notas Markdown
max_chars        = 2000
min_chars        = 50
contextual_prefix = true

[repos]           # repositórios Git a indexar
paths            = ["~/ai-local/SPEECH-LAB"]  # adiciona os teus repos
collection_name  = "code_repos"

[repos.chunking]  # chunking de código Python
strategy         = "ast"
max_chars        = 2000
min_chars        = 80

[graphify]        # knowledge graph (opt-in)
enabled          = false
backend          = "ollama"
output_dir       = "data/graphify"
auto_update      = false

[retrieval]
top_k            = 10
score_threshold  = 0.45

[models]          # RAG activado por modelo (nome do modelo Ollama)
"qwen3:8b"       = true
"deepseek-r1:8b" = true
"qwen2.5-coder"  = false  # sem RAG para queries de código puro
```

**Override por variável de ambiente** (útil para CI/testes):

```bash
RAG_RETRIEVAL_TOP_K=15 rag-serve
RAG_GRAPHIFY_AUTO_UPDATE=true rag-sync -g
RAG_API_API_KEY=minha-chave rag-serve   # activa autenticação
```

---

## Primeiro Uso

```bash
# 1. Activar o virtualenv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate           # Windows

# 2. Sync inicial (copia notas + indexa embeddings)
rag-sync --all

# 3. Iniciar a API
rag-serve
# API disponível em http://localhost:8484

# 4. Testar
curl http://localhost:8484/health
# {"status":"ok","version":"0.3.0"}

# 5. Primeira query
rag-query "como configurar aliases no zsh"
```

---

## Comandos CLI

| Comando                   | Descrição                                              |
| ------------------------- | ------------------------------------------------------ |
| `rag-sync -l`             | Embeddings: notas Obsidian + repos Git (só deltas)     |
| `rag-sync -g`             | Grafos Graphify para repos sem grafo ou desatualizados |
| `rag-sync --all`          | Tudo: embeddings + grafos (`-l` + `-g`)                |
| `rag-serve`               | Iniciar API REST (porta 8484)                          |
| `rag-query "texto"`       | Query semântica (notas + código)                       |
| `rag-query -n 10 "texto"` | Query com N resultados                                 |
| `rag-chat`                | REPL interativo com RAG augmentation                   |
| `rag-backup`              | Backup timestamped do ChromaDB (rotação de 3 cópias)   |

---

## API REST

| Método | Endpoint                         | Descrição                                 | Auth  |
| ------ | -------------------------------- | ----------------------------------------- | ----- |
| `GET`  | `/health`                        | Health check + versão                     | Não   |
| `GET`  | `/stats`                         | Estatísticas (chunks notas + código)      | Sim\* |
| `POST` | `/query`                         | Pesquisa semântica nas notas Obsidian     | Sim\* |
| `POST` | `/query/code`                    | Pesquisa semântica no código dos repos    | Sim\* |
| `GET`  | `/repos`                         | Lista repos configurados + stats grafo    | Sim\* |
| `GET`  | `/graph/{repo}`                  | GRAPH_REPORT.md de um repo                | Sim\* |
| `POST` | `/graph/{repo}/query`            | Query em linguagem natural ao grafo       | Sim\* |
| `GET`  | `/graph/{repo}/neighbors/{node}` | Vizinhos de um nó no grafo                | Sim\* |
| `POST` | `/chat`                          | Chat RAG-augmented com streaming → Ollama | Sim\* |

_\*Auth obrigatória apenas quando `api_key` está definido em `rag.toml`._

### Exemplos cURL

```bash
# Health check
curl http://localhost:8484/health

# Query semântica nas notas
curl -s http://localhost:8484/query \
  -H "Content-Type: application/json" \
  -d '{"query": "como configurar aliases no zsh", "top_k": 5}'

# Query de código (filtro por repo)
curl -s http://localhost:8484/query/code \
  -H "Content-Type: application/json" \
  -d '{"query": "segment_window chunking strategy", "repo": "SPEECH-LAB"}'

# Estatísticas
curl -s http://localhost:8484/stats

# Lista de repos e estado do grafo
curl -s http://localhost:8484/repos

# Query ao knowledge graph
curl -s http://localhost:8484/graph/SPEECH-LAB/query \
  -H "Content-Type: application/json" \
  -d '{"query": "como o transcriber liga ao postprocess?"}'

# Chat RAG (streaming)
curl -s http://localhost:8484/chat \
  -H "Content-Type: application/json" \
  -d '{"model": "qwen3:8b", "messages": [{"role": "user", "content": "Explica o sistema de chunking"}]}'
```

---

## Docker (todas as plataformas)

A abordagem Docker funciona em Linux, macOS e Windows (com Docker Desktop).

**Pré-requisito:** Ollama deve correr no host ou num container acessível.

```bash
# Build e arranque com docker compose
docker compose up -d

# Logs
docker compose logs -f obsidian-rag

# Parar
docker compose down
```

O `docker-compose.yml` expõe a porta `8484` e monta `./data` para persistência do ChromaDB.

> **Windows/macOS:** O Ollama no host é acessível via `host.docker.internal:11434`. Ajusta `rag.toml` ou define a env var `RAG_OLLAMA_BASE_URL=http://host.docker.internal:11434`.

---

## Graphify — Knowledge Graph (opt-in)

O Graphify analisa repositórios Git e cria um grafo estrutural de relações entre módulos, funções e classes.

```bash
# Instalar o extra
pip install -e ".[graphify]"

# Gerar grafos para todos os repos configurados
rag-sync -g

# Consultar via API
curl -s http://localhost:8484/graph/SPEECH-LAB
curl -s http://localhost:8484/graph/SPEECH-LAB/neighbors/ChunkBuilder
```

Resultados guardados em `data/graphify/{repo}/graphify-out/`:

```
├── graph.json           # grafo completo (NetworkX node-link)
├── GRAPH_REPORT.md      # god nodes, conexões, questões sugeridas
└── community_summaries.json
```

**Processamento:** código Python via AST local (sem LLM); docs Markdown via Ollama local. Nenhum dado enviado para fora.

---

## Arquitetura

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

Git Repos ──► graphify extract ──► graph.json ──► /graph/{repo}/query
              (AST local + Ollama)
```

**Stack:**

| Componente      | Tecnologia                                        |
| --------------- | ------------------------------------------------- |
| Embeddings      | Ollama `bge-m3` (multilíngue, 1024d, local)       |
| Vector Store    | ChromaDB persistente (cosine similarity)          |
| Code Chunking   | `ast.parse()` stdlib — zero dependências externas |
| Knowledge Graph | Graphify com backend Ollama (opt-in)              |
| API             | FastAPI + uvicorn                                 |
| Graph Query     | NetworkX (leitura local de `graph.json`)          |

---

## Notas Técnicas

- **Sync incremental**: só re-processa chunks cujo conteúdo mudou (hash SHA256) — segunda execução muito rápida
- **Chunking Markdown**: divide por headers H1/H2/H3, max 2000 chars, overlap 200
- **Chunking código**: `ast.parse()` — função/classe/módulo; fallback texto para parse failures
- **Performance**: ~37 chunks/s no embedding, queries <200ms
- **Retrieval multi-estratégia**: vector search + keyword + title-based, com threshold dinâmico
- **Token budget**: 4000 tokens, split 40/40/20 (notas/código/grafo), trunca por chunks inteiros
