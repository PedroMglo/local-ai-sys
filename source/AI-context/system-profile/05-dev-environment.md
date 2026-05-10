# Ambiente de Desenvolvimento

## Gestor de pacotes
- **apt** (base Ubuntu/Debian)
- **pipx** para ferramentas Python isoladas
- **mise** para gestão de versões de ferramentas (runtime manager)

## Terminal e shell
| Ferramenta | Descrição |
|------------|-----------|
| zsh 5.9 | Shell principal |
| starship | Prompt customizável e rápido |
| fzf | Fuzzy finder para ficheiros, histórico, etc. |
| zoxide | cd inteligente (baseado em frequência) |
| yazi | File manager de terminal (via mise) |

## Ferramentas de busca e ficheiros
| Ferramenta | Descrição |
|------------|-----------|
| ripgrep (rg) | Pesquisa rápida em ficheiros (substituto de grep) |
| fd | Alternativa rápida ao find |
| eza | Substituto moderno do ls |

## Containers e dados
| Ferramenta | Descrição |
|------------|-----------|
| Docker | Containers (verificar se Docker Compose está disponível) |
| DuckDB | Base de dados analítica local (excelente para Parquet/CSV) |
| rclone | Gestão de cloud storage (OneDrive, Google Drive) |

## Python
- python3 disponível (versão do sistema)
- pipx para instalar CLI tools Python
- Recomendação: usar mise ou pyenv para gerir múltiplas versões Python

## Clipboard
- wl-copy (Wayland) + xclip (X11 fallback)
- Útil para integração terminal ↔ GUI

## Ferramentas em falta
- **bat** — alternativa a cat com syntax highlighting (recomendado instalar: `sudo apt install bat`)
- Verificar: Docker Compose, Node.js/npm, Java/JVM (necessário para Spark)

## Implicações práticas
- Stack moderna de terminal com ferramentas rápidas em Rust (rg, fd, eza, zoxide, starship)
- DuckDB local permite queries SQL sobre Parquet/CSV sem infraestrutura
- Docker disponível para containers de desenvolvimento e data pipelines
- mise permite gerir versões de ferramentas sem conflitos com o sistema
- Falta bat para visualização de código no terminal com highlighting
