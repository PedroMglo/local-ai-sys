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

# 🔭 Shell — Visão Geral

## Objetivo

Setup modular Zsh focado em produtividade no terminal, com ferramentas modernas que substituem utilitários clássicos. Organizado em ficheiros numerados para controlar a ordem de carregamento.

---

## Ordem de Carregamento

Os ficheiros são carregados por ordem numérica pelo `.zshrc`:

| Ordem | Ficheiro | Objetivo |
|-------|----------|----------|
| 1 | `00-core.zsh` | Funções internas de suporte |
| 2 | `05-modern-tools.zsh` | PATH, inicialização de ferramentas |
| 3 | `10-help.zsh` | Sistema de ajuda, reloadz, myz |
| 4 | `20-navigation.zsh` | Funções de navegação, venvs e uv helpers |
| 5 | `25-modern-ui.zsh` | Yazi e Zellij |
| 6 | `26-fzf-power.zsh` | Helpers FZF |
| 7 | `30-rclone.zsh` | Cloud mounts |
| 8 | `35-daily.zsh` | Comandos do dia a dia + extract |
| 9 | `40-gpu.zsh` | NVIDIA GPU |
| 10 | `42-ai.zsh` | AI local — Ollama (ol, aicode, aiask, aimodels, aistatus, aiembed) |
| 11 | `45-data-engineering.zsh` | Data Engineering — DuckDB, Parquet (duckpq, pqschema, csv2pq, etc.) |
| 12 | `50-convert.zsh` | Conversão de ficheiros (com validação) |
| 13 | `60-info.zsh` | Info do sistema/shell |
| 14 | `70-clipboard.zsh` | Clipboard (cpath, ccat) |
| 15 | `80-dotfiles.zsh` | Gestão de dotfiles (com confirmação) |
| 16 | `85-maintenance.zsh` | Manutenção do sistema (sem sudo em health) |
| 17 | `90-aliases.zsh` | Aliases finais |
| 18 | `95-completions.zsh` | Auto-completions personalizados |
| 19 | `95-copilot-context.zsh` | Copilot CLI com contexto do Vault (copilotctx) |

> **Nota:** A ordem é importante. O `00-core.zsh` define helpers como `_err` e `_wants_help` que são usados por todos os outros ficheiros.

---

## Dependências Principais

### Ferramentas obrigatórias (inicializadas no arranque)

| Ferramenta | Papel | Inicializada em |
|------------|-------|-----------------|
| mise | Gestor de runtimes/ferramentas | 05-modern-tools.zsh |
| zoxide | cd inteligente com memória | 05-modern-tools.zsh |
| direnv | Variáveis de ambiente por projeto | 05-modern-tools.zsh |
| atuin | Histórico inteligente de comandos | 05-modern-tools.zsh |

### Ferramentas usadas como dependência

| Ferramenta | Usada por | Função |
|------------|-----------|--------|
| fzf | ff, cdf, vf, bf | Seleção interativa |
| fd | ff, cdf | Procura de ficheiros |
| eza | aliases ls/l/ll/la/lt | Listagens modernas |
| batcat/bat | ff, bf, ccat | Visualização com syntax |
| yazi | y | File manager terminal |
| zellij | zj, zjm, zjd | Terminal multiplexer |
| lazygit | lg | Git TUI |
| btop | top | Monitor de processos |
| starship | prompt | Prompt moderno |
| rsync | dotsync, dotapply | Sincronização de ficheiros |
| rclone | mounts, rclone_* | Cloud storage |
| trash-put | del | Eliminação segura |
| wl-copy/xclip | cpath, ccat | Clipboard |

### Ferramentas opcionais

| Ferramenta | Usada por | Fallback |
|------------|-----------|----------|
| ncdu | big | du + sort |
| fastfetch | sysinfo | neofetch |
| qrencode | qrcode | — |
| pandoc | convert_file | — |
| wkhtmltopdf | convert_file (html mode) | — |
| xelatex | convert_file (tex mode) | — |
| libreoffice | convert_file (doc/odt) | — |

---

## Padrão de Design

Todas as funções seguem o mesmo padrão:

```zsh
function nome {
  # 1. Suporte a --help
  if _wants_help "$1"; then
    cat <<'EOF2'
    ...documentação...
EOF2
    return 0
  fi

  # 2. Validação de argumentos
  [[ -z "$1" ]] && { _err "Uso: ..."; return 2; }

  # 3. Verificação de dependências
  command -v ferramenta >/dev/null 2>&1 || { _err "..."; return 127; }

  # 4. Lógica principal
  ...
}
```

---

## Variáveis de Ambiente Definidas

| Variável | Valor | Ficheiro |
|----------|-------|----------|
| `PATH` | Inclui `~/.local/bin` e mise shims | 05-modern-tools.zsh |
| `DOTFILES_DIR` | `$HOME/dotfiles` | 80-dotfiles.zsh |

---

## Integrações entre ficheiros

- `26-fzf-power.zsh` depende de `fd` e `batcat` (que devem estar disponíveis via `05-modern-tools.zsh` / mise)
- `25-modern-ui.zsh` usa `yazi` e `zellij` como comandos externos
- `80-dotfiles.zsh` usa `_dotfiles_require_repo` que verifica `$DOTFILES_DIR/.git`
- `40-gpu.zsh` começa com `unalias gpu` para evitar conflitos
- `90-aliases.zsh` é carregado por último para ter a palavra final nos aliases
