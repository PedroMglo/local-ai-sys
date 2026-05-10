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
  - aliases
---

# 🔗 Shell — Aliases

## Aliases de Navegação

| Alias | Comando | Ficheiro | Descrição |
|-------|---------|----------|-----------|
| `c` | `clear` | 35-daily.zsh | Limpar terminal |
| `home` | `cd ~` | 35-daily.zsh | Ir para home |
| `dl` | `cd ~/Downloads` | 35-daily.zsh | Ir para Downloads |
| `docs` | `cd ~/Documents` | 35-daily.zsh | Ir para Documents |
| `desk` | `cd ~/Desktop` | 35-daily.zsh | Ir para Desktop |
| `proj` | `cd ~/_Projects` | 35-daily.zsh | Ir para projetos |

---

## Aliases de Listagem (eza)

| Alias | Comando | Ficheiro | Descrição |
|-------|---------|----------|-----------|
| `ls` | `eza --group-directories-first --icons=auto` | 90-aliases.zsh | Listagem básica |
| `l` | `eza -lh --group-directories-first --icons=auto --git` | 90-aliases.zsh | Listagem longa (sem ocultos) |
| `ll` | `eza -lh --group-directories-first --icons=auto --git` | 90-aliases.zsh | Listagem longa (sem ocultos) |
| `la` | `eza -lah --group-directories-first --icons=auto --git` | 90-aliases.zsh | Listagem longa com ocultos |
| `lt` | `eza --tree --level=2 --icons=auto --group-directories-first` | 90-aliases.zsh | Árvore 2 níveis |
| `lta` | `eza --tree --level=3 --icons=auto --group-directories-first -a` | 90-aliases.zsh | Árvore 3 níveis com ocultos |

---

## Aliases de Python/uv

| Alias | Comando | Ficheiro | Descrição |
|-------|---------|----------|-----------|
| `uvp` | `uv pip` | 20-navigation.zsh | Gestor de pacotes uv |
| `uvr` | `uv run` | 20-navigation.zsh | Executar com uv |

---

## Aliases de Sistema

| Alias | Comando | Ficheiro | Descrição |
|-------|---------|----------|-----------|
| `top` | `btop` | 35-daily.zsh | Monitor de processos moderno |
| `disk` | `df -h` | 35-daily.zsh | Uso de disco |
| `mem` | `free -h` | 35-daily.zsh | Memória RAM |
| `path` | `print -l ${(s/:/)PATH}` | 35-daily.zsh | PATH linha a linha |

---

## Aliases de Segurança

| Alias | Comando | Ficheiro | Condição | Descrição |
|-------|---------|----------|----------|-----------|
| `del` | `trash-put` | 35-daily.zsh | Se `trash-put` existe | Apagar para o lixo |
| `trash-list` | `trash-list` | 35-daily.zsh | Se `trash-put` existe | Listar lixo |
| `trash-empty` | `trash-empty` | 35-daily.zsh | Se `trash-put` existe | Esvaziar lixo |

---

## Aliases de UI/Sessões

| Alias | Comando | Ficheiro | Descrição |
|-------|---------|----------|-----------|
| `zj` | `zellij` | 25-modern-ui.zsh | Abrir Zellij |
| `zjl` | `zellij list-sessions` | 25-modern-ui.zsh | Listar sessões |
| `zjd` | `zellij --layout daily` | 25-modern-ui.zsh | Layout diário |

---

## Aliases de Ajuda

| Alias | Comando | Ficheiro | Descrição |
|-------|---------|----------|-----------|
| `helpz` | `zhelp_custom` | 90-aliases.zsh | Ajuda geral |
| `shellinfo` | `show_startup_info` | 90-aliases.zsh | Info do shell |

---

## Aliases de Git

| Alias | Comando | Ficheiro | Descrição |
|-------|---------|----------|-----------|
| `lg` | `lazygit` | 35-daily.zsh | Git TUI |

---

## Exemplos Práticos

```zsh
# Navegar rapidamente
proj          # vai para ~/_Projects
dl            # vai para ~/Downloads

# Listagens detalhadas
l             # listagem completa com git status
lt            # árvore de 2 níveis
lta           # árvore de 3 níveis (incluindo ocultos)

# Apagar com segurança
del ficheiro.txt    # vai para o lixo, não apaga definitivamente
trash-list          # ver o que está no lixo
trash-empty         # esvaziar o lixo

# Sessões Zellij
zjd           # abre layout diário
zjl           # lista sessões ativas
```

| `duck` | `duckdb` | 45-data-engineering.zsh | Abrir DuckDB |
| `duckm` | `duckdb :memory:` | 45-data-engineering.zsh | DuckDB em memória |

---

## ⚠️ Possíveis Conflitos

| Alias | Conflito | Notas |
|-------|----------|-------|
| `ls` | Substitui `/usr/bin/ls` | Usa `command ls` para aceder ao original |
| `top` | Substitui `/usr/bin/top` | Usa `command top` para aceder ao original |
