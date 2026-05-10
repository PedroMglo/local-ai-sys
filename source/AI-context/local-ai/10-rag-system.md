---
type: ai-knowledge
area: local-ai
tags:
  - rag
  - pipeline
  - obsidian
  - chromadb
  - embeddings
  - sync
---

# 🔍 Sistema RAG Local

## O que é

Sistema de **Retrieval-Augmented Generation (RAG)** que injeta contexto das notas pessoais (Obsidian Vault) automaticamente nas respostas dos LLMs locais. Quando fazes uma pergunta ao `ol`, o sistema:

1. Gera um embedding da tua pergunta (via bge-m3)
2. Procura chunks relevantes no ChromaDB (busca semântica)
3. Injeta o contexto encontrado no system prompt do LLM
4. O LLM responde usando os dados das tuas notas

## Localização

```
~/ai-local/obsidian-rag/
├── rag.toml              ← Configuração central (TOML)
├── obsidian_rag/         ← Package Python modular
│   ├── config.py         ← Carrega rag.toml
│   ├── chunking/         ← Split Markdown por headers
│   ├── embeddings/       ← Gera embeddings via Ollama bge-m3
│   ├── store/            ← ChromaDB (armazenamento vetorial)
│   ├── retrieval/        ← Multi-strategy RAG search
│   ├── api/              ← FastAPI REST + CLI
│   └── pipeline/         ← Orchestração sync
├── data/chroma/          ← Base de dados vetorial (persistente)
└── source/               ← Cópia das notas .md do Vault
```

## Comandos principais

### `obsidian-rag-sync` — Sincronizar Vault → RAG

```bash
obsidian-rag-sync
```

Faz rsync do Obsidian Vault para `source/`, depois chunk → embed → ChromaDB.
Corre automaticamente via **systemd timer diário às 04:00**.

Para forçar re-sync manual:

```bash
~/.local/bin/obsidian-rag-sync
```

### `obsidian-rag-query` — Busca semântica direta

```bash
obsidian-rag-query "que modelos tenho?"
obsidian-rag-query -n 5 "aliases zsh"
obsidian-rag-query --json "gpu vram"
```

Busca chunks relevantes no ChromaDB sem passar pelo LLM. Útil para debug e verificação.

### `obsidian-rag-serve` — Iniciar API

```bash
obsidian-rag-serve
```

Inicia o servidor FastAPI na porta 8484. Normalmente gerido pelo systemd.

## API REST (porta 8484)

| Endpoint  | Método | Descrição                       |
| --------- | ------ | ------------------------------- |
| `/health` | GET    | Health check                    |
| `/stats`  | GET    | Nº de chunks, coleção           |
| `/query`  | POST   | Busca semântica (sem LLM)       |
| `/chat`   | POST   | Proxy RAG-augmented para Ollama |

### Testar API

```bash
curl http://localhost:8484/health
curl http://localhost:8484/stats
```

## Configuração (`rag.toml`)

Ficheiro central de configuração em `~/ai-local/obsidian-rag/rag.toml`:

```toml
[paths]
source_dir = "source"
data_dir = "data/chroma"
vault_dir = "~/Obsidian/Vault"

[ollama]
base_url = "http://localhost:11434"
embedding_model = "bge-m3"

[chunking]
max_chars = 2000
overlap_chars = 200
min_chars = 50

[retrieval]
top_k = 10
score_threshold = 0.45
dynamic_threshold_ratio = 0.75

[api]
host = "0.0.0.0"
port = 8484

[models]
"qwen3-pt" = true       # RAG ativo
"deepseek-r1-pt" = true # RAG ativo
"coder-pt" = false      # passthrough (sem RAG)
"gemma3-pt" = true      # RAG ativo
```

Qualquer opção pode ser overridden via env var: `RAG_RETRIEVAL_TOP_K=15`.

## Integração com terminal

O comando `ol` (definido em `~/.zsh_custom.d/42-ai.zsh`) envia prompts para `localhost:8484/chat` em vez de diretamente ao Ollama. Isto ativa o RAG automaticamente.

- Se o RAG está ativo para o modelo → injeta contexto das notas
- Se o score é baixo (pergunta não relacionada) → passthrough sem RAG
- Se a API não responde → fallback automático para `ollama run`

## Systemd

```bash
# Serviço da API
systemctl --user status obsidian-rag-api
systemctl --user restart obsidian-rag-api

# Timer de sync (04:00 diário)
systemctl --user status obsidian-rag-sync.timer
```

## Como funciona o pipeline

1. **rsync** — Copia .md files do Vault Obsidian para `source/`
2. **Chunking** — Divide notas por headers (H1/H2/H3), strip frontmatter, adiciona prefixo contextual
3. **Embedding** — Gera vetores 1024d via bge-m3 (Ollama)
4. **ChromaDB** — Armazena vetores + metadata (incremental, só novos chunks)
5. **API** — Serve queries semânticas e proxy RAG para o Ollama

## Troubleshooting

### RAG não injeta contexto

```bash
# Verificar se API está a correr
curl http://localhost:8484/health

# Verificar se há chunks
curl http://localhost:8484/stats

# Testar query diretamente
obsidian-rag-query "teste"
```

### Notas não aparecem nos resultados

```bash
# Re-sincronizar
~/.local/bin/obsidian-rag-sync

# Ou forçar re-index completo
cd ~/ai-local/obsidian-rag
rm -rf data/chroma
python -m obsidian_rag.pipeline.sync
```

### Modelo responde sem contexto das notas

- Verificar se modelo tem RAG ativo em `rag.toml` (`[models]` section)
- Confirmar que `ol` está a usar o proxy: `curl http://localhost:8484/health`
