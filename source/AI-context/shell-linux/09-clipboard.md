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
  - clipboard
  - wayland
  - x11
---

# 📋 Shell — Clipboard

## Contexto

O sistema suporta tanto Wayland como X11, com deteção automática da ferramenta de clipboard correta.

Definido em: `70-clipboard.zsh`

---

## Comandos Disponíveis

### `cpath` — Copiar diretório atual

```zsh
cpath
# ✔ Copiado para a clipboard: /home/user/Projects/meu-projeto
```

### `ccat` — Mostrar e copiar ficheiro

```zsh
ccat script.py
# Mostra conteúdo com syntax highlighting (bat)
# ✔ Conteúdo copiado para clipboard
```

---

## Ferramentas de Clipboard

### Wayland (padrão em Zorin/Ubuntu modernos)

| Comando | Função |
|---------|--------|
| `wl-copy` | Copiar para clipboard |
| `wl-paste` | Colar da clipboard |
| `wl-copy < ficheiro` | Copiar conteúdo de ficheiro |
| `echo "texto" \| wl-copy` | Copiar texto |

**Instalar:**
```zsh
sudo apt install wl-clipboard
```

### X11 (fallback)

| Comando | Função |
|---------|--------|
| `xclip -selection clipboard` | Copiar para clipboard |
| `xclip -selection clipboard -o` | Colar da clipboard |
| `xclip -selection clipboard < ficheiro` | Copiar ficheiro |

**Instalar:**
```zsh
sudo apt install xclip
```

---

## Ordem de Preferência nas Funções

As funções `cpath` e `ccat` verificam na seguinte ordem:
1. `wl-copy` (Wayland) — preferido
2. `xclip` (X11) — fallback

Se nenhum estiver instalado, mostra erro.

---

## Exemplos de Uso

### Copiar output de um comando

```zsh
# Com wl-copy
ls -la | wl-copy

# Com xclip
ls -la | xclip -selection clipboard
```

### Copiar caminho de um ficheiro encontrado

```zsh
ff | wl-copy    # seleciona ficheiro com fzf, copia caminho
```

### Copiar conteúdo de ficheiro para colar noutro lado

```zsh
ccat ~/.config/starship.toml
# Agora pode colar noutro editor/aplicação
```

### Copiar e colar entre terminais

```zsh
# Terminal 1
cpath             # copia caminho atual

# Terminal 2
cd $(wl-paste)    # cola e navega
```

---

## Problemas Comuns

### `wl-copy: command not found`

```zsh
sudo apt install wl-clipboard
```

### Clipboard não funciona em sessão SSH

A clipboard requer um display server. Em SSH:
- Usar `ssh -X` para forwarding X11
- Ou copiar manualmente com selecção do terminal

### Clipboard perde conteúdo ao fechar terminal

No Wayland, a clipboard pode ser limpa quando a aplicação que copiou fecha. Soluções:
- Usar um clipboard manager (ex.: `cliphist`, `clipman`)
- Ou `wl-copy` que mantém o conteúdo

### `ccat` mostra conteúdo mas não copia

Verificar:
```zsh
command -v wl-copy    # deve retornar caminho
command -v xclip      # alternativa
echo $XDG_SESSION_TYPE   # wayland ou x11
```

### Diferença entre selections (X11)

No X11 existem 3 selections:
- `PRIMARY` — seleção com rato (middle-click para colar)
- `CLIPBOARD` — Ctrl+C / Ctrl+V
- `SECONDARY` — raramente usada

As funções usam `clipboard` (Ctrl+V).
