---
type: ai-knowledge
area: local-ai
tags:
  - recommendations
  - models
  - upgrades
  - best-practices
---

# 💡 Recomendações e Boas Práticas

## Modelos recomendados por tarefa

### Setup atual (todos 100% GPU)

| Tarefa | Modelo | Razão |
|--------|--------|-------|
| Chat diário | qwen3-pt | 44 tok/s, thinking mode, multilingue |
| Código rápido | coder-pt | 43 tok/s, especializado |
| Raciocínio profundo | deepseek-r1-pt | 45 tok/s, chain-of-thought |
| Respostas rápidas | gemma3-pt | 77 tok/s, multimodal |
| Português PT | qwen3-pt | Melhor qualidade PT-PT |
| Embeddings/RAG | bge-m3 | 1024 dimensões, multilíngue |

### Modelos sugeridos para experimentar

| Modelo | Tamanho | Porquê | Comando |
|--------|---------|--------|---------|
| deepseek-r1:7b | ~4.7 GB | Raciocínio tipo o1, cabe na GPU | `ollama pull deepseek-r1:7b` |
| llava:7b | ~4.7 GB | Multimodal (imagens) leve | `ollama pull llava:7b` |
| gemma3:4b | ~3 GB | Multimodal ultra-rápido | `ollama pull gemma3:4b` |
| qwen2.5-coder:14b-q3_K_S | ~6 GB | Código mais inteligente, cabe | `ollama pull qwen2.5-coder:14b-q3_K_S` |
| mistral:7b | ~4 GB | Generalista rápido | `ollama pull mistral:7b` |

### Modelos a evitar (nesta GPU)

| Modelo | Razão |
|--------|-------|
| Qualquer >14B sem quantização agressiva | Offloading >50% CPU, demasiado lento |
| Modelos Q8 ou FP16 de >7B | Não cabem na VRAM |
| Mixtral/Qwen-72B/Llama-70B | Impossível com 8 GB VRAM |

## Boas Práticas

### Performance

1. **Usar o modelo certo para cada tarefa** — não usar phi4 para código simples
2. **Preferir modelos que cabem 100% na GPU** — qwen2.5-coder é 3x mais rápido que phi4
3. **Descarregar modelo quando não usar** — liberta VRAM para desktop/gaming
4. **Flash Attention sempre ativo** — já configurado no systemd override
5. **Contexto proporcional ao necessário** — não usar 32k se 4k chega

### Qualidade

1. **Para raciocínio complexo** — qwen3.5 com thinking mode (aceitar que demora)
2. **Para código** — coder-pt com temperatura baixa (0.3)
3. **Para PT-PT correto** — gemma3:12b
4. **Para resumos/análise** — phi4-deep com temperatura 0.6
5. **Validar sempre código gerado** — executar e testar antes de usar

### Embeddings e RAG

1. **bge-m3 > nomic-embed-text** — melhor qualidade multilíngue
2. **Usar batch processing** — mais eficiente que individual
3. **1024 dimensões** — bom equilíbrio qualidade/storage
4. **Normalizar embeddings** antes de cosine similarity

### Manutenção

1. **Actualizar Ollama regularmente** — `curl -fsSL https://ollama.com/install.sh | sh`
2. **Verificar novos modelos** — Ollama library actualiza frequentemente
3. **Monitorizar VRAM** — `aistatus` ou `nvtop`
4. **Limpar modelos não usados** — `ollama rm <modelo>`
5. **Verificar espaço** — modelos ocupam ~30 GB total

## Upgrades futuros

### Se fizer upgrade de GPU (>= 12 GB VRAM)
- phi4:14b e gemma3:12b ficam 100% GPU
- Possível correr modelos 20B+ quantizados
- Contextos de 32k+ tornam-se práticos
- Dois modelos em simultâneo

### Se adicionar RAM (64 GB)
- Offloading CPU fica mais rápido (mais bandwidth)
- Datasets maiores em DuckDB sem spill
- Mais containers Docker em simultâneo

### Software

| Melhoria | Quando | Impacto |
|----------|--------|---------|
| Ollama com speculative decoding | Quando suportado | +30-50% velocidade |
| Modelos Qwen 3.5 menores (4B) | Quando disponíveis | Thinking mode ultra-rápido |
| GGUF com importance matrix | Melhores quantizações | Melhor qualidade/tamanho |

## Limitações a aceitar

- 8 GB VRAM é o bottleneck — mas todos os modelos actuais cabem 100%
- Modo thinking do qwen3 pode ser verboso (gera tokens internos)
- Para modelos >8B seria necessário offloading CPU (evitado com o setup actual)
- Inferência nunca será tão rápida como APIs cloud (mas é privada e gratuita)
