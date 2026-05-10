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
  - functions
---

# ⚙️ Shell — Funções

## Funções Internas (00-core.zsh)

### `_err`
- **Objetivo:** Imprimir mensagens de erro no stderr
- **Parâmetros:** `$@` — mensagem(s) de erro
- **Uso interno:** Todas as funções

### `_wants_help`
- **Objetivo:** Verificar se o utilizador pediu ajuda
- **Parâmetros:** `$1` — primeiro argumento do comando
- **Retorna:** Verdadeiro se `$1` é `-h`, `--help` ou `help`

### `_list_dir_names`
- **Objetivo:** Listar nomes dentro de um diretório
- **Parâmetros:** `$1` — caminho do diretório
- **Usa:** `command ls -1A`

### `_edit_file`
- **Objetivo:** Abrir ficheiro no editor
- **Parâmetros:** `$1` — caminho do ficheiro
- **Usa:** `$EDITOR` (fallback: `nano`)

---

## Sistema de Ajuda (10-help.zsh)

### `zhelp_custom`
- **Objetivo:** Sistema central de ajuda do toolkit
- **Parâmetros:** `[$1]` — nome do comando (opcional)
- **Comportamento:**
  - Sem argumento: mostra ajuda completa
  - Com argumento função: executa `--help` da função
  - Com argumento alias: mostra definição do alias
  - Com argumento comando: mostra caminho com `whence`
- **Alias:** `helpz`

### `reloadz`
- **Objetivo:** Recarregar `~/.zshrc` na shell atual
- **Parâmetros:** Nenhum
- **Usa:** `source ~/.zshrc`, `hash -r`
- **⚠️ Nota:** Redefine PATH manualmente com caminho hardcoded

### `myz`
- **Objetivo:** Editar módulos da configuração Zsh
- **Parâmetros:** `[$1]` — nome do módulo (core, help, modern, navigation, ui, fzf, rclone, daily, gpu, convert, info, clipboard, dotfiles, maintenance, aliases)
- **Comportamento:**
  - Sem argumento: abre `~/.zsh_custom.d` no VS Code (ou `$EDITOR`)
  - Com módulo: abre ficheiro correspondente

---

## Navegação (20-navigation.zsh)

### `drives`
- **Objetivo:** `cd ~/Drives`
- **Parâmetros:** Nenhum

### `o_drive`
- **Objetivo:** `cd ~/Drives/OneDrive`
- **Parâmetros:** Nenhum

### `g_drive`
- **Objetivo:** `cd ~/Drives/GoogleDrive`
- **Parâmetros:** Nenhum

### `vls`
- **Objetivo:** Listar ambientes virtuais Python
- **Parâmetros:** Nenhum
- **Diretório:** `~/venvs`

### `act_e`
- **Objetivo:** Ativar virtualenv Python
- **Parâmetros:** `$1` — nome do ambiente
- **Usa:** `source ~/venvs/<nome>/bin/activate`
- **Fallback:** Mostra ambientes disponíveis se falhar

### `mkcd`
- **Objetivo:** Alias semântico para `take` (mantido por compatibilidade)
- **Parâmetros:** `$1` — caminho/nome
- **Nota:** Redirige para `take`

---

## UV / Python Moderno (20-navigation.zsh)

### `uvv`
- **Objetivo:** Criar virtualenv com uv
- **Parâmetros:** `[$1]` — nome do venv (opcional)
- **Comportamento:**
  - Sem argumento: cria `.venv` na pasta atual
  - Com argumento: cria em `~/venvs/<nome>`
- **Dependência:** `uv`

### Aliases uv

| Alias | Comando | Descrição |
|-------|---------|-----------|
| `uvp` | `uv pip` | Gestor de pacotes |
| `uvr` | `uv run` | Executar com uv |

---

## UI Moderna (25-modern-ui.zsh)

### `y`
- **Objetivo:** Abrir Yazi e fazer cd para a pasta final
- **Parâmetros:** `[$@]` — argumentos passados ao yazi
- **Usa:** `yazi --cwd-file`
- **Comportamento:** Se o utilizador mudar de pasta no Yazi, a shell acompanha

### `zja`
- **Objetivo:** Anexar a sessão Zellij
- **Parâmetros:** `[$1]` — nome da sessão (default: "main")

