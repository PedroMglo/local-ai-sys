# Auditoria do Shell Zsh

**Data:** 2026-05-01  
**Método:** Análise estática + diagnósticos seguros (sem alterações)  
**Scope:** `~/.zshrc` + `~/.zsh_custom.d/` (17 ficheiros, 1946 linhas)

---

## 1. Resumo executivo

### Estado geral: ✅ Muito bom

O setup é **modular, bem organizado e consistente**. Segue padrões claros de design, tem documentação integrada via `--help` em todas as funções, e o tempo de arranque é excelente.

### Principais pontos fortes

- Modularidade exemplar — 16 módulos numerados com ordem de carregamento clara
- Padrão de código consistente (`_wants_help`, `_err`, validação de dependências)
- Sistema de ajuda integrado (`zhelp_custom`, `--help` em cada função)
- Bom sistema de dotfiles com confirmação em operações destrutivas
- Sem duplicação de aliases
- Sintaxe válida em 100% dos ficheiros
- Startup rápido (238ms)

### Principais problemas

| Prioridade | Problema |
|------------|----------|
| 🔴 Alta | Secção "Copilot CLI helpers" duplicada no .zshrc (linhas 106-155) |
| 🔴 Alta | PATH `$HOME/.local/bin` adicionado 3 vezes no .zshrc |
| 🟡 Média | Falta alias `bat=batcat` — ferramentas usam ambos os nomes |
| 🟡 Média | Ficheiro `update.save` órfão na pasta |
| 🟡 Média | `cleanup` apaga caches sem pedir confirmação |
| 🟢 Baixa | Inicializações com `eval` podem ser cacheadas para ganhar ~50ms |

### Melhorias com maior impacto

1. Limpar duplicações no `.zshrc` (imediato, sem risco)
2. Criar alias `bat=batcat` (resolve fallbacks em `ff`, `bf`, `ccat`)
3. Lazy-load de ferramentas menos usadas (ganho marginal em startup)
4. Adicionar aliases para DuckDB/Parquet (produtividade data engineering)

---

## 2. Performance

### Tempo de arranque atual

```
real    0m0,238s
user    0m0,182s
sys     0m0,165s
```

**Veredicto:** Excelente. Abaixo de 300ms é considerado rápido para Zsh com plugins.

### O que contribui para o tempo

| Componente | Impacto estimado | Notas |
|------------|-----------------|-------|
| Oh My Zsh + plugins | ~80ms | Já tem `ZSH_DISABLE_COMPFIX=true` ✓ |
| Zinit (fzf-tab, autosuggestions, fast-syntax) | ~30ms | `wait lucid` já aplicado ✓ |
| `eval "$(mise activate zsh)"` | ~20ms | Pode ser cacheado |
| `eval "$(zoxide init zsh)"` | ~10ms | Pode ser cacheado |
| `eval "$(direnv hook zsh)"` | ~10ms | Leve |
| `eval "$(atuin init zsh)"` | ~15ms | Pode ser cacheado |
| `eval "$(starship init zsh)"` | ~15ms | Necessário, sem alternativa |
| Módulos custom (~1946 linhas) | ~5ms | Leve — são só definições |

### Sugestões de otimização

#### Opção A: Cache de inicializações (ganho ~50ms)

```zsh
# Em 05-modern-tools.zsh, substituir eval direto por cache:
_cached_eval() {
  local cmd="$1" cache="$HOME/.cache/zsh-eval/${cmd//[^a-z]/-}"
  if [[ ! -f "$cache" || "$(command -v "$cmd")" -nt "$cache" ]]; then
    mkdir -p "${cache:h}"
    "$cmd" > "$cache" 2>/dev/null
  fi
  source "$cache"
}
```

**Nota:** Com 238ms de startup, esta otimização é **opcional**. Só vale a pena se o tempo crescer no futuro.

#### Opção B: Remover Oh My Zsh (ganho ~80ms, risco alto)

Não recomendado sem plano de migração. Os plugins `git`, `gh`, `docker`, `sudo`, `fzf` teriam de ser substituídos.

### Diagnóstico: sem problemas

- Nenhum comando lento no startup
- Nenhuma subshell desnecessária
- Nenhum `sleep` ou `curl` no arranque

---

## 3. Organização dos ficheiros

### Avaliação da estrutura atual: ✅ Excelente

