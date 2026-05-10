---
type: shell-knowledge
area: linux
system: zsh
source: ~/.zsh_custom.d/42-ai.zsh
created_by: github-copilot-cli
tags:
  - linux
  - zsh
  - shell
  - ai
  - ollama
  - llm
  - rag
---

# 🤖 Shell — AI Local (Ollama)

## Sobre

Módulo `42-ai.zsh` — funções para interagir com modelos de linguagem locais via Ollama.  
Suporta RAG-augmented chat através de um proxy local (`obsidian-rag` em `localhost:8484`), com fallback automático para Ollama direto.

---

## Arquitetura

```
┌────────────┐     ┌─────────────────────────┐     ┌──────────────┐
│  Terminal  │────▶│  RAG Proxy :8484/chat   │────▶│  Ollama :11434│
│  (ol, etc) │     │  (obsidian-rag)         │     │  (modelos)   │
└────────────┘     └─────────────────────────┘     └──────────────┘
                   Se proxy indisponível → fallback direto para Ollama
```

**Variável interna:** `_AI_RAG_PROXY="http://localhost:8484/chat"`

---

## Modelos Disponíveis

| Atalho | Modelfile interno | Base | Uso |
|--------|-------------------|------|-----|
| `qwen` / `qwen3` | `qwen3-pt` | qwen3:8b | Default — raciocínio, multilingue |
| `coder` / `code` | `coder-pt` | qwen2.5-coder:7b | Código |
| `deep` / `deepseek` / `r1` | `deepseek-r1-pt` | deepseek-r1:8b | Raciocínio profundo (chain-of-thought) |
| `gemma` / `gemma3` | `gemma3-pt` | gemma3:4b | Multimodal, ultra-rápido |

> Todos os modelos correm 100% na GPU (8GB VRAM).

---

## Funções

### `ol`
**Objetivo:** Chat principal com modelo AI local  
**Alias anterior:** `ai` (removido com `unalias`)

```zsh
ol [modelo] [prompt...]
echo "texto" | ol [modelo]
```

**Exemplos:**
```zsh
ol explica o que é um pipe em Linux
ol coder refactora esta função para usar async/await
ol deep analisa os prós e contras de microservices
cat ficheiro.py | ol coder "revê este código"
ol                  # chat interativo com qwen3
```

**Comportamento:**
- Sem argumentos: abre chat interativo com `qwen3-pt`
- Primeiro argumento pode ser atalho de modelo ou início do prompt
- Aceita stdin via pipe
- Usa `_ai_chat` internamente (RAG proxy + fallback Ollama)

---

### `aicode`
**Objetivo:** Assistente de código (atalho para `ol coder`)

```zsh
aicode <prompt>
cat ficheiro.py | aicode "revê este código"
aicode < script.sh
```

---

### `aiask`
**Objetivo:** Pergunta rápida com resposta concisa (máximo 3 frases)

```zsh
aiask <pergunta>
aiask "qual é a porta default do PostgreSQL?"
aiask "diferença entre git rebase e merge"
```

---

### `aimodels`
**Objetivo:** Listar modelos Ollama instalados localmente

```zsh
aimodels
```

Equivalente a `ollama list`.

---

### `aistatus`
**Objetivo:** Ver modelos em memória e uso de VRAM

```zsh
aistatus
```

Mostra output de `ollama ps` + VRAM via `nvidia-smi`.

---

### `aiembed`
**Objetivo:** Gerar embedding de texto com `bge-m3`

```zsh
aiembed <texto>
echo "texto" | aiembed
cat documento.txt | aiembed
```

- Modelo: `bge-m3` (multilíngue, 1024 dimensões)
- Output: dimensões + primeiros 5 valores do array
- Útil para RAG, busca semântica, clustering

---

### `_ai_chat` (interna)
**Objetivo:** Enviar prompt para RAG proxy ou Ollama diretamente

```zsh
_ai_chat <model> <prompt>
```

- Testa disponibilidade do proxy com timeout de 1s
- Se disponível: envia para `localhost:8484/chat` com streaming NDJSON
- Se indisponível: executa `ollama run <model> <prompt>`

---

## Cheat Sheet

| Comando | Descrição |
|---------|-----------|
| `ol <prompt>` | Chat com qwen3 (default) |
| `ol coder <prompt>` | Chat com modelo de código |
| `ol deep <prompt>` | Raciocínio profundo deepseek-r1 |
| `ol gemma <prompt>` | Chat rápido gemma3 |
| `aicode <prompt>` | Atalho para código |
| `aiask <pergunta>` | Resposta concisa (3 frases) |
| `aimodels` | Listar modelos instalados |
| `aistatus` | Ver VRAM e modelos carregados |
| `aiembed <texto>` | Gerar embedding bge-m3 |
| `cat f.py \| aicode "revê"` | Analisar ficheiro |

---

## Dependências

| Ferramenta | Obrigatória | Uso |
|------------|-------------|-----|
| `ollama` | Sim | Backend de modelos |
| `python3` | Sim | Parsing NDJSON, escaping JSON |
| `curl` | Sim | HTTP para proxy e Ollama API |
| `nvidia-smi` | Não | VRAM em `aistatus` |

---

## Troubleshooting

### Modelo não encontrado
```zsh
ollama list          # verificar modelos instalados
ollama pull qwen3:8b # instalar modelo
```

### Proxy RAG indisponível
O fallback é automático. Para verificar o proxy:
```zsh
curl -sf http://localhost:8484/health && echo "OK" || echo "offline"
```

### VRAM insuficiente
```zsh
aistatus   # ver o que está em memória
ollama stop <modelo>  # libertar VRAM
```
