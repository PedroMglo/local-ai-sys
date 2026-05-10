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
  - dotfiles
---

# 🧠 Shell — Índice Principal

## Sobre este setup

Configuração modular Zsh organizada em `~/.zsh_custom.d/`, com 19 ficheiros carregados por ordem numérica. Usa ferramentas modernas (eza, fzf, zoxide, atuin, yazi, zellij, starship) num sistema Zorin/Ubuntu com GPU NVIDIA híbrida, cloud mounts via rclone e modelos AI locais via Ollama.

---

## 📚 Documentação

| # | Documento | Conteúdo |
|---|-----------|----------|
| 01 | [[01-shell-overview]] | Visão geral, ordem de carregamento, dependências |
| 02 | [[02-aliases]] | Todos os aliases definidos |
| 03 | [[03-functions]] | Todas as funções Zsh |
| 04 | [[04-navigation-and-files]] | Navegação, yazi, fzf, zoxide |
| 05 | [[05-modern-terminal-tools]] | Ferramentas modernas instaladas |
| 06 | [[06-git-and-dotfiles]] | Git, dotfiles, backups |
| 07 | [[07-gpu-nvidia]] | GPU NVIDIA, prime-run, jogos |
| 08 | [[08-rclone-cloud]] | Rclone, mounts, cloud |
| 09 | [[09-clipboard]] | Clipboard Wayland/X11 |
| 10 | [[10-maintenance]] | Manutenção, atualizações, limpeza |
| 11 | [[11-cheatsheet]] | Cheat sheet rápido |
| 12 | [[12-troubleshooting]] | Erros e soluções |
| 13 | [[13-ai-local]] | AI local — Ollama, funções ol/aicode/aiask |
| 14 | [[14-data-engineering]] | Data Engineering — DuckDB, Parquet, CSV |

---

## 🗂️ Mapa dos ficheiros `.zsh`

```
~/.zsh_custom.d/
├── 00-core.zsh           → Helpers internos (_err, _wants_help, etc.)
├── 05-modern-tools.zsh   → PATH, mise, zoxide, direnv, atuin
├── 10-help.zsh           → Sistema de ajuda (zhelp_custom, reloadz, myz)
├── 20-navigation.zsh     → Navegação (drives, venvs, mkcd, uv helpers)
├── 25-modern-ui.zsh      → Yazi + Zellij
├── 26-fzf-power.zsh      → FZF helpers (ff, cdf, vf, bf, hf)
├── 30-rclone.zsh         → Cloud mounts (rclone services)
├── 35-daily.zsh          → Comandos diários (op, take, up, ports, extract, etc.)
├── 40-gpu.zsh            → NVIDIA GPU helpers
├── 42-ai.zsh             → AI local (ol, aicode, aiask, aimodels, Ollama + RAG proxy)
├── 45-data-engineering.zsh → DuckDB/Parquet helpers (duckpq, pqschema, csv2pq, etc.)
├── 50-convert.zsh        → Conversão de ficheiros (com validação de saída)
├── 60-info.zsh           → Info do shell e sistema (shellinfo)
├── 70-clipboard.zsh      → Clipboard (cpath, ccat)
├── 80-dotfiles.zsh       → Dotfiles sync/backup (com confirmação e erros)
├── 85-maintenance.zsh    → Manutenção do sistema (health, updateall, cleanup)
├── 90-aliases.zsh        → Aliases finais (eza, helpz, etc.)
├── 95-completions.zsh    → Auto-completions personalizados
└── 95-copilot-context.zsh → copilotctx — Copilot CLI com contexto do Vault
```

---

## 🔑 Comandos essenciais

- `helpz` — ajuda geral do toolkit
- `shellinfo` — resumo do contexto do shell
- `reloadz` — recarregar configuração
- `myz <módulo>` — editar módulo específico
- `doctor` — diagnóstico rápido
- `dotup "msg"` — guardar configs no GitHub

---

## 📍 Caminhos importantes

| Caminho | Descrição |
|---------|-----------|
| `~/.zshrc` | Configuração principal Zsh |
| `~/.zsh_custom.d/` | Módulos personalizados |
| `~/.config/starship.toml` | Prompt Starship |
| `~/.config/yazi/` | File manager Yazi |
| `~/.config/zellij/` | Terminal multiplexer |
| `~/dotfiles/` | Repositório Git de dotfiles |
| `~/Drives/OneDrive/` | OneDrive via rclone |
| `~/Drives/GoogleDrive/` | Google Drive via rclone |
| `~/_Projects/` | Projetos |
| `~/venvs/` | Ambientes virtuais Python |
| `~/Notes/terminal/` | Notas rápidas mensais |