### `zjm`
- **Objetivo:** Abrir ou anexar sessão "main" do Zellij
- **Parâmetros:** Nenhum

---

## FZF Helpers (26-fzf-power.zsh)

### `ff`
- **Objetivo:** Procurar ficheiro com fzf + preview
- **Parâmetros:** `[$1]` — diretório base (default: `.`)
- **Usa:** `fd` + `fzf` + `batcat`/`bat`
- **Retorna:** Caminho do ficheiro selecionado (stdout)

### `cdf`
- **Objetivo:** Procurar pasta e fazer cd
- **Parâmetros:** `[$1]` — diretório base (default: `.`)
- **Usa:** `fd` + `fzf` + `eza`

### `vf`
- **Objetivo:** Procurar ficheiro e abrir no editor
- **Parâmetros:** `[$@]` — passados a `ff`
- **Usa:** `ff` + `$EDITOR`

### `bf`
- **Objetivo:** Procurar ficheiro e ver com bat
- **Parâmetros:** `[$@]` — passados a `ff`
- **Usa:** `ff` + `batcat`/`bat`/`less`

### `hf`
- **Objetivo:** Histórico interativo com Atuin
- **Parâmetros:** Nenhum
- **Usa:** `atuin search -i`

---

## Rclone (30-rclone.zsh)

### `mounts`
- **Objetivo:** Mostrar mounts rclone ativos
- **Usa:** `mount | grep rclone`

### `rclone_status`
- **Objetivo:** Estado dos serviços systemd do rclone
- **Serviços:** `rclone-onedrive.service`, `rclone-googledrive.service`

### `rclone_restart`
- **Objetivo:** Reiniciar serviços rclone
- **⚠️ Risco:** Pode desligar mounts ativos temporariamente

---

## Comandos Diários (35-daily.zsh)

### `op`
- **Objetivo:** Abrir ficheiro/pasta com app gráfica
- **Parâmetros:** `[$1]` — alvo (default: `.`)
- **Usa:** `xdg-open`

### `take`
- **Objetivo:** Criar pasta e entrar (alias semântico de `mkcd`)
- **Parâmetros:** `$1` — nome da pasta

### `up`
- **Objetivo:** Subir N diretórios
- **Parâmetros:** `[$1]` — número (default: 1)

### `tmpd`
- **Objetivo:** Criar diretório temporário e entrar
- **Usa:** `mktemp -d`
- **Retorna:** Caminho impresso no stdout

### `note`
- **Objetivo:** Abrir notas rápidas mensais
- **Caminho:** `~/Notes/terminal/YYYY-MM.md`

### `recent`
- **Objetivo:** Mostrar ficheiros recentes
- **Parâmetros:** `[$1]` — pasta (default: `.`), `[$2]` — número (default: 30)
- **Usa:** `find` + `sort`

### `big`
- **Objetivo:** Analisar espaço em disco
- **Parâmetros:** `[$1]` — pasta (default: `.`)
- **Usa:** `ncdu` (fallback: `du + sort`)

### `ports`
- **Objetivo:** Listar portas TCP em escuta
- **Usa:** `sudo lsof`
- **⚠️ Requer:** sudo

### `portkill`
- **Objetivo:** Matar processo numa porta
- **Parâmetros:** `$1` — número da porta
- **⚠️ Requer:** sudo
- **Comportamento:** Mostra PID/nome do processo e pede confirmação antes de matar

### `serve`
- **Objetivo:** Servidor HTTP na pasta atual
- **Parâmetros:** `[$1]` — porta (default: 8000)
- **Usa:** `python3 -m http.server`

### `qrcode`
- **Objetivo:** Gerar QR code no terminal
- **Parâmetros:** `$@` — texto ou URL
- **Usa:** `qrencode -t ANSIUTF8`

### `myip`
- **Objetivo:** Mostrar IP público
- **Usa:** `curl ifconfig.me`

### `localip`
- **Objetivo:** Mostrar IPs locais
- **Usa:** `ip -brief addr show`

### `today`
- **Objetivo:** Mostrar data/hora atual formatada

---

## GPU/NVIDIA (40-gpu.zsh)

