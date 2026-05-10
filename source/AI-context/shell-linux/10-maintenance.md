---
type: shell-knowledge
area: linux
system: zsh
source: ~/.zsh_custom.d
created_by: github-copilot-cli
tags:
  - linux
  - zsh
  - shell
  - terminal
  - maintenance
  - updates
  - cleanup
---

# 🔧 Shell — Manutenção

## Comandos de Manutenção

Definidos em: `85-maintenance.zsh`

---

## `health` — Resumo do Sistema

```zsh
health
```

Mostra:
- Hostname e uptime
- Uso de disco (/ e /home)
- Memória RAM
- Top 10 pastas em ~
- Portas em escuta
- Estado dos dotfiles
- Versão do Zsh
- Ferramentas instaladas (starship, atuin, yazi, zellij, mise)

---

## `updateall` — Atualizar Tudo

```zsh
updateall
```

Executa sequencialmente:

| Passo | Comando | Condição |
|-------|---------|----------|
| 1 | `sudo apt update && sudo apt upgrade -y` | Sempre |
| 2 | `flatpak update -y` | Se flatpak instalado |
| 3 | `mise upgrade -y` | Se mise instalado |
| 4 | `zinit self-update` + `zinit update` | Se zinit instalado |
| 5 | OMZ `upgrade.sh` | Se `~/.oh-my-zsh` existe |

**⚠️ Requer:** sudo (para apt)
**⏱️ Duração:** Pode demorar vários minutos

---

## `cleanup` — Limpeza do Sistema

```zsh
cleanup
```

Executa:

| Passo | Ação | Risco |
|-------|------|-------|
| 1 | `sudo apt autoremove -y` | Baixo — remove pacotes órfãos |
| 2 | `sudo apt autoclean` | Baixo — limpa cache apt |
| 3 | Remove `~/.cache/thumbnails/*` | Nenhum |
| 4 | Remove `~/.cache/yarn/*` | Nenhum |
| 5 | Remove `~/.npm/_cacache/` | Baixo — npm recria |
| 6 | `sudo journalctl --vacuum-time=14d` | Baixo — mantém 14 dias de logs |

**⚠️ Nota:** Não esvazia o lixo automaticamente (apenas sugere `trash-empty`).

---

## `doctor` — Diagnóstico Rápido

```zsh
doctor
```

Verifica:
1. **Tempo de arranque** da shell (`time zsh -i -c exit`)
2. **Comandos críticos** — se estão instalados:
   - zsh, starship, mise, atuin, zoxide, direnv, fzf, fd, rg, eza, batcat, yazi, zellij, lazygit, btop, git, gh
3. **Dotfiles** — repo existe, remote, status
4. **Prompt** — `starship explain`

---

## Fluxo Recomendado de Manutenção

### Manutenção semanal

```zsh
updateall       # atualiza tudo
cleanup         # limpa caches
doctor          # verifica se tudo funciona
dotup "Weekly maintenance"   # guarda configs
```

### Diagnóstico rápido

```zsh
health          # visão geral do sistema
doctor          # verifica ferramentas
```

### Após instalar algo novo

```zsh
doctor          # confirmar que está no PATH
reloadz         # recarregar shell se necessário
```

---

## Comandos Seguros vs Perigosos

### ✅ Seguros

| Comando | Descrição |
|---------|-----------|
| `health` | Apenas lê informação |
| `doctor` | Apenas verifica |
| `dotstatus` | Apenas mostra git status |
| `mounts` | Apenas lista |
| `rclone_status` | Apenas mostra estado |

### ⚠️ Requerem atenção

| Comando | Risco | Mitigação |
|---------|-------|-----------|
| `updateall` | Pode atualizar pacotes com breaking changes | Verificar changelog antes |
| `cleanup` | Remove caches que podem ser úteis | Caches são recriados |
| `reloadz` | Pode falhar se .zshrc tiver erros | Ter terminal extra aberto |
| `rclone_restart` | Desmonta pastas temporariamente | Fechar ficheiros abertos no mount |

### ⛔ Perigosos (não existem no toolkit, mas atenção)

| Comando | Risco |
|---------|-------|
| `rm -rf ~/` | Elimina tudo |
| `dotapply` (sem backup) | Sobrescreve configs locais |
| `trash-empty` | Irreversível |
| `portkill` (porta errada) | Pode matar serviço crítico |

---

## Logs e Diagnóstico

### Ver logs do sistema

```zsh
journalctl --user -f               # logs do utilizador em tempo real
journalctl -b -p err               # erros desde o último boot
```

### Ver tempo de arranque do Zsh

```zsh
time zsh -i -c exit                # tempo total
zsh -xv 2>&1 | head -n 100        # trace detalhado (debug)
```

### Verificar espaço em disco

```zsh
disk            # df -h
big ~           # análise detalhada com ncdu
```
