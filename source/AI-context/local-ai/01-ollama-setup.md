---
type: ai-knowledge
area: local-ai
tags:
  - ollama
  - setup
  - systemd
  - configuration
---

# ⚙️ Ollama — Setup e Configuração

## Instalação

- **Versão:** Ollama 0.23.0
- **Binário:** `/usr/local/bin/ollama`
- **Service:** systemd (`ollama.service`)
- **User:** `ollama` (dedicado)
- **Modelos:** armazenados pelo serviço (geridos por `ollama pull/rm`)

## Serviço systemd

### Ficheiro principal
```
/usr/lib/systemd/system/ollama.service
```

### Override de otimização (criado 2026-05-04)
```
/etc/systemd/system/ollama.service.d/override.conf
```

```ini
[Service]
Environment="OLLAMA_FLASH_ATTENTION=1"
Environment="OLLAMA_MAX_LOADED_MODELS=1"
Environment="OLLAMA_NUM_PARALLEL=2"
Environment="OLLAMA_KEEP_ALIVE=10m"
Environment="OLLAMA_GPU_OVERHEAD=256m"
Environment="OLLAMA_HOST=0.0.0.0:11434"
```

### Explicação das variáveis

| Variável | Valor | Razão |
|----------|-------|-------|
| OLLAMA_FLASH_ATTENTION | 1 | Reduz VRAM, permite contextos maiores |
| OLLAMA_MAX_LOADED_MODELS | 1 | Com 8GB VRAM, apenas 1 modelo de cada vez |
| OLLAMA_NUM_PARALLEL | 2 | Permite 2 requests simultâneos |
| OLLAMA_KEEP_ALIVE | 10m | Descarrega modelo após 10 min sem uso |
| OLLAMA_GPU_OVERHEAD | 256m | Reserva menos VRAM para overhead |
| OLLAMA_HOST | 0.0.0.0:11434 | Aceita conexões de qualquer interface |

## Comandos de gestão

```bash
# Estado do serviço
systemctl status ollama

# Reiniciar (após alterar override)
sudo systemctl daemon-reload && sudo systemctl restart ollama

# Logs
journalctl -u ollama -f

# Editar override
sudo systemctl edit ollama
```

## API REST

- **URL:** `http://localhost:11434`
- **Gerar texto:** `POST /api/generate`
- **Chat:** `POST /api/chat`
- **Embeddings:** `POST /api/embed`
- **Listar modelos:** `GET /api/tags`
- **Modelo carregado:** `GET /api/ps`

## Monitorização

```bash
# Ver modelos carregados + VRAM
aistatus

# Monitor GPU live
nvtop

# Dashboard completo (VRAM + RAM + CPU + Ollama)
ai-monitor
```

## Localização dos dados

- Modelos: geridos pelo user `ollama` (em `/usr/share/ollama/.ollama/` ou path do serviço)
- Modelfiles custom: `~/.ollama/modelfiles/`
- Histórico CLI: `~/.ollama/history`
