---
type: ai-knowledge
area: local-ai
tags:
  - vram
  - gpu
  - memory
  - offloading
  - optimization
---

# 🎮 Gestão de VRAM

## Contexto

- **GPU:** RTX 4060 Max-Q — **8188 MiB VRAM total**
- **VRAM utilizável:** ~7800 MiB (o sistema reserva ~400 MiB para desktop)
- **Flash Attention:** ativo (reduz VRAM por token de contexto)

## Como o Ollama usa a VRAM

1. **Carrega layers do modelo na GPU** (quanto mais layers, mais rápido)
2. **Layers que não cabem vão para RAM/CPU** (offloading — mais lento)
3. **O contexto (KV cache) também ocupa VRAM** — contexto maior = mais VRAM
4. **Flash Attention** reduz o custo do KV cache significativamente

## Mapa de VRAM por modelo

```
8188 MiB total
├── Sistema/Desktop:     ~394 MiB (reservado)
├── Espaço utilizável: ~7794 MiB
│
├── gemma3:4b:         4016 MiB → ✅ 100% GPU (sobram 3778 MiB!)
├── qwen2.5-coder:7b:  5072 MiB → ✅ 100% GPU (sobram 2722 MiB)
├── deepseek-r1:8b:    6060 MiB → ✅ 100% GPU (sobram 1734 MiB)
├── qwen3:8b:          6060 MiB → ✅ 100% GPU (sobram 1734 MiB)
└── bge-m3:            1916 MiB → ✅ 100% GPU
```

## Offloading CPU/GPU

Quando um modelo não cabe totalmente na VRAM:
- As **primeiras layers** ficam na GPU (inferência rápida)
- As **layers restantes** ficam em RAM e usam CPU
- **Impacto:** cada % de CPU offloading reduz velocidade proporcionalmente
- Exemplo: phi4 com 36% CPU → ~13 tok/s vs ~20+ tok/s se coubesse todo

## Otimizações aplicadas

### Flash Attention (`OLLAMA_FLASH_ATTENTION=1`)
- Reduz VRAM do KV cache de O(n²) para O(n)
- Permite contextos maiores sem gastar mais VRAM
- Essencial para esta GPU (8 GB é limitado)

### Max loaded models (`OLLAMA_MAX_LOADED_MODELS=1`)
- Apenas 1 modelo na VRAM de cada vez
- Evita que 2 modelos tentem caber simultaneamente
- Modelo anterior é descarregado antes de carregar novo

### Keep alive (`OLLAMA_KEEP_ALIVE=10m`)
- Modelo descarregado após 10 min inativo
- Liberta VRAM para o desktop/gaming
- Tradeoff: próximo pedido tem cold start

### GPU overhead (`OLLAMA_GPU_OVERHEAD=256m`)
- Ollama reserva menos espaço para "overhead" interno
- Permite mais layers do modelo na GPU
- Safe com Flash Attention ativo

## Contexto vs VRAM

Custo aproximado de VRAM por tamanho de contexto (com Flash Attention):

| Contexto | VRAM extra estimada |
|----------|-------------------|
| 4096 | ~200-400 MiB |
| 8192 | ~400-800 MiB |
| 16384 | ~800-1500 MiB |
| 32768 | ~1500-3000 MiB |

**Implicação:** com qwen2.5-coder (5 GB base), podemos usar contexto 16384 e ainda caber na GPU.
Com gemma3 (7.5 GB base), contexto 4096 já é o limite prático.

## Dicas práticas

1. **Verificar VRAM em tempo real:**
   ```bash
   aistatus    # mostra VRAM + modelo carregado
   nvtop       # monitor interativo
   ai-monitor  # dashboard completo
   ```

2. **Forçar descarregar modelo:**
   ```bash
   ollama stop <modelo>
   ```

3. **Ver split GPU/CPU de um modelo carregado:**
   ```bash
   ollama ps
   ```

4. **Se VRAM não chega:**
   - Reduzir `num_ctx` no Modelfile
   - Usar modelo com quantização mais agressiva (q3_K_S < q4_K_M < q5_K_M)
   - Usar `OLLAMA_NUM_GPU` para forçar número de layers na GPU

## Combinações possíveis

| Cenário | VRAM usada | Funciona? |
|---------|-----------|-----------|
| gemma3:4b + bge-m3 | ~5900 MiB | ✅ Confortável |
| qwen2.5-coder + bge-m3 | ~7000 MiB | ⚠️ Apertado mas possível |
| qwen3 ou deepseek-r1 (ctx 16k) | ~6500 MiB | ✅ |
| gemma3:4b (ctx 16k) | ~5000 MiB | ✅ Muito confortável |
| 2 modelos generativos | >10 GB | ❌ Impossível |