```
~/.zsh_custom.d/
├── 00-core.zsh           (23 linhas)  — helpers internos
├── 05-modern-tools.zsh   (33 linhas)  — PATH + inicializações
├── 10-help.zsh           (253 linhas) — sistema de ajuda
├── 20-navigation.zsh     (197 linhas) — navegação + Python venvs
├── 25-modern-ui.zsh      (46 linhas)  — Yazi + Zellij
├── 26-fzf-power.zsh      (49 linhas)  — FZF helpers
├── 30-rclone.zsh         (67 linhas)  — cloud mounts
├── 35-daily.zsh          (319 linhas) — comandos diários
├── 40-gpu.zsh            (129 linhas) — NVIDIA
├── 50-convert.zsh        (172 linhas) — conversão de ficheiros
├── 60-info.zsh           (114 linhas) — info do sistema
├── 70-clipboard.zsh      (94 linhas)  — clipboard
├── 80-dotfiles.zsh       (220 linhas) — gestão dotfiles
├── 85-maintenance.zsh    (153 linhas) — manutenção
├── 90-aliases.zsh        (17 linhas)  — aliases finais
├── 95-completions.zsh    (56 linhas)  — completions custom
├── 95-copilot-context.zsh (7 linhas)  — copilot com contexto
└── update.save           (vazio)      — ⚠️ ficheiro órfão
```

### Ficheiros bem separados ✓

- Cada módulo tem responsabilidade clara
- Numeração garante ordem de carregamento previsível
- Nenhum ficheiro mistura temas diferentes

### Problemas encontrados

| Problema | Ficheiro | Ação recomendada |
|----------|----------|------------------|
| `update.save` sem extensão .zsh | ~/.zsh_custom.d/ | Apagar (está vazio) |
| `35-daily.zsh` tem 319 linhas | 35-daily.zsh | Considerar separar `extract` para 36-archive.zsh |
| `20-navigation.zsh` mistura navegação com Python venvs | 20-navigation.zsh | Considerar mover venvs para 21-python.zsh |
| Dois ficheiros com prefixo 95- | 95-*.zsh | Renomear `95-copilot-context.zsh` para `96-copilot-context.zsh` |

### Sobre o .zshrc

**Problema crítico:** O `.zshrc` tem uma **secção duplicada** (linhas 106-155):

```
Linha 106: # ===== GitHub Copilot CLI helpers =====
Linha 151: # ===== GitHub Copilot CLI helpers =====  ← DUPLICADO
```

Isto causa:
- `export PATH="$HOME/.local/bin:$PATH"` executado 2 vezes extra
- Funções `ask`, `cmd`, `why`, `gitai`, `err`, `dockai`, `dataai` definidas 2 vezes (sem efeito mas sujo)

**Correção:** Apagar linhas 151-155 do `.zshrc`.

---

## 4. Aliases

### Aliases bons ✓

| Alias | Comando | Avaliação |
|-------|---------|-----------|
| `ls` | `eza --group-directories-first --icons=auto` | ✓ Excelente substituto |
| `l/ll` | `eza -lh ... --git` | ✓ Informativo |
| `la` | `eza -lah ...` | ✓ Consistente |
| `lt/lta` | `eza --tree ...` | ✓ Muito útil |
| `del` | `trash-put` | ✓ Seguro — evita rm acidental |
| `top` | `btop` | ✓ Upgrade visual |
| `lg` | `lazygit` | ✓ Git produtivo |
| `c` | `clear` | ✓ Standard |
| `ai/cop` | `copilot` | ✓ Rápido |

### Aliases redundantes

| Alias | Motivo |
|-------|--------|
| `l` e `ll` | São idênticos — manter apenas um |
| `helpz` e `zhelp_custom` | `helpz` basta como alias; a função pode ficar interna |

### Aliases perigosos

Nenhum alias perigoso encontrado. ✓

### Aliases recomendados a adicionar

```zsh
# bat (resolve o problema batcat vs bat)
alias bat='batcat'
alias cat='batcat --paging=never'

# Git shortcuts (complementar ao plugin oh-my-zsh)
alias gs='git status'
alias gd='git diff'
alias gds='git diff --staged'
alias glog='git log --oneline --graph --decorate -20'

# Docker
alias dps='docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'
alias dlog='docker logs -f'
alias dex='docker exec -it'
alias dc='docker compose'
alias dcu='docker compose up -d'
alias dcd='docker compose down'

# Sistema
alias reload='exec zsh'
alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'

# Segurança
alias cp='cp -i'
alias mv='mv -i'
```

