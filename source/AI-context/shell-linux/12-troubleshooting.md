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
  - troubleshooting
  - debug
---

# 🔍 Shell — Troubleshooting

## Shell lenta ao abrir

### Sintomas
- Terminal demora mais de 1-2 segundos a ficar pronto
- Prompt aparece com atraso

### Diagnóstico
```zsh
time zsh -i -c exit              # medir tempo total
zsh -xv 2>&1 | head -n 200      # trace detalhado
```

### Causas comuns
1. **atuin init** lento — verificar conectividade (sync remoto)
2. **mise activate** lento — muitas ferramentas instaladas
3. **starship** lento — muitos módulos ativos
4. **oh-my-zsh** com plugins pesados

### Soluções
- Desativar ferramentas temporariamente para isolar
- Verificar `~/.config/starship.toml` para módulos desnecessários
- Usar `mise activate --shims` em vez de `eval`

---

## Comando não encontrado

### Sintomas
- `command not found: <nome>`

### Diagnóstico
```zsh
which <nome>                     # onde está definido
type <nome>                      # que tipo é (alias, function, etc.)
command -v <nome>                # caminho do binário
echo $PATH | tr ':' '\n'         # ver PATH
```

### Causas comuns
1. **Ferramenta não instalada** — `doctor` mostra ✗
2. **PATH incompleto** — `~/.local/bin` não incluído
3. **mise shims desatualizados** — `mise reshim`
4. **Shell não recarregada** — `reloadz`

### Soluções
```zsh
doctor                           # ver o que falta
mise install <ferramenta>        # instalar via mise
reloadz                          # recarregar
```

---

## `reloadz` causa erros

### Sintomas
- Erros de syntax ao recarregar
- Funções desaparecem
- PATH fica corrompido

### Diagnóstico
```zsh
zsh -n ~/.zshrc                  # verificar syntax sem executar
zsh -n ~/.zsh_custom.d/XX-*.zsh  # verificar módulo específico
```

### Causas comuns
1. **Erro de syntax** num ficheiro .zsh
2. **PATH hardcoded** no `reloadz` desatualizado
3. **Dependência circular** entre módulos

### Soluções
- Abrir novo terminal (não recarregar o quebrado)
- Corrigir syntax com `zsh -n`
- Usar `exec zsh` em vez de `reloadz` para reset completo

---

## FZF/fd não funciona

### Sintomas
- `ff`, `cdf`, `vf` não mostram resultados ou dão erro

### Diagnóstico
```zsh
command -v fd                    # deve existir
command -v fzf                   # deve existir
fd --type f . .                  # testar fd isolado
```

### Causas comuns
1. **fd não instalado** — no Ubuntu é `fd-find`
2. **Nenhum ficheiro** na pasta (pasta vazia)
3. **Permissões** — sem acesso a ficheiros

### Soluções
```zsh
sudo apt install fd-find fzf
ln -sf $(which fdfind) ~/.local/bin/fd
```

---

## Rclone mounts não disponíveis

### Sintomas
- `~/Drives/OneDrive` vazio ou inacessível
- `mounts` não mostra nada

### Diagnóstico
```zsh
mounts                           # verificar mounts
rclone_status                    # estado dos serviços
journalctl --user -u rclone-onedrive.service -n 20
```

### Causas comuns
1. **Serviço parado** — restart necessário
2. **Token expirado** — reautenticação necessária
3. **Sem internet** — rclone não consegue conectar
4. **Pasta de mount não existe**

### Soluções
```zsh
rclone_restart                   # reiniciar
rclone config reconnect onedrive:   # reautenticar
mkdir -p ~/Drives/OneDrive       # criar pasta se não existe
```

---

## GPU não funciona com `gpu`

### Sintomas
- App não usa NVIDIA mesmo com `gpu`
- `glxinfo` mostra Intel/Mesa

### Diagnóstico
```zsh
gpu_mode                         # deve ser "on-demand"
gpu_status                       # deve mostrar nvidia-smi
gpu glxinfo | grep "OpenGL renderer"
lsmod | grep nvidia
```

### Causas comuns
1. **Driver não instalado**
2. **Modo errado** (intel-only)
3. **Módulo kernel não carregado**
4. **Wayland vs X11** — algumas apps precisam de configuração extra

### Soluções
```zsh
sudo ubuntu-drivers install      # instalar driver
sudo prime-select on-demand      # modo correto
sudo modprobe nvidia             # carregar módulo
```

---

## Clipboard não funciona

### Sintomas
- `cpath` ou `ccat` dão erro
- Conteúdo não cola

### Diagnóstico
```zsh
echo $XDG_SESSION_TYPE           # wayland ou x11
command -v wl-copy               # para Wayland
command -v xclip                 # para X11
echo "teste" | wl-copy && wl-paste   # testar roundtrip
```

### Causas comuns
1. **Ferramenta não instalada**
2. **Sessão SSH** — sem display server
3. **Wayland mas usa xclip** — incompatível

### Soluções
```zsh
# Para Wayland
sudo apt install wl-clipboard

# Para X11
sudo apt install xclip
```

---

## `dotapply` sobrescreveu ficheiros

### Sintomas
- Configurações locais desapareceram
- Ficheiros que não estavam no repo foram eliminados

### Diagnóstico
```zsh
cd ~/dotfiles
git log --oneline -10            # ver últimos commits
git diff HEAD~1                  # ver o que mudou
```

### Causas comuns
- `rsync --delete` remove tudo que não está na source
- Não fez `dotup` antes no sistema local

### Soluções
- Se os ficheiros estavam em backup: restaurar
- Se não: verificar se há cópias em `~/.local/share/Trash/`
- **Prevenção:** Sempre `dotup` antes de `dotapply`

---

## Zellij não abre / sessão perdida

### Sintomas
- `zjm` falha
- Sessões não persistem

### Diagnóstico
```zsh
command -v zellij
zellij list-sessions
```

### Causas comuns
1. **Não instalado**
2. **Sessão morreu** (crash)
3. **Versão incompatível** com config

### Soluções
```zsh
zellij delete-session main       # limpar sessão corrompida
zjm                              # criar nova
```

---

## Dicas Gerais de Debug

```zsh
# Verificar se função existe
typeset -f nome_funcao

# Verificar se alias existe
alias nome_alias

# Ver toda a configuração carregada
zsh -i -c 'typeset -f' | grep "^nome"

# Testar módulo isolado
zsh -c 'source ~/.zsh_custom.d/XX-modulo.zsh && funcao_teste'

# Ver erros de arranque
zsh -i 2>&1 | grep -i error
```
