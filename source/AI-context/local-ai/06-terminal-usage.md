---
type: ai-knowledge
area: local-ai
tags:
  - terminal
  - zsh
  - aliases
  - functions
  - workflows
---

# 💻 Uso no Terminal

## Ficheiro de funções

```
~/.zsh_custom.d/42-ai.zsh
```

Carregado automaticamente pelo Zsh ao iniciar sessão.

## Comandos disponíveis

### `ai` — Chat principal

```bash
# Chat interativo (abre REPL)
ai

# Prompt direto
ai "explica o que são containers Docker"

# Com modelo específico
ai coder "escreve um Dockerfile para Python 3.12"
ai phi "analisa prós e contras de microservices vs monolith"
ai gemma "descreve esta imagem"

# Com pipe (stdin)
cat ficheiro.py | ai "revê este código"
cat error.log | ai "o que significa este erro?"
git diff | ai coder "resume as alterações"
```

**Atalhos de modelo:**
| Atalho | Modelo | Uso |
|--------|--------|-----|
| `qwen` / `qwen3` | qwen3-pt | Default, raciocínio, multilingue |
| `coder` / `code` | coder-pt | Código |
| `deep` / `r1` | deepseek-r1-pt | Raciocínio profundo |
| `gemma` / `gemma3` | gemma3-pt | Multimodal, ultra-rápido |

### `aicode` — Assistente de código

```bash
aicode "escreve função para ler Parquet com DuckDB"
cat app.py | aicode "encontra bugs"
aicode < script.sh
```

### `aiask` — Resposta rápida

```bash
aiask "porta default do PostgreSQL?"
aiask "diferença entre git rebase e merge"
```

### `aimodels` — Listar modelos

```bash
aimodels
```

### `aistatus` — Estado (VRAM + modelos carregados)

```bash
aistatus
```

### `aiembed` — Gerar embeddings

```bash
aiembed "machine learning com python"
echo "texto para embedding" | aiembed
```

### `ai-monitor` — Dashboard live

```bash
ai-monitor        # refresh a cada 2s
ai-monitor 5      # refresh a cada 5s
```

## Workflows úteis

### Rever código antes de commit
```bash
git diff --staged | aicode "revê este código, encontra bugs ou melhorias"
```

### Explicar um erro
```bash
comando_que_falha 2>&1 | ai "explica este erro e sugere solução"
```

### Resumir um ficheiro longo
```bash
cat README.md | ai "resume em 5 pontos principais"
```

### Gerar commit message
```bash
git diff --staged | aicode "gera uma commit message descritiva em inglês"
```

### Converter formatos
```bash
cat dados.csv | aicode "converte para SQL INSERT statements"
```

### Documentar função
```bash
cat utils.py | aicode "adiciona docstrings a todas as funções"
```

## Monitorização

| Comando | O que mostra |
|---------|-------------|
| `aistatus` | Modelo carregado + VRAM |
| `nvtop` | GPU interativo (como htop para GPU) |
| `ai-monitor` | Dashboard: GPU + RAM + CPU + Ollama |
| `nvidia-smi` | Snapshot da GPU |
| `ollama ps` | Modelos em memória |

## Dicas

- Usar **`ai coder`** para código — tão rápido como o default mas especializado
- **`ai gemma`** para respostas ultra-rápidas (77 tok/s!)
- **`ai deep`** para problemas que exigem raciocínio passo-a-passo
- **Pipe é poderoso** — qualquer output pode ser enviado para análise
- **`aiask`** é ideal para perguntas factuais rápidas (resposta curta forçada)
- **Todos os modelos correm 100% na GPU** — sem offloading CPU
- Para sessões longas, usar `ai` sem argumentos (modo REPL interativo)
- Ctrl+D ou `/bye` para sair do modo interativo