---

## 5. Funções

### Funções mais úteis

| Função | Rating | Porquê |
|--------|--------|--------|
| `ff` | ⭐⭐⭐⭐⭐ | Procura interativa com preview |
| `y` | ⭐⭐⭐⭐⭐ | Yazi + cd automático |
| `take` | ⭐⭐⭐⭐⭐ | mkdir + cd num só comando |
| `dotup` | ⭐⭐⭐⭐⭐ | Backup de configs num comando |
| `portkill` | ⭐⭐⭐⭐ | Útil + pede confirmação |
| `extract` | ⭐⭐⭐⭐ | Detecta formato automaticamente |
| `convert_file` | ⭐⭐⭐⭐ | Versátil |
| `health` | ⭐⭐⭐⭐ | Visão geral rápida |
| `ccat` | ⭐⭐⭐⭐ | Ver + copiar num passo |

### Funções quebradas ou frágeis

| Função | Problema | Solução |
|--------|----------|---------|
| `ff`, `bf` | Tentam `batcat` e `bat` separadamente | Criar alias `bat=batcat` e simplificar |
| `doctor` | Executa `time zsh -i -c exit` que imprime para stderr e pode confundir | Capturar output com `{ time ... } 2>&1` |
| `sysinfo` | Usa `echo` em vez de `print` | Inconsistente com o padrão (cosmético) |

### Funções que precisam de fallback

| Função | Dependência | Falta fallback? |
|--------|-------------|-----------------|
| `hf` | atuin | Sim — se atuin não estiver instalado, dá erro silencioso |
| `zja/zjm` | zellij | Sim — se zellij não existir, dá erro não tratado |
| `cdf` | fd + fzf | Se `fd` faltar, `fd --type d` falha silenciosamente |

**Correção recomendada para `hf`:**

```zsh
function hf {
  command -v atuin >/dev/null 2>&1 || { _err "atuin não encontrado."; return 127; }
  atuin search -i
}
```

### Funções que precisam de confirmação antes de ações perigosas

| Função | Risco | Estado atual |
|--------|-------|-------------|
| `dotapply` | Sobrescreve configs locais | ✓ Já pede confirmação |
| `portkill` | Mata processos | ✓ Já pede confirmação |
| `updateall` | Atualiza sistema | ⚠️ Não pede confirmação |
| `cleanup` | Apaga caches e logs | ⚠️ Não pede confirmação |

**Recomendação:** Adicionar confirmação a `updateall` e `cleanup`:

```zsh
function updateall {
  print "⚠️  Vai atualizar: apt, flatpak, mise, zinit e OMZ"
  print -n "Continuar? [y/N] "
  local reply; read -r reply
  [[ "$reply" =~ ^[Yy]$ ]] || { print "Cancelado."; return 0; }
  # ... resto da função
}
```

---

## 6. Ferramentas modernas

### O que está bem integrado ✓

| Ferramenta | Integração | Nota |
|------------|-----------|------|
| eza | Aliases `ls/l/ll/la/lt` | Perfeita |
| fzf | `ff`, `cdf`, `vf`, `bf`, fzf-tab | Excelente |
| zoxide | `eval` no arranque | Funcional |
| yazi | Função `y` com cd automático | Excelente |
| starship | Prompt no final do .zshrc | Correto |
| lazygit | Alias `lg` | Simples e eficaz |
| trash-put | Alias `del` | Seguro |
| atuin | `eval` no arranque + `hf` | Bom |
| rclone | Funções `mounts`, `rclone_status/restart` | Funcional |
| mise | Gestor de runtimes + shims | Correto |
| direnv | Hook no arranque | Correto |

### O que falta integrar melhor

| Ferramenta | O que falta |
|------------|-------------|
| **batcat** | Alias `bat=batcat` para unificar referências |
| **fd** | Poderia ter aliases tipo `alias fdf='fd --type f'`, `alias fdd='fd --type d'` |
| **rg** | Falta alias tipo `alias rgi='rg -i'` (case-insensitive) |
| **git** | Faltam aliases de workflow (stash, rebase, log bonito) |
| **docker** | Faltam aliases de dia a dia (`dps`, `dc`, `dlog`) |
| **zellij** | Layout `daily` existe mas podia ter layouts para projetos |

### Sugestões específicas

#### Para fzf

