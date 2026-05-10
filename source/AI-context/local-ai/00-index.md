---
type: ai-knowledge
area: local-ai
tags:
  - index
  - meta
---

# 📑 Local AI — Índice

## Visão geral

Sistema de AI local baseado em **Ollama v0.23.0** com GPU NVIDIA RTX 4060 Max-Q (8 GB VRAM).
Otimizado para inferência de modelos até ~9B parâmetros (100% GPU) e até ~14B com offloading CPU/GPU.

## Modelos ativos

| Modelo | Parâmetros | Tamanho | GPU% | Uso principal |
|--------|-----------|---------|------|---------------|
| qwen3:8b | 8B | 5.2 GB | **100% GPU** | Geral, raciocínio, multilingue |
| deepseek-r1:8b | 8B | 5.2 GB | **100% GPU** | Raciocínio profundo (chain-of-thought) |
| qwen2.5-coder:7b | 7B | 4.7 GB | **100% GPU** | Código |
| gemma3:4b | 4B | 3.3 GB | **100% GPU** | Multimodal, ultra-rápido |
| bge-m3 | — | 1.2 GB | **100% GPU** | Embeddings 1024d |

## Modelos custom (com system prompts PT)

| Modelo | Base | Contexto | Temperatura |
|--------|------|----------|-------------|
| qwen3-pt | qwen3:8b | 16384 | 0.7 |
| deepseek-r1-pt | deepseek-r1:8b | 16384 | 0.6 |
| coder-pt | qwen2.5-coder:7b | 16384 | 0.3 |
| gemma3-pt | gemma3:4b | 16384 | 0.7 |

## Performance resumida

| Modelo | Velocidade | Melhor para |
|--------|-----------|-------------|
| gemma3:4b | **77 tok/s** | Multimodal, respostas rápidas |
| qwen2.5-coder:7b | **43 tok/s** | Código rápido |
| deepseek-r1:8b | **45 tok/s** | Raciocínio profundo |
| qwen3:8b | **44 tok/s** | Geral, multilingue |

## Modelos removidos (2026-05-05)

| Modelo | Razão da remoção |
|--------|-----------------|
| phi4:14b | 9.1 GB, 64% GPU / 36% CPU offloading, 13 tok/s. Substituído por deepseek-r1:8b |
| gemma3:12b | 8.1 GB, 72% GPU / 28% CPU, usava 92% VRAM. Substituído por gemma3:4b |
| qwen3.5:9b-q4_K_M | 6.6 GB, 72% GPU / 28% CPU. Substituído por qwen3:8b (evolução da família) |

## Navegação

- [[01-ollama-setup]] — Como está configurado
- [[02-models-inventory]] — Detalhe de cada modelo
- [[03-modelfiles]] — Configurações custom
- [[04-benchmarks]] — Testes comparativos completos
- [[05-vram-management]] — Gestão de memória GPU
- [[06-terminal-usage]] — Como usar no terminal
- [[07-recommendations]] — Sugestões e melhorias
- [[08-troubleshooting]] — Resolver problemas
- [[09-model-changes-log]] — Histórico de alterações de modelos
