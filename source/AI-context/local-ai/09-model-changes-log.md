---
type: ai-knowledge
area: local-ai
tags:
  - changelog
  - models
  - decisions
  - vram
---

# 📋 Histórico de Alterações de Modelos

## 2026-05-05 — Substituição de modelos com offloading CPU

### Motivação

Com 8 GB de VRAM (RTX 4060 Max-Q), os modelos originais não cabiam inteiramente na GPU:
- **phi4:14b** — 36% das layers corriam na CPU (13 tok/s)
- **gemma3:12b** — 28% na CPU, usava 92% da VRAM (19 tok/s)
- **qwen3.5:9b-q4_K_M** — 28% na CPU (23 tok/s)

O offloading CPU degrada significativamente a performance:
- Velocidade reduzida (cada layer na CPU é ~3-5x mais lenta)
- Latência de primeiro token mais alta
- Sem margem de VRAM para contextos grandes

### Decisão

Substituir por modelos que correm **100% na GPU** com qualidade equivalente ou superior.

### Substituições realizadas

#### phi4:14b → deepseek-r1:8b

| Métrica | phi4:14b (antigo) | deepseek-r1:8b (novo) |
|---------|-------------------|----------------------|
| VRAM | 6728 MiB (64% GPU) | 6060 MiB (**100% GPU**) |
| Velocidade | 13.4 tok/s | **45.4 tok/s** (+238%) |
| Load time | 18.4s | 3.0s |
| Raciocínio lógico | ⚠️ Contraditório (disse 8, explicou 9) | ✅ Correto |
| Contexto | 4096 (limitado pela VRAM) | **16384** (cabe na GPU) |

**Razão:** DeepSeek-R1 é especializado em raciocínio chain-of-thought (destilado do modelo R1 completo). Mais rápido, mais fiável, e com contexto 4x maior.

#### gemma3:12b → gemma3:4b

| Métrica | gemma3:12b (antigo) | gemma3:4b (novo) |
|---------|--------------------|--------------------|
| VRAM | 7512 MiB (72% GPU) | 4016 MiB (**100% GPU**) |
| Velocidade | 19.9 tok/s | **77.2 tok/s** (+288%) |
| Load time | 11.1s | 2.6s |
| Raciocínio lógico | ✅ Correto | ✅ Correto |
| Português PT | ✅ Muito bom | ✅ Bom |
| Multimodal | ✅ Sim | ✅ Sim |

**Razão:** Mesma família, mantém multimodal (imagens). Velocidade 4x superior. Espaço de VRAM para contextos grandes (16384 tokens). Qualidade PT ligeiramente inferior mas compensada pela velocidade.

#### qwen3.5:9b-q4_K_M → qwen3:8b

| Métrica | qwen3.5:9b (antigo) | qwen3:8b (novo) |
|---------|---------------------|--------------------|
| VRAM | 6136 MiB (72% GPU) | 6060 MiB (**100% GPU**) |
| Velocidade | 23.4 tok/s | **44.9 tok/s** (+92%) |
| Load time | 4.5s | 2.3s |
| Raciocínio lógico | ✅ Correto (mas 120s!) | ✅ Correto (18s) |
| Código | ✅ Bom | ✅ Bom |
| Português PT | ✅ Bom | ✅ Bom |

**Razão:** Qwen3 é a evolução directa do Qwen3.5 (família mais recente, melhor em benchmarks). 8B cabe 100% na GPU. Thinking mode mantido mas mais eficiente. Velocidade quase duplicada.

### Resultado final

| Antes | Depois |
|-------|--------|
| 3 de 4 modelos com offloading CPU | **Todos 100% GPU** |
| Velocidade média: 18 tok/s | **Velocidade média: 52 tok/s** |
| Contexto limitado (4096) | **Contexto 16384 em todos** |
| VRAM sempre no limite | **Margem confortável** |

### Modelos que permaneceram

- **qwen2.5-coder:7b** — já corria 100% GPU (43 tok/s), excelente para código
- **bge-m3** — embeddings, sem necessidade de alteração (1.9 GB VRAM)

### Espaço em disco libertado

- Removidos: ~26.3 GB (phi4:14b 9.1 + gemma3:12b 8.1 + qwen3.5:9b 6.6 + custom derivados)
- Adicionados: ~13.7 GB (deepseek-r1:8b 5.2 + qwen3:8b 5.2 + gemma3:4b 3.3)
- **Ganho líquido: ~12.6 GB de espaço**