```zsh
# Procurar dentro de ficheiros (grep interativo)
function rgf {
  local file line
  local result="$(rg --line-number --color=always "${@:-.}" 2>/dev/null |
    fzf --ansi --height=80% --layout=reverse --border \
      --delimiter=: \
      --preview 'batcat --color=always --highlight-line {2} {1} 2>/dev/null || sed -n "{2}p" {1}'
  )"
  [[ -n "$result" ]] || return
  file="$(echo "$result" | cut -d: -f1)"
  line="$(echo "$result" | cut -d: -f2)"
  "${EDITOR:-nano}" "+$line" "$file"
}
```

#### Para zoxide

```zsh
# Alias para z interativo
alias zi='zoxide query -i'
```

#### Para starship

Sem problemas. O prompt é inicializado no sítio correto (fim do .zshrc, depois de tudo).

---

## 7. Produtividade para Data Engineering

### Melhorias para Python

```zsh
# Já tem: vls, act_e, uvv, uvp, uvr ✓
# Recomendado adicionar:

# Jupyter rápido
alias jn='jupyter notebook'
alias jl='jupyter lab'

# IPython com autoreload
alias ipy='ipython --TerminalInteractiveShell.autoformatter=black'

# Instalar pacote e adicionar ao requirements
function pipadd {
  uv pip install "$@" && uv pip freeze | grep -i "${1%%[=<>]*}" >> requirements.txt
}
```

### Melhorias para DuckDB

```zsh
# DuckDB já está instalado em ~/.local/bin ✓
# Aliases produtivos:

alias duck='duckdb'
alias duckm='duckdb :memory:'

# Abrir DuckDB num ficheiro Parquet diretamente
function duckpq {
  [[ -z "$1" ]] && { _err "Uso: duckpq <ficheiro.parquet>"; return 2; }
  duckdb -c "SELECT * FROM read_parquet('$1') LIMIT 100;"
}

# Schema de um Parquet
function pqschema {
  [[ -z "$1" ]] && { _err "Uso: pqschema <ficheiro.parquet>"; return 2; }
  duckdb -c "DESCRIBE SELECT * FROM read_parquet('$1');"
}

# Contagem de linhas de um Parquet
function pqcount {
  [[ -z "$1" ]] && { _err "Uso: pqcount <ficheiro.parquet>"; return 2; }
  duckdb -c "SELECT count(*) as total FROM read_parquet('$1');"
}

# Query ad-hoc num Parquet
function pqsql {
  local file="$1"; shift
  [[ -z "$file" ]] && { _err "Uso: pqsql <ficheiro.parquet> <query>"; return 2; }
  duckdb -c "CREATE VIEW data AS SELECT * FROM read_parquet('$file'); $*"
}
```

### Melhorias para Parquet

As funções acima (`duckpq`, `pqschema`, `pqcount`, `pqsql`) cobrem os casos mais comuns.

Adicional:

```zsh
# Converter CSV para Parquet
function csv2pq {
  [[ -z "$1" ]] && { _err "Uso: csv2pq <ficheiro.csv> [output.parquet]"; return 2; }
  local out="${2:-${1%.csv}.parquet}"
  duckdb -c "COPY (SELECT * FROM read_csv_auto('$1')) TO '$out' (FORMAT PARQUET);"
  print "✔ Convertido: $1 → $out"
}

# Converter Parquet para CSV
function pq2csv {
  [[ -z "$1" ]] && { _err "Uso: pq2csv <ficheiro.parquet> [output.csv]"; return 2; }
  local out="${2:-${1%.parquet}.csv}"
  duckdb -c "COPY (SELECT * FROM read_parquet('$1')) TO '$out' (FORMAT CSV, HEADER);"
  print "✔ Convertido: $1 → $out"
}
```

### Melhorias para Oracle

```zsh
# Alias para sqlplus se instalado
alias sqlp='sqlplus'

# Conectar via string
function oraconn {
  [[ -z "$1" ]] && { _err "Uso: oraconn <connection_string>"; return 2; }
  command -v sqlplus >/dev/null 2>&1 || { _err "sqlplus não encontrado."; return 127; }
  sqlplus "$1"
}
```

### Melhorias para Docker

