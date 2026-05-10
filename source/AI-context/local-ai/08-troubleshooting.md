---
type: ai-knowledge
area: local-ai
tags:
  - troubleshooting
  - errors
  - solutions
---

# 🔧 Troubleshooting

## Problemas comuns

### Ollama não responde

**Sintomas:** `connection refused` ao usar `ai` ou `curl localhost:11434`

```bash
# Verificar se o serviço está ativo
systemctl status ollama

# Reiniciar
sudo systemctl restart ollama

# Ver logs de erro
journalctl -u ollama --since "5 min ago"
```

---

### Modelo demora muito a carregar (cold start)

**Causa:** Modelo grande + offloading CPU (phi4:14b demora ~18s)

**Soluções:**
- Aumentar `OLLAMA_KEEP_ALIVE` para `30m` ou `1h` (menos cold starts)
- Usar modelo mais pequeno para tarefas rápidas
- Pré-carregar: `ollama run phi4:14b "" >/dev/null 2>&1 &`

---

### "out of memory" ou modelo não carrega

**Causa:** VRAM insuficiente (outro processo a usar GPU, ou modelo demasiado grande)

```bash
# Verificar o que está a usar VRAM
nvidia-smi

# Descarregar modelo anterior
ollama stop <modelo_anterior>

# Se um jogo/app está a usar VRAM, fechar primeiro
```

---

### Respostas muito lentas (<10 tok/s)

**Causa:** Offloading excessivo para CPU

```bash
# Verificar split GPU/CPU
ollama ps

# Se >40% CPU:
# 1. Reduzir contexto no Modelfile
# 2. Usar quantização mais agressiva
# 3. Fechar apps que usem VRAM
```

---

### Modelo gera texto infinito ou loops

**Causa:** Temperatura alta ou repeat_penalty baixo

**Solução:** Usar Modelfile custom com:
```
PARAMETER repeat_penalty 1.1
PARAMETER temperature 0.7
```

Ou no prompt: adicionar "Responde de forma concisa."

---

### qwen3.5 demora imenso a responder

**Causa:** Modo thinking — o modelo gera milhares de tokens internos antes da resposta

**Soluções:**
- Aceitar (é o preço do raciocínio profundo)
- Para tarefas simples, usar `aiask` (prompt com "máximo 3 frases")
- Usar `qwen2.5-coder` ou `gemma3` para respostas rápidas
- Desativar thinking: adicionar `/no_think` no prompt (se suportado)

---

### Erro "model not found"

```bash
# Listar modelos disponíveis
ollama list

# Se modelo custom não existe, recriar
ollama create qwen3.5-pt -f ~/.ollama/modelfiles/qwen3.5-pt.Modelfile
```

---

### GPU não é usada (0% GPU no nvidia-smi)

**Causas possíveis:**
- CUDA não disponível no Ollama
- Driver NVIDIA desatualizado

```bash
# Verificar CUDA
nvidia-smi  # deve mostrar "CUDA Version: 13.0"

# Verificar se Ollama vê a GPU
ollama ps  # deve mostrar "GPU" no Processor

# Se necessário, reinstalar Ollama
curl -fsSL https://ollama.com/install.sh | sh
```

---

### Espaço em disco a acabar

```bash
# Ver espaço dos modelos
ollama list  # mostra tamanho de cada um

# Remover modelos não usados
ollama rm nomic-embed-text  # exemplo

# Ver espaço total
df -h /
```

---

## Comandos de diagnóstico

| Comando | O que verifica |
|---------|---------------|
| `systemctl status ollama` | Serviço ativo? |
| `ollama list` | Modelos instalados |
| `ollama ps` | Modelos carregados + GPU/CPU split |
| `nvidia-smi` | VRAM, temperatura, processos GPU |
| `nvtop` | Monitor GPU interativo |
| `aistatus` | Resumo rápido (modelo + VRAM) |
| `journalctl -u ollama -f` | Logs em tempo real |
| `curl localhost:11434` | API acessível? |

## Contactos úteis

- [Ollama GitHub](https://github.com/ollama/ollama)
- [Ollama Models Library](https://ollama.com/library)
- [NVIDIA Driver Downloads](https://www.nvidia.com/drivers)
