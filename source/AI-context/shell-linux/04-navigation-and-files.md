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
  - navigation
  - fzf
  - yazi
  - zoxide
---

# 🧭 Shell — Navegação e Ficheiros

## Ferramentas de Navegação

### Zoxide (cd inteligente)

Inicializado em `05-modern-tools.zsh`. Permite saltar para pastas visitadas anteriormente:

```zsh
z proj          # salta para ~/_Projects (ou similar)
z docs          # salta para ~/Documents
zi              # seleção interativa com fzf
```

### Yazi (file manager)

Definido em `25-modern-ui.zsh`:

```zsh
y               # abre yazi na pasta atual
y ~/Downloads   # abre yazi em Downloads
# Ao sair do yazi, a shell muda para a última pasta visitada
```

**Como funciona:** A função `y` usa `--cwd-file` para guardar a última pasta e faz `cd` automaticamente ao sair.

### FZF (seleção interativa)

Definido em `26-fzf-power.zsh`:

```zsh
ff              # procura ficheiro com preview (bat)
ff ~/Downloads  # procura em pasta específica
cdf             # procura pasta e faz cd
cdf ~           # procura pasta a partir de ~
vf              # procura ficheiro e abre no editor
bf              # procura ficheiro e mostra com bat
hf              # histórico interativo (atuin)
```

---

## Atalhos de Navegação Rápida

### Aliases de cd (35-daily.zsh)

```zsh
home            # cd ~
dl              # cd ~/Downloads
docs            # cd ~/Documents
desk            # cd ~/Desktop
proj            # cd ~/_Projects
```

### Funções de navegação

```zsh
drives          # cd ~/Drives
o_drive         # cd ~/Drives/OneDrive
g_drive         # cd ~/Drives/GoogleDrive
take nova_pasta # mkdir -p + cd
mkcd pasta      # igual a take
up              # cd ..
up 3            # cd ../../..
tmpd            # mktemp -d + cd (pasta temporária)
```

---

## Listagem de Ficheiros (eza)

```zsh
ls              # listagem básica com ícones
l               # listagem longa completa
ll              # listagem longa (sem ocultos)
la              # listagem longa com ocultos
lt              # árvore 2 níveis
lta             # árvore 3 níveis com ocultos
```

---

## Operações com Ficheiros

### Abrir

```zsh
op              # abre pasta atual na app gráfica
op ficheiro.pdf # abre ficheiro com app padrão
op ~/Downloads  # abre Downloads no gestor de ficheiros
```

### Copiar para clipboard

```zsh
cpath           # copia o caminho atual (PWD) para clipboard
ccat script.py  # mostra e copia conteúdo para clipboard
```

### Extrair arquivos

```zsh
extract file.zip
extract backup.tar.gz
extract data.7z
```

### Apagar com segurança

```zsh
del ficheiro    # move para lixo (trash-put)
trash-list      # ver lixo
trash-empty     # esvaziar
```

### Análise de ficheiros

```zsh
recent          # 30 ficheiros mais recentes (pasta atual)
recent ~ 50    # 50 mais recentes em ~
big             # espaço ocupado (ncdu ou du)
big ~/Downloads # análise de Downloads
```

---

## Fluxos de Uso Comuns

### Encontrar e editar um ficheiro

```zsh
vf              # procura com fzf → abre no editor
# ou
ff | xargs nano # seleciona → edita
```

### Navegar para uma pasta desconhecida

```zsh
cdf ~           # procura interativa em ~
# ou
zi              # zoxide interativo
```

### Explorar com Yazi e voltar

```zsh
y               # explora visualmente
# Navega nas pastas no yazi, encontra o que precisa
# Ao sair (q), a shell fica na última pasta do yazi
```

### Copiar caminho para usar noutro lugar

```zsh
cdf ~/proj      # navega para pasta do projeto
cpath           # copia o caminho
# Cola noutro terminal ou app
```

---

## Diagnóstico de Problemas Comuns

### `ff` ou `cdf` não funciona

```zsh
# Verificar dependências
command -v fd    # deve existir
command -v fzf   # deve existir
command -v eza   # para preview no cdf
command -v batcat # para preview no ff
```

**Solução:** Instalar com `sudo apt install fd-find fzf` ou via mise.

### Yazi não muda a pasta ao sair

- Verificar se `yazi` está instalado: `command -v yazi`
- Verificar se a função `y` está definida: `which y`
- Se usar o comando `yazi` diretamente (sem a função `y`), não faz cd

### Zoxide não salta para pastas

```zsh
# Verificar se está inicializado
zoxide query --list    # mostra base de dados
# Se vazia, é preciso "treinar" visitando pastas com cd normal
```

### `eza` não mostra ícones

- Verificar se tem fonte Nerd Font instalada
- Verificar variável `TERM` e emulador de terminal
- Testar: `eza --icons=auto ~/`

### `del` não funciona

```zsh
command -v trash-put   # deve existir
# Instalar: sudo apt install trash-cli
```