### `gpu`
- **Objetivo:** Executar comando com NVIDIA On-Demand
- **Parâmetros:** `$@` — comando e argumentos
- **Variáveis definidas:** `__NV_PRIME_RENDER_OFFLOAD=1`, `__GLX_VENDOR_LIBRARY_NAME=nvidia`, `__VK_LAYER_NV_optimus=NVIDIA_only`

### `gpu_mode`
- **Objetivo:** Mostrar modo prime-select atual
- **Usa:** `prime-select query`

### `gpu_status`
- **Objetivo:** Mostrar estado da GPU NVIDIA
- **Usa:** `nvidia-smi`

### `gpu_flatpak`
- **Objetivo:** Executar app Flatpak com NVIDIA
- **Parâmetros:** `$@` — app-id e argumentos
- **Usa:** `gpu flatpak run`

---

## Conversão (50-convert.zsh)

### `convert_file`
- **Objetivo:** Converter ficheiros entre formatos
- **Parâmetros:** `$1` — input, `$2` — output, `[$3]` — mode (tex/html)
- **Formatos:** md, docx, odt, doc, html, txt → pdf, html, docx, odt, tex, txt
- **Ferramentas:** pandoc, wkhtmltopdf, xelatex, libreoffice
- **Detalhes:** Ver [[05-modern-terminal-tools]]

---

## Info (60-info.zsh)

### `show_startup_info`
- **Objetivo:** Mostrar resumo do contexto do shell
- **Alias:** `shellinfo`

### `sysinfo`
- **Objetivo:** Info visual do sistema
- **Usa:** `fastfetch` (fallback: `neofetch`)

---

## Clipboard (70-clipboard.zsh)

### `extract`
- **Objetivo:** Extrair ficheiros comprimidos
- **Parâmetros:** `$1` — ficheiro
- **Ficheiro:** `35-daily.zsh`
- **Formatos:** tar.bz2, tar.gz, tar.xz, tbz2, tgz, tar, bz2, gz, zip, rar, 7z

### `cpath`
- **Objetivo:** Copiar diretório atual para clipboard
- **Usa:** `wl-copy` (Wayland) ou `xclip` (X11)

### `ccat`
- **Objetivo:** Mostrar ficheiro e copiar conteúdo para clipboard
- **Parâmetros:** `$1` — ficheiro
- **Usa:** `batcat`/`bat` + `wl-copy`/`xclip`

---

## Dotfiles (80-dotfiles.zsh)

### `dotstatus`
- **Objetivo:** Mostrar alterações no repo dotfiles
- **Usa:** `git status --short`

### `dotsync`
- **Objetivo:** Copiar configs atuais para `~/dotfiles`
- **Sincroniza:** .zshrc, .zsh_custom.d/, starship.toml, yazi/, zellij/, mise/, .wezterm.lua
- **Usa:** `rsync -a --delete`

### `dotup`
- **Objetivo:** Sync + commit + push
- **Parâmetros:** `[$@]` — mensagem de commit (default: "Update shell dotfiles")
- **Fluxo:** dotsync → git add → git commit → git push

### `dotpull`
- **Objetivo:** Pull com rebase do repo dotfiles

### `dotapply`
- **Objetivo:** Aplicar configs do repo no sistema
- **Parâmetros:** `[--force]` — salta confirmação
- **Comportamento:** Pede confirmação antes de sobrescrever (a não ser com `--force`)
- **⚠️ Risco:** Sobrescreve ficheiros locais com `rsync --delete`

### `dotdoctor`
- **Objetivo:** Diagnóstico do repo dotfiles
- **Verifica:** Remote, branch, status, ficheiros sensíveis (ssh, gnupg, tokens, etc.)

---

## Manutenção (85-maintenance.zsh)

### `health`
- **Objetivo:** Resumo completo do sistema
- **Mostra:** hostname, uptime, disco, memória, portas, dotfiles, tools

### `updateall`
- **Objetivo:** Atualizar tudo
- **Atualiza:** apt, flatpak, mise, zinit, oh-my-zsh
- **⚠️ Requer:** sudo

### `cleanup`
- **Objetivo:** Limpar sistema
- **Remove:** apt autoremove, caches (thumbnails, yarn, npm), logs systemd
- **⚠️ Requer:** sudo

### `doctor`
- **Objetivo:** Diagnóstico rápido do shell
- **Verifica:** Tempo de arranque, comandos críticos, dotfiles, prompt

---

## AI Local (42-ai.zsh)