```zsh
# Já tem plugin docker + docker-compose no OMZ ✓
# Adicionar aliases práticos:

alias dps='docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"'
alias dpsa='docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"'
alias dlog='docker logs -f'
alias dex='docker exec -it'
alias dc='docker compose'
alias dcu='docker compose up -d'
alias dcd='docker compose down'
alias dcr='docker compose restart'
alias dcl='docker compose logs -f'

# Limpar Docker (com confirmação)
function docker_clean {
  print "⚠️  Vai remover: containers parados, imagens dangling, volumes órfãos"
  print -n "Continuar? [y/N] "
  local reply; read -r reply
  [[ "$reply" =~ ^[Yy]$ ]] || { print "Cancelado."; return 0; }
  docker system prune -af --volumes
}
```

### Melhorias para ficheiros grandes

```zsh
# Dividir ficheiro grande em partes
function splitfile {
  [[ -z "$1" || -z "$2" ]] && { _err "Uso: splitfile <ficheiro> <tamanho> (ex: 100M)"; return 2; }
  split -b "$2" "$1" "${1}."
  print "✔ Ficheiro dividido com prefixo: ${1}."
}

# Contar linhas eficientemente
alias wl='wc -l'

# Head/tail grandes ficheiros
alias h100='head -n 100'
alias t100='tail -n 100'
```

---

## 8. Segurança

### Riscos encontrados

| Risco | Gravidade | Localização | Detalhes |
|-------|-----------|-------------|----------|
| PATH duplicado | 🟡 Média | .zshrc (3 sítios) | Não é vulnerabilidade mas polui o ambiente |
| Código duplicado | 🟡 Média | .zshrc linhas 106-155 | Indica edição manual sem revisão |
| `cleanup` sem confirmação | 🟡 Média | 85-maintenance.zsh | Apaga caches sem perguntar |
| `updateall` sem confirmação | 🟡 Média | 85-maintenance.zsh | Faz `sudo apt upgrade -y` sem perguntar |
| `ports` usa sudo | 🟢 Baixa | 35-daily.zsh | Poderia usar `ss -tlnp` sem sudo |

### Comandos perigosos

| Comando | Risco | Proteção atual |
|---------|-------|----------------|
| `dotapply --force` | Sobrescreve configs | Sem `--force` pede confirmação ✓ |
| `portkill` | Mata processos | Pede confirmação ✓ |
| `updateall` | Modifica sistema | ⚠️ Sem confirmação |
| `cleanup` | Apaga ficheiros | ⚠️ Sem confirmação (mas só caches) |
| `dotsync` | Usa `rsync --delete` | Mas é para o repo, não o sistema ✓ |

### Recomendações de proteção

1. **Adicionar confirmação a `updateall` e `cleanup`** — são operações com efeitos irreversíveis

2. **Substituir `ports` por versão sem sudo:**
```zsh
function ports {
  ss -tlnp 2>/dev/null || sudo lsof -iTCP -sTCP:LISTEN -P -n
}
```

3. **Proteger `rm` global (opcional):**
```zsh
# Já tem del=trash-put, mas para proteção extra:
alias rm='rm -I'  # pede confirmação se > 3 ficheiros
```

4. **Validar que dotdoctor corre antes de dotup** — já está implementado com a verificação de ficheiros sensíveis ✓

### O que está bem em segurança ✓

- `del` usa `trash-put` em vez de `rm`
- `dotapply` pede confirmação
- `dotdoctor` procura ficheiros sensíveis no repo
- Nenhum token/segredo exposto nos ficheiros
- `_dotfiles_require_repo` valida existência do repo antes de operar
- `unalias gpu` previne conflitos

---

## 9. Backlog de melhorias

### 🔴 Alta prioridade

| # | Melhoria | Impacto | Risco |
|---|----------|---------|-------|
| 1 | Remover secção Copilot CLI duplicada no .zshrc (linhas 151-155) | Limpa código morto + PATH duplicado | Nenhum |
| 2 | Remover `export PATH="$HOME/.local/bin:$PATH"` duplicado (linhas 109, 154) | PATH limpo | Nenhum |
| 3 | Criar alias `bat='batcat'` | Resolve fallbacks em ff, bf, ccat | Nenhum |
| 4 | Apagar `update.save` da pasta | Limpa lixo | Nenhum |
| 5 | Adicionar confirmação a `updateall` e `cleanup` | Segurança | Mínimo |

### 🟡 Média prioridade

