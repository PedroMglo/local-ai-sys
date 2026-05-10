---
type: ai-knowledge
area: local-ai
tags:
  - modelfiles
  - configuration
  - system-prompts
---

# 📝 Modelfiles Personalizados

## Localização

```
~/.ollama/modelfiles/
├── qwen3-pt.Modelfile
├── deepseek-r1-pt.Modelfile
├── coder-pt.Modelfile
└── gemma3-pt.Modelfile
```

## qwen3-pt (default para uso geral)

```dockerfile
FROM qwen3:8b

PARAMETER num_ctx 16384
PARAMETER temperature 0.7
PARAMETER top_p 0.9

SYSTEM """Tu és um assistente inteligente. Respondes em português de Portugal, de forma clara, precisa e prática. Quando o tema for técnico (programação, Linux, data engineering), dás exemplos de código ou comandos prontos a usar."""
```

**Notas:**
- Contexto 16384 — cabe na VRAM com 100% GPU + Flash Attention
- Temperatura 0.7 — equilibrio criatividade/precisão
- System prompt em PT com foco prático

## deepseek-r1-pt (raciocínio profundo)

```dockerfile
FROM deepseek-r1:8b

PARAMETER num_ctx 16384
PARAMETER temperature 0.6
PARAMETER top_p 0.9

SYSTEM """Tu és um assistente de raciocínio profundo. Pensas passo a passo, analisas múltiplas perspectivas, e dás respostas estruturadas e completas. Respondes em português de Portugal."""
```

**Notas:**
- Chain-of-thought nativo — pensa passo a passo automaticamente
- Temperatura 0.6 — raciocínio mais focado
- Contexto 16384 — cabe confortavelmente na GPU

## coder-pt (código)

```dockerfile
FROM qwen2.5-coder:7b

PARAMETER num_ctx 16384
PARAMETER temperature 0.3
PARAMETER top_p 0.85

SYSTEM """Tu és um assistente especializado em programação. Respondes com código limpo, bem comentado e funcional. Preferes Python, SQL, Bash e TypeScript. Explicas brevemente o que o código faz. Respondes em português de Portugal quando a explicação não é código."""
```

**Notas:**
- Contexto 16384 — permite ficheiros grandes em pipe
- Temperatura baixa (0.3) — código mais determinístico
- Cabe 100% na GPU mesmo com contexto grande (Flash Attention)

## gemma3-pt (multimodal rápido)

```dockerfile
FROM gemma3:4b

PARAMETER num_ctx 16384
PARAMETER temperature 0.7
PARAMETER top_p 0.9

SYSTEM """Tu és um assistente versátil. Respondes em português de Portugal, de forma clara e concisa. Suportas análise de imagens quando fornecidas."""
```

**Notas:**
- Ultra-rápido (77 tok/s) — ideal para respostas rápidas
- Multimodal: suporta imagens
- VRAM baixa (4 GB) — margem enorme para contexto

## Como criar/atualizar modelos custom

```bash
# Criar modelo a partir de Modelfile
ollama create qwen3.5-pt -f ~/.ollama/modelfiles/qwen3.5-pt.Modelfile

# Verificar que foi criado
ollama list | grep "pt\|deep"

# Testar
ollama run qwen3.5-pt "Olá, testa em português"

# Remover modelo custom (não afeta o base)
ollama rm qwen3.5-pt
```

## Criar novo Modelfile

Template:
```dockerfile
FROM <modelo-base>

PARAMETER num_ctx <contexto>
PARAMETER temperature <0.0-1.0>
PARAMETER top_p <0.0-1.0>
PARAMETER repeat_penalty <1.0-1.5>

SYSTEM """<system prompt>"""
```

Parâmetros úteis:
- `num_ctx` — tamanho do contexto (tokens). Mais = mais VRAM
- `temperature` — aleatoriedade (0 = determinístico, 1 = criativo)
- `top_p` — nucleus sampling
- `repeat_penalty` — penaliza repetições (1.1 é bom default)
- `num_gpu` — forçar número de layers na GPU (avançado)
