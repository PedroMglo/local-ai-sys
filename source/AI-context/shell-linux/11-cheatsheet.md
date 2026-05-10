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
  - cheatsheet
---

# ⚡ Shell — Cheat Sheet

## 🧭 Navegação

```zsh
home / dl / docs / desk / proj    # atalhos de cd
drives / o_drive / g_drive        # cloud mounts
take pasta                        # mkdir + cd
up 3                              # cd ../../..
tmpd                              # pasta temporária
z nome                            # zoxide (cd inteligente)
zi                                # zoxide interativo
cdf                               # fzf para escolher pasta
y                                 # yazi (file manager)
```

## 📂 Ficheiros

```zsh
ls / l / ll / la                  # eza listagens
lt / lta                          # árvores
ff                                # procurar ficheiro (fzf + preview)
vf                                # procurar e editar
bf                                # procurar e ver com bat
recent                            # ficheiros recentes
big                               # análise de espaço (ncdu)
op ficheiro                       # abrir com app gráfica
extract arquivo.zip               # extrair comprimido
del ficheiro                      # mover para lixo
```

## 📋 Clipboard

```zsh
cpath                             # copiar PWD
ccat ficheiro                     # mostrar + copiar conteúdo
echo "x" | wl-copy               # copiar texto
wl-paste                          # colar
```

## 🖥️ Sessões

```zsh
zjm                               # Zellij sessão main
zjd                               # Zellij layout diário
zjl                               # listar sessões
zja nome                          # anexar a sessão
lg                                # lazygit
```

## 🔍 Histórico

```zsh
hf                                # atuin interativo
Ctrl+R                            # atuin search (atalho)
```

## 🌐 Rede

```zsh
myip                              # IP público
localip                           # IPs locais
ports                             # portas em escuta
portkill 3000                     # matar processo na porta
serve 8080                        # HTTP server
qrcode "https://..."             # gerar QR
```

## 🎮 GPU

```zsh
gpu blender                       # executar com NVIDIA
gpu_status                        # nvidia-smi
gpu_mode                          # ver modo prime-select
gpu_flatpak com.app.Id            # flatpak com NVIDIA
```

## 📦 Dotfiles

```zsh
dotup "msg"                       # sync + commit + push
dotstatus                         # ver alterações
dotpull                           # buscar alterações
dotapply                          # aplicar do repo
dotdoctor                         # diagnóstico
```

## 🔧 Manutenção

```zsh
health                            # resumo do sistema
updateall                         # atualizar tudo
cleanup                           # limpar caches/logs
doctor                            # diagnóstico do shell
reloadz                           # recarregar zsh
```

## 🐍 Python

```zsh
vls                               # listar venvs
act_e nome                        # ativar venv
uvv nome                          # criar venv com uv
uvv                               # criar .venv local com uv
uvp install pacote                # uv pip install
uvr script.py                     # uv run
```

## 📄 Conversão

```zsh
convert_file in.md out.pdf        # md → pdf (LaTeX)
convert_file in.md out.pdf html   # md → pdf (HTML)
convert_file in.docx out.pdf      # docx → pdf
convert_file in.md out.html       # md → html
```

## 🤖 AI Local (Ollama)

```zsh
ol <prompt>                       # chat com qwen3 (default)
ol coder <prompt>                 # modelo de código
ol deep <prompt>                  # raciocínio profundo (deepseek-r1)
ol gemma <prompt>                 # modelo ultra-rápido
aicode <prompt>                   # atalho para código
aiask <pergunta>                  # resposta concisa (3 frases)
aimodels                          # listar modelos instalados
aistatus                          # VRAM e modelos em memória
aiembed <texto>                   # gerar embedding bge-m3
cat f.py | aicode "revê"          # analisar ficheiro com pipe
```

## 🦆 Data Engineering

```zsh
duck                              # abrir DuckDB
duckm                             # DuckDB em memória
duckpq data.parquet               # preview (100 linhas)
duckpq data.parquet 50            # preview com limite
pqschema data.parquet             # schema / tipos de colunas
pqcount data.parquet              # contar linhas
pqsql data.parquet "SELECT ..."   # query SQL ad-hoc
csv2pq data.csv                   # CSV → Parquet
pq2csv data.parquet               # Parquet → CSV
docker_clean                      # limpar Docker (com confirmação)
```

## ℹ️ Ajuda

```zsh
helpz                             # ajuda geral
helpz <cmd>                       # ajuda de um comando
shellinfo                         # info do shell
daily_help                        # comandos diários
maintenance_help                  # comandos manutenção
dothelp                           # comandos dotfiles
myz                               # editar config
myz gpu                           # editar módulo gpu
```

## 📅 Produtividade

```zsh
today                             # data/hora
note                              # notas mensais
c                                 # clear
```