| # | Melhoria | Impacto | Risco |
|---|----------|---------|-------|
| 6 | Adicionar aliases Docker (`dps`, `dc`, `dcu`, etc.) | Produtividade | Nenhum |
| 7 | Adicionar funções DuckDB/Parquet (`duckpq`, `pqschema`, etc.) | Produtividade DE | Nenhum |
| 8 | Adicionar verificação de dependências a `hf`, `zja`, `zjm` | Robustez | Nenhum |
| 9 | Substituir `ports` por `ss -tlnp` (sem sudo) | Praticidade | Nenhum |
| 10 | Adicionar aliases Git extras (`glog`, `gds`, etc.) | Produtividade | Nenhum |
| 11 | Adicionar `rgf` (grep interativo com fzf) | Produtividade | Nenhum |
| 12 | Proteger `rm` com `rm -I` e `cp`/`mv` com `-i` | Segurança | Baixo (pode incomodar) |
| 13 | Unificar `l` e `ll` (são idênticos) | Consistência | Nenhum |

### 🟢 Baixa prioridade

| # | Melhoria | Impacto | Risco |
|---|----------|---------|-------|
| 14 | Separar `35-daily.zsh` (extract → 36-archive.zsh) | Organização | Nenhum |
| 15 | Mover venvs de 20-navigation para 21-python.zsh | Organização | Nenhum |
| 16 | Renomear `95-copilot-context.zsh` → `96-copilot-context.zsh` | Ordem clara | Nenhum |
| 17 | Cache de `eval` para mise/zoxide/atuin/direnv | Performance (~50ms) | Médio |
| 18 | Adicionar layout Zellij para projetos | Produtividade | Nenhum |
| 19 | Adicionar função `csv2pq`/`pq2csv` | Produtividade DE | Nenhum |
| 20 | Melhorar `doctor` com verificação de versões | Manutenção | Nenhum |
| 21 | Adicionar aliases `..`, `...`, `....` | Conveniência | Nenhum |

---

## 10. Plano de implementação seguro

### Alterações rápidas e seguras (podem ser feitas já)

```bash
# 1. Apagar ficheiro órfão
rm ~/.zsh_custom.d/update.save

# 2. No .zshrc, apagar linhas 151-155 (secção duplicada)
# Bloco a remover:
# ===== GitHub Copilot CLI helpers =====
# Garante que binários instalados no user path são encontrados
# export PATH="$HOME/.local/bin:$PATH"

# 3. No .zshrc, apagar a linha 109 (PATH duplicado dentro do primeiro bloco Copilot)
# export PATH="$HOME/.local/bin:$PATH"

# 4. Em 90-aliases.zsh, adicionar:
# alias bat='batcat'
```

### Alterações que precisam de teste

| Alteração | Como testar |
|-----------|-------------|
| Remover duplicados do .zshrc | `zsh -n ~/.zshrc && exec zsh && doctor` |
| Adicionar aliases Docker | `exec zsh && dps` |
| Adicionar funções DuckDB | `exec zsh && duckpq algum_ficheiro.parquet` |
| Modificar `updateall`/`cleanup` | `exec zsh && updateall` (verificar prompt) |
| Substituir `ports` | `exec zsh && ports` |

### Alterações que só devem ser feitas com backup

| Alteração | Backup recomendado |
|-----------|-------------------|
| Qualquer edição ao .zshrc | `cp ~/.zshrc ~/.zshrc.bak.$(date +%s)` |
| Reorganizar módulos (separar ficheiros) | `dotup "Backup before reorganization"` |
| Cache de eval | `dotup "Backup before eval cache"` |

### Como testar depois de alterar

```bash
# 1. Verificar sintaxe
zsh -n ~/.zshrc
for f in ~/.zsh_custom.d/*.zsh; do zsh -n "$f"; done

# 2. Medir tempo de arranque
time zsh -i -c exit

# 3. Abrir shell nova e testar funcionalidades
exec zsh
doctor
helpz

# 4. Se algo correr mal, reverter:
cp ~/.zshrc.bak.TIMESTAMP ~/.zshrc
exec zsh

# 5. Se tudo estiver bem, guardar:
dotup "Apply shell audit improvements"
```

---

## Anexo: Estatísticas

| Métrica | Valor |
|---------|-------|
| Total de ficheiros | 17 (16 .zsh + 1 orphan) |
| Total de linhas | 1946 |
| Total de funções | 63 |
| Total de aliases | ~30 |
| Tempo de arranque | 238ms |
| Erros de sintaxe | 0 |
| Aliases duplicados | 0 |
| Funções sem --help | 0 |
| Dependências falhadas | 0 (bat listado como "não instalado" mas batcat existe) |
