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
  - git
  - backup
---

# 📦 Shell — Git e Dotfiles

## Repositório de Dotfiles

| | |
|---|---|
| **Localização** | `~/dotfiles` |
| **Variável** | `$DOTFILES_DIR` |
| **Definida em** | `80-dotfiles.zsh` |
| **Tipo** | Repositório Git com remote no GitHub |

---

## Estrutura do Repositório

```
~/dotfiles/
└── home/
    ├── .zshrc
    ├── .zsh_custom.d/
    │   ├── 00-core.zsh
    │   ├── 05-modern-tools.zsh
    │   └── ... (todos os módulos)
    ├── .config/
    │   ├── starship.toml
    │   ├── yazi/
    │   ├── zellij/
    │   └── mise/
    └── .wezterm.lua (se existir)
```

---

## Comandos Disponíveis

### `dotsync` — Copiar configs para o repo

```zsh
dotsync
```

Sincroniza (com `rsync -a --delete`):
- `~/.zshrc` → `~/dotfiles/home/.zshrc`
- `~/.zsh_custom.d/` → `~/dotfiles/home/.zsh_custom.d/`
- `~/.config/starship.toml`
- `~/.config/yazi/` (se existir)
- `~/.config/zellij/` (se existir)
- `~/.config/mise/` (exclui cache/downloads)
- `~/.wezterm.lua` (se existir)

**Exclusões:** `*.bak`, `*.bak.*`, `*.off`

### `dotstatus` — Ver alterações

```zsh
dotstatus
```

Equivale a `git -C ~/dotfiles status --short`.

### `dotup` — Guardar tudo no GitHub

```zsh
dotup "Mensagem do commit"
dotup                        # usa "Update shell dotfiles"
```

**Fluxo interno:**
1. `dotsync` (copia configs)
2. `git add -A`
3. `git commit -m "mensagem"`
4. `git push`

### `dotpull` — Buscar alterações do remote

```zsh
dotpull
```

Equivale a `git -C ~/dotfiles pull --rebase`.

### `dotapply` — Aplicar configs do repo neste sistema

```zsh
dotapply          # pede confirmação antes de sobrescrever
dotapply --force  # salta confirmação
```

**⚠️ CUIDADO:** Este comando sobrescreve ficheiros locais!

**Fluxo interno:**
1. Pede confirmação (a não ser com `--force`)
2. `dotpull` (puxa últimas alterações)
3. Copia tudo do repo para o sistema (com `rsync --delete`)
4. No final, pede para executar `exec zsh`

### `dotdoctor` — Diagnóstico

```zsh
dotdoctor
```

Verifica:
- Se o repo existe
- Remote configurado
- Branch atual
- Status (alterações pendentes)
- **Ficheiros sensíveis** (procura por ssh, gnupg, tokens, passwords, keys, etc.)

---

## Fluxo Recomendado

### Guardar alterações diárias

```zsh
# Depois de editar configs
dotup "Add new alias for X"
```

### Configurar novo sistema

```zsh
git clone <url-do-repo> ~/dotfiles
dotapply
exec zsh
```

### Sincronizar entre máquinas

```zsh
# Máquina A (onde fizeste alterações)
dotup "Update from machine A"

# Máquina B (onde queres aplicar)
dotpull
dotapply
exec zsh
```

### Verificar antes de publicar

```zsh
dotdoctor    # verifica ficheiros sensíveis
dotstatus    # ver o que mudou
```

---

## ⚠️ Riscos e Cuidados

### `dotapply` sobrescreve ficheiros locais

O comando usa `rsync --delete`, o que significa:
- Ficheiros que existam localmente mas **não** no repo serão **eliminados**
- Alterações locais não commitadas serão **perdidas**

**Mitigação:** Fazer sempre `dotup` antes de `dotapply` noutro sistema.

### Ficheiros sensíveis no repo

O `dotdoctor` procura por padrões como:
- ssh, gnupg, rclone, token, secret, password, credential, .env, key, pem, p12

Se encontrar, mostra aviso. **Nunca fazer commit de chaves ou tokens!**

### Conflitos no pull

Se `dotpull` falhar com conflitos:

```zsh
cd ~/dotfiles
git status            # ver o que conflitou
git diff              # ver diferenças
git rebase --continue # resolver e continuar
# ou
git rebase --abort    # desistir
```

---

## Git (uso geral)

### Lazygit

```zsh
lg              # abre lazygit no repo atual
```

### Verificar estado do Git

```zsh
l               # eza com --git mostra status nos ficheiros
dotstatus       # status do repo dotfiles
```
