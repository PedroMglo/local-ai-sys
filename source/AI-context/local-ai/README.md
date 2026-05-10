---
type: ai-knowledge
area: local-ai
system: ollama
created_by: github-copilot-cli
tags:
  - ai
  - ollama
  - llm
  - local
  - gpu
  - nvidia
  - inference
  - embeddings
  - terminal
---

# 🤖 Local AI — Knowledge Base

## O que é esta pasta

Base de conhecimento sobre a configuração de AI local (Ollama) nesta máquina. Inclui documentação de modelos, benchmarks de performance, configuração do sistema, e workflows de utilização via terminal.

## Como foi gerada

- **Data:** 2026-05-04
- **Ferramenta:** GitHub Copilot CLI (Claude Opus 4.6)
- **Método:** Análise da configuração Ollama + benchmarks reais em todos os modelos
- **Benchmarks corridos a frio** (modelo descarregado antes de cada teste)

## Hardware relevante

| Recurso | Valor |
|---------|-------|
| GPU | NVIDIA RTX 4060 Max-Q (8 GB VRAM) |
| CPU | 24 threads x86_64 |
| RAM | 32 GB DDR |
| Disco | NVMe ~745 GB |
| CUDA | 13.0 |
| Driver | 580.126.09 |

## Ficheiros

| Ficheiro | Conteúdo |
|----------|----------|
| 00-index.md | Índice e visão geral |
| 01-ollama-setup.md | Instalação, configuração, systemd |
| 02-models-inventory.md | Modelos instalados: specs, quantização, uso ideal |
| 03-modelfiles.md | Modelfiles custom (system prompts, parâmetros) |
| 04-benchmarks.md | Resultados comparativos de performance |
| 05-vram-management.md | Gestão de VRAM, offloading CPU/GPU |
| 06-terminal-usage.md | Aliases Zsh, funções, workflows |
| 07-recommendations.md | Boas práticas, modelos sugeridos |
| 08-troubleshooting.md | Problemas comuns e soluções |
| 09-model-changes-log.md | Histórico de alterações e razões |

## Quando consultar

Consultar esta pasta quando o pedido envolver:
- Ollama, modelos locais, LLMs
- Inferência local, VRAM, GPU para AI
- Embeddings, RAG, busca semântica
- Performance de modelos, tokens/s
- Aliases `ai`, `aicode`, `aiask`, `aistatus`
- Configuração Ollama, Modelfiles
