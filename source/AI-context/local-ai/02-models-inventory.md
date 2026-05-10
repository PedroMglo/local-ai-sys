---
type: ai-knowledge
area: local-ai
tags:
  - models
  - inventory
  - specs
  - quantization
---

# 📦 Modelos — Inventário Detalhado

> **Última actualização:** 2026-05-05 — Todos os modelos correm 100% na GPU.

## Modelos Generativos

### qwen3:8b (default — uso geral)

| Propriedade | Valor |
|-------------|-------|
| Família | Qwen 3 (Alibaba) |
| Parâmetros | 8B |
| Quantização | Q4 (default) |
| Tamanho disco | 5.2 GB |
| VRAM usada | 6060 MiB |
| GPU/CPU split | **100% GPU** |
| Velocidade | **~44 tok/s** |
| Contexto default | 4096 tokens |
| Contexto max | 32768 tokens |
| Capacidades | Raciocínio (thinking mode), multilingue, instrução |
| Modo thinking | ✅ Sim |

**Notas:**
- Modelo por defeito para uso geral
- Evolução da família Qwen3.5 (melhor em benchmarks)
- Excelente em português e multilingue
- Thinking mode mais eficiente que qwen3.5

---

### deepseek-r1:8b (raciocínio profundo)

| Propriedade | Valor |
|-------------|-------|
| Família | DeepSeek-R1 (DeepSeek) |
| Parâmetros | 8B (destilado de Llama 3.1) |
| Quantização | Q4 (default) |
| Tamanho disco | 5.2 GB |
| VRAM usada | 6060 MiB |
| GPU/CPU split | **100% GPU** |
| Velocidade | **~45 tok/s** |
| Contexto default | 4096 tokens |
| Contexto max | 128K tokens |
| Capacidades | Chain-of-thought, raciocínio tipo o1, math, lógica |

**Notas:**
- Destilado do modelo R1 completo (671B) — raciocínio profundo em pacote pequeno
- Especializado em pensamento passo-a-passo
- Excelente em matemática e puzzles lógicos
- Contexto máximo de 128K (o maior entre todos)

---

### qwen2.5-coder:7b (código)

| Propriedade | Valor |
|-------------|-------|
| Família | Qwen 2.5 Coder (Alibaba) |
| Parâmetros | 7B |
| Quantização | Q4_0 (default) |
| Tamanho disco | 4.7 GB |
| VRAM usada | 5072 MiB |
| GPU/CPU split | **100% GPU** |
| Velocidade | **~43 tok/s** |
| Contexto default | 4096 tokens |
| Contexto max | 32768 tokens |
| Capacidades | Geração de código, refactoring, debugging |

**Notas:**
- Especializado em código (Python, JS, Bash, SQL, etc.)
- Menos forte em conversação geral ou português
- Ideal para `aicode` e pipe de ficheiros

---

### gemma3:4b (multimodal — ultra-rápido)

| Propriedade | Valor |
|-------------|-------|
| Família | Gemma 3 (Google) |
| Parâmetros | 4B |
| Quantização | Q4 (default) |
| Tamanho disco | 3.3 GB |
| VRAM usada | 4016 MiB |
| GPU/CPU split | **100% GPU** |
| Velocidade | **~77 tok/s** |
| Contexto default | 4096 tokens |
| Capacidades | Multimodal (imagens), conversação, multilingue |

**Notas:**
- Modelo mais rápido do setup (77 tok/s!)
- Suporta input de imagens (multimodal)
- Bom em português de Portugal
- VRAM baixa — deixa espaço para contextos grandes

---

## Modelo de Embeddings

### bge-m3

| Propriedade | Valor |
|-------------|-------|
| Família | BGE-M3 (BAAI) |
| Tipo | Embedding model |
| Tamanho disco | 1.2 GB |
| VRAM usada | 1916 MiB |
| Dimensões | 1024 |
| Multilíngue | ✅ Sim (100+ idiomas) |
| Velocidade | ~8s single / ~3s batch(4) |

**Notas:**
- Excelente para RAG, busca semântica, clustering
- Multilíngue (funciona bem com PT)
- Suporta batch processing

---

## Resumo comparativo

| Modelo | Speed | VRAM | 100% GPU | Melhor para |
|--------|-------|------|----------|-------------|
| gemma3:4b | ⚡ 77 tok/s | 4.0 GB | ✅ | Multimodal, respostas rápidas |
| deepseek-r1:8b | 🔥 45 tok/s | 6.0 GB | ✅ | Raciocínio profundo |
| qwen3:8b | 🔥 44 tok/s | 6.0 GB | ✅ | Geral, multilingue |
| qwen2.5-coder:7b | 🔥 43 tok/s | 5.0 GB | ✅ | Código |
| bge-m3 | — | 1.9 GB | ✅ | Embeddings |