> ⚠️ **Cold start**: modelos Ollama demoram alguns segundos na **primeira chamada** após inatividade
> porque é necessário carregar os pesos (5.2 GB para qwen3-pt, 3.3 GB para gemma3-pt) do disco para a VRAM.
> Mitigações: `OLLAMA_KEEP_ALIVE=30m` (mantém modelo em VRAM 30 min após uso) e `aiwarm` (pré-aquece manualmente).

### `ol`
- **Objetivo:** Chat com modelo AI local (Ollama) com RAG-augmented proxy
- **Parâmetros:** `[modelo] [prompt...]` ou stdin via pipe
- **Modelos (atalhos):** `qwen`/`qwen3` (default), `coder`/`code`, `deep`/`deepseek`/`r1`, `gemma`/`gemma3`
- **Nota:** Mostra aviso `⏳ A carregar modelo…` quando o modelo não está em VRAM

### `olfast`
- **Objetivo:** Chat rápido com gemma3-pt (3.3 GB — carrega mais depressa que qwen3)
- **Parâmetros:** `[prompt...]` ou stdin via pipe
- **Quando usar:** Perguntas simples e rápidas onde o tempo de arranque importa

### `aiwarm`
- **Objetivo:** Pré-aquecer modelo Ollama em background (carrega na GPU)
- **Parâmetros:** `[modelo]` (default: qwen3-pt)
- **Atalhos:** `qwen`, `coder`, `deep`/`r1`, `gemma`
- **Nota:** Não bloqueia o terminal; usa VRAM até `OLLAMA_KEEP_ALIVE` expirar (30m)
- **Auto-warm:** Ativar com `export AI_AUTOWARM=1` no `.zshrc` ou `00-core.zsh`

### `aicode`
- **Objetivo:** Assistente de código (atalho para `ol coder`)
- **Parâmetros:** `<prompt>` ou stdin via pipe

### `aiask`
- **Objetivo:** Pergunta rápida — resposta concisa (máximo 3 frases)
- **Parâmetros:** `<pergunta>`

### `aimodels`
- **Objetivo:** Listar modelos Ollama instalados localmente
- **Parâmetros:** Nenhum

### `aistatus`
- **Objetivo:** Ver modelos em memória e uso de VRAM
- **Parâmetros:** Nenhum
- **Usa:** `ollama ps` + `nvidia-smi`

### `aiembed`
- **Objetivo:** Gerar embedding de texto com `bge-m3`
- **Parâmetros:** `<texto>` ou stdin via pipe
- **Output:** Dimensões + primeiros 5 valores

### `_ai_chat` (interna)
- **Objetivo:** Enviar prompt para RAG proxy (`localhost:8484`) com fallback para Ollama
- **Parâmetros:** `<model> <prompt>`
- **Inclui:** indicador de carregamento se modelo não estiver em VRAM

### `_ai_model_loaded` (interna)
- **Objetivo:** Verifica se um modelo está atualmente carregado em VRAM (`ollama ps`)
- **Retorna:** 0 (verdadeiro) se carregado, 1 se não

---

## Data Engineering (45-data-engineering.zsh)

### `duckpq`
- **Objetivo:** Preview de ficheiro Parquet (primeiras N linhas)
- **Parâmetros:** `<ficheiro.parquet> [limite]` (default: 100)

### `pqschema`
- **Objetivo:** Mostrar schema/tipos de colunas de um Parquet
- **Parâmetros:** `<ficheiro.parquet>`

### `pqcount`
- **Objetivo:** Contar linhas de um ficheiro Parquet
- **Parâmetros:** `<ficheiro.parquet>`

### `pqsql`
- **Objetivo:** Query SQL ad-hoc num ficheiro Parquet (tabela exposta como `data`)
- **Parâmetros:** `<ficheiro.parquet> <query_sql>`

### `csv2pq`
- **Objetivo:** Converter CSV para Parquet
- **Parâmetros:** `<ficheiro.csv> [output.parquet]`

### `pq2csv`
- **Objetivo:** Converter Parquet para CSV
- **Parâmetros:** `<ficheiro.parquet> [output.csv]`

### `docker_clean`
- **Objetivo:** Limpar Docker (containers parados, imagens dangling, volumes órfãos)
- **Parâmetros:** Nenhum — pede confirmação antes de executar
