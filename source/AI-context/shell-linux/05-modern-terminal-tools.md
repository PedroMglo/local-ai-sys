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
  - tools
  - modern-cli
---

# 🚀 Shell — Ferramentas Modernas

## Ferramentas Inicializadas no Arranque

Definidas em `05-modern-tools.zsh`, são carregadas via `eval` no startup:

### mise

| | |
|---|---|
| **Função** | Gestor de runtimes e ferramentas (substitui asdf/nvm/pyenv) |
| **Inicialização** | `eval "$(mise activate zsh)"` |
| **Verificar** | `mise --version` |
| **Instalar** | `curl https://mise.run \| sh` |
| **Usar** | `mise install node@20`, `mise use python@3.12` |

### zoxide

| | |
|---|---|
| **Função** | cd inteligente com memória de pastas visitadas |
| **Inicialização** | `eval "$(zoxide init zsh)"` |
| **Verificar** | `zoxide --version` |
| **Instalar** | `mise install zoxide` ou `cargo install zoxide` |
| **Usar** | `z pasta`, `zi` (interativo) |

### direnv

| | |
|---|---|
| **Função** | Carrega variáveis de ambiente automaticamente por projeto |
| **Inicialização** | `eval "$(direnv hook zsh)"` |
| **Verificar** | `direnv version` |
| **Instalar** | `sudo apt install direnv` |
| **Usar** | Criar `.envrc` na raiz do projeto |

### atuin

| | |
|---|---|
| **Função** | Histórico de shell inteligente, sincronizado, pesquisável |
| **Inicialização** | `eval "$(atuin init zsh)"` |
| **Verificar** | `atuin --version` |
| **Instalar** | `curl --proto '=https' --tlsv1.2 -LsSf https://setup.atuin.sh \| sh` |
| **Usar** | `Ctrl+R` (interativo), `hf`, `atuin search <termo>` |

---

## Ferramentas Usadas nos Módulos

### eza (substitui ls)

| | |
|---|---|
| **Função** | Listagem moderna com ícones, cores e git status |
| **Usada em** | 90-aliases.zsh, 26-fzf-power.zsh |
| **Verificar** | `eza --version` |
| **Instalar** | `sudo apt install eza` ou `cargo install eza` |

### fd (substitui find)

| | |
|---|---|
| **Função** | Procura de ficheiros rápida e intuitiva |
| **Usada em** | 26-fzf-power.zsh (ff, cdf) |
| **Verificar** | `fd --version` (nota: no Ubuntu é `fdfind`) |
| **Instalar** | `sudo apt install fd-find` |
| **Nota** | No Ubuntu, o binário chama-se `fdfind`. Criar link: `ln -s $(which fdfind) ~/.local/bin/fd` |

### fzf (fuzzy finder)

| | |
|---|---|
| **Função** | Seleção interativa de texto/ficheiros |
| **Usada em** | 26-fzf-power.zsh |
| **Verificar** | `fzf --version` |
| **Instalar** | `sudo apt install fzf` |

### bat/batcat (substitui cat)

| | |
|---|---|
| **Função** | Visualização de ficheiros com syntax highlighting |
| **Usada em** | 26-fzf-power.zsh, 70-clipboard.zsh |
| **Verificar** | `batcat --version` ou `bat --version` |
| **Instalar** | `sudo apt install bat` |
| **Nota** | No Ubuntu/Debian chama-se `batcat`. Os scripts verificam ambos. |

### ripgrep (rg)

| | |
|---|---|
| **Função** | Grep moderno, muito rápido |
| **Usada em** | Verificada no `doctor` |
| **Verificar** | `rg --version` |
| **Instalar** | `sudo apt install ripgrep` |

### yazi (file manager)

| | |
|---|---|
| **Função** | File manager de terminal com preview |
| **Usada em** | 25-modern-ui.zsh |
| **Verificar** | `yazi --version` |
| **Instalar** | Via cargo: `cargo install --locked yazi-fm yazi-cli` |
| **Config** | `~/.config/yazi/` |

### zellij (multiplexer)

| | |
|---|---|
| **Função** | Terminal multiplexer moderno (substitui tmux) |
| **Usada em** | 25-modern-ui.zsh |
| **Verificar** | `zellij --version` |
| **Instalar** | `cargo install --locked zellij` |
| **Config** | `~/.config/zellij/` |

### lazygit

| | |
|---|---|
| **Função** | Git TUI interativo |
| **Usada em** | 35-daily.zsh |
| **Verificar** | `lazygit --version` |
| **Instalar** | Via mise: `mise install lazygit` |

### btop (substitui top/htop)

| | |
|---|---|
| **Função** | Monitor de recursos do sistema |
| **Usada em** | 35-daily.zsh (alias `top`) |
| **Verificar** | `btop --version` |
| **Instalar** | `sudo apt install btop` |

### starship (prompt)

| | |
|---|---|
| **Função** | Prompt rápido e personalizável |
| **Usada em** | Verificada no `doctor` e `health` |
| **Verificar** | `starship --version` |
| **Instalar** | `curl -sS https://starship.rs/install.sh \| sh` |
| **Config** | `~/.config/starship.toml` |

### fastfetch/neofetch

| | |
|---|---|
| **Função** | Info visual do sistema |
| **Usada em** | 60-info.zsh |
| **Verificar** | `fastfetch --version` |
| **Instalar** | `sudo apt install fastfetch` |

---

## Ferramentas de Conversão

### pandoc

| | |
|---|---|
| **Função** | Conversor universal de documentos |
| **Usada em** | 50-convert.zsh |
| **Verificar** | `pandoc --version` |
| **Instalar** | `sudo apt install pandoc` |

### wkhtmltopdf

| | |
|---|---|
| **Função** | HTML para PDF |
| **Usada em** | 50-convert.zsh (mode html) |
| **Verificar** | `wkhtmltopdf --version` |
| **Instalar** | `sudo apt install wkhtmltopdf` |

### xelatex

| | |
|---|---|
| **Função** | Motor LaTeX para PDF |
| **Usada em** | 50-convert.zsh (mode tex) |
| **Verificar** | `xelatex --version` |
| **Instalar** | `sudo apt install texlive-xetex texlive-fonts-recommended` |

---

## Ferramentas de Sistema

### trash-cli

| | |
|---|---|
| **Função** | Eliminar ficheiros para o lixo (sem rm destrutivo) |
| **Usada em** | 35-daily.zsh |
| **Verificar** | `command -v trash-put` |
| **Instalar** | `sudo apt install trash-cli` |

### qrencode

| | |
|---|---|
| **Função** | Gerar QR codes no terminal |
| **Usada em** | 35-daily.zsh |
| **Verificar** | `command -v qrencode` |
| **Instalar** | `sudo apt install qrencode` |

### ncdu

| | |
|---|---|
| **Função** | Análise de uso de disco interativa |
| **Usada em** | 35-daily.zsh (big) |
| **Verificar** | `command -v ncdu` |
| **Instalar** | `sudo apt install ncdu` |

---

## Verificar todas as ferramentas de uma vez

```zsh
doctor          # mostra estado de todas as ferramentas críticas
```

Ou manualmente:

```zsh
for cmd in mise zoxide direnv atuin fzf fd rg eza batcat yazi zellij lazygit btop starship fastfetch pandoc qrencode ncdu trash-put wl-copy; do
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "✓ $cmd"
  else
    echo "✗ $cmd"
  fi
done
```
