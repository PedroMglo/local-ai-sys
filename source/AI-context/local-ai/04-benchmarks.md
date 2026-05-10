---
type: ai-knowledge
area: local-ai
tags:
  - benchmarks
  - performance
  - tokens-per-second
  - comparison
---

# 📊 Benchmarks de Performance

## Condições do teste

- **Data:** 2026-05-05
- **Hardware:** RTX 4060 Max-Q 8GB, 32GB RAM, 24 CPU threads
- **Ollama:** v0.23.0 com Flash Attention ativo
- **Método:** API `/api/generate` com `stream: false`
- **Cold start:** modelo descarregado antes de cada teste (`ollama stop`)
- **Todos os modelos:** 100% GPU (sem offloading CPU)

---

## Teste 1: Velocidade Bruta

**Prompt:** "Count from 1 to 20, one number per line."

| Modelo | Load time | Tokens | Speed | VRAM |
|--------|-----------|--------|-------|------|
| gemma3:4b | 2.6s | 51 | **77.2 tok/s** | 4016 MiB |
| deepseek-r1:8b | 3.0s | 272 | **45.4 tok/s** | 6060 MiB |
| qwen3:8b | 2.3s | 493 | **44.9 tok/s** | 6060 MiB |
| qwen2.5-coder:7b | 1.4s | 74 | **43.2 tok/s** | 5072 MiB |

**Observações:**
- gemma3:4b é o mais rápido (77 tok/s!) — ideal para respostas rápidas
- deepseek-r1, qwen3 e coder estão todos acima de 43 tok/s
- qwen3 gerou 493 tokens (thinking mode) mas manteve 44 tok/s
- Load times todos abaixo de 3s (100% GPU = carregamento rápido)

---

## Teste 2: Raciocínio Lógico

**Puzzle:** "Um agricultor tem 17 ovelhas. Todas menos 9 morrem. Quantas ovelhas restam?"
**Resposta correta:** 9

| Modelo | Tempo | Tokens | Speed | Resposta | Correto? |
|--------|-------|--------|-------|----------|----------|
| deepseek-r1:8b | 9.3s | 311 | 45.1 tok/s | **9** — "todas menos 9 = 9 sobrevivem" | ✅ |
| qwen3:8b | 18.1s | 698 | 44.4 tok/s | **9** — "todas menos 9 morrem" | ✅ |
| gemma3:4b | 3.0s | 32 | 77.1 tok/s | **9** — explicação clara | ✅ |
| qwen2.5-coder:7b | 4.7s | 13 | 47.6 tok/s | **8** | ❌ |

**Observações:**
- **Todos os novos modelos acertaram!** (vs phi4 antigo que se contradisse)
- gemma3:4b responde em 3 segundos com resposta correta
- deepseek-r1 é eficiente no raciocínio (9s, chain-of-thought compacto)
- qwen2.5-coder continua fraco em lógica (é para código)

---

## Teste 3: Geração de Código

**Prompt:** "Write a Python function fibonacci(n) with memoization decorator. Only code."

| Modelo | Tempo | Tokens | Speed | Qualidade |
|--------|-------|--------|-------|-----------|
| gemma3:4b | 4.1s | 118 | 75.4 tok/s | ✅ Correto (helper com dict manual) |
| qwen2.5-coder:7b | 4.1s | 103 | 42.4 tok/s | ✅ Decorator custom, funcional |
| qwen3:8b | 27.4s | 1083 | 43.5 tok/s | ✅ lru_cache, docstring completa |
| deepseek-r1:8b | 71.2s | 2905 | 42.6 tok/s | ✅ Correto mas verboso (thinking mode) |

**Observações:**
- Para código rápido: **gemma3:4b** ou **qwen2.5-coder** (4s cada)
- deepseek-r1 é verboso (explica abordagem antes do código) — usar para problemas complexos
- qwen3 usa thinking mode mas produz código limpo

---

## Teste 4: Português de Portugal

**Prompt:** "Explica a diferença entre 'há' e 'à' com exemplos."

| Modelo | Tempo | Tokens | Speed | Qualidade PT |
|--------|-------|--------|-------|-------------|
| qwen3:8b | 10.8s | 372 | 44.4 tok/s | ✅ Correto e conciso |
| gemma3:4b | 4.2s | 120 | 75.7 tok/s | ✅ Bom, exemplos claros |
| deepseek-r1:8b | 11.7s | 411 | 44.5 tok/s | ⚠️ "à" = "para ela" (impreciso) |
| qwen2.5-coder:7b | 3.6s | 82 | 42.2 tok/s | ✅ Correto (tende PT-BR) |

**Observações:**
- **qwen3:8b** e **gemma3:4b** são os melhores em PT-PT
- deepseek-r1 menos preciso em gramática PT (foco é raciocínio/math)
- Para conteúdo em PT-PT, preferir qwen3-pt ou gemma3-pt

---

## Teste 5: VRAM (100% GPU em todos)

| Modelo | VRAM (MiB) | % da VRAM total | GPU layers | Load time |
|--------|-----------|-----------------|------------|-----------|
| gemma3:4b | 4016 | 49% | **100% GPU** | 2.6s |
| qwen2.5-coder:7b | 5072 | 62% | **100% GPU** | 1.4s |
| deepseek-r1:8b | 6060 | 74% | **100% GPU** | 3.0s |
| qwen3:8b | 6060 | 74% | **100% GPU** | 2.3s |
| bge-m3 | 1916 | 23% | **100% GPU** | <1s |

---

## Ranking Final

### Por velocidade (tok/s):
1. 🥇 gemma3:4b — **77 tok/s**
2. 🥈 deepseek-r1:8b — **45 tok/s**
3. 🥉 qwen3:8b — **44 tok/s**
4. qwen2.5-coder:7b — **43 tok/s**

### Por qualidade de raciocínio:
1. 🥇 deepseek-r1:8b (chain-of-thought, sempre correto)
2. 🥈 qwen3:8b (thinking mode, correto)
3. 🥉 gemma3:4b (correto e rápido)
4. qwen2.5-coder:7b (fraco em lógica)

### Por qualidade em PT-PT:
1. 🥇 qwen3:8b (melhor equilíbrio)
2. 🥈 gemma3:4b (bom e ultra-rápido)
3. 🥉 qwen2.5-coder:7b (tende PT-BR)
4. deepseek-r1:8b (impreciso em gramática)

### Recomendação por caso de uso:

| Uso | Modelo | Razão |
|-----|--------|-------|
| Chat geral | qwen3-pt | 44 tok/s, multilingue, thinking |
| Código rápido | coder-pt | 43 tok/s, especializado |
| Raciocínio profundo | deepseek-r1-pt | Chain-of-thought, 45 tok/s |
| Respostas rápidas | gemma3-pt | 77 tok/s! Multimodal |
| Português PT | qwen3-pt | Melhor gramática PT-PT |
| Embeddings/RAG | bge-m3 | 1024d, multilíngue |

---

## Comparação com setup anterior (removido)

| Métrica | Antes | Depois |
|---------|-------|--------|
| Modelos 100% GPU | 1 de 4 | **4 de 4** |
| Velocidade média | 25 tok/s | **52 tok/s** (+108%) |
| Raciocínio (acertos) | 2/4 | **3/4** |
| Load time médio | 8.8s | **2.3s** |
| VRAM máxima usada | 7512 MiB (92%) | 6060 MiB (74%) |
