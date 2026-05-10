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
  - meta
---

# 📖 Shell Linux — Knowledge Base

## O que é esta pasta

Uma base de conhecimento técnica gerada automaticamente a partir da configuração Zsh em `~/.zsh_custom.d/`. Contém documentação detalhada de todos os aliases, funções, ferramentas e workflows do terminal.

## Como foi gerada

- **Data:** 2026-05-01
- **Ferramenta:** GitHub Copilot CLI (Claude Opus 4.6)
- **Método:** Análise estática dos 16 ficheiros em `~/.zsh_custom.d/`
- **Nenhum ficheiro original foi alterado**
- **Nenhum comando foi executado**

## Ficheiros mais importantes

| Ficheiro | Para quê |
|----------|----------|
| `00-shell-index.md` | Ponto de entrada — índice de tudo |
| `11-cheatsheet.md` | Referência rápida para uso diário |
| `13-improvement-backlog.md` | Melhorias pendentes |
| `12-troubleshooting.md` | Resolver problemas |

## Como usar com Copilot

Ao pedir ajuda sobre o terminal, referenciar estes ficheiros como contexto:

```
"Usando a minha configuração shell documentada em ~/Obsidian/Vault/AI-context/shell-linux/,
como posso [fazer X]?"
```

Exemplos de perguntas:
- "Quais aliases tenho para listagem de ficheiros?"
- "Como funciona o meu sistema de dotfiles?"
- "Que melhorias posso fazer ao meu setup?"
- "Como resolvo o problema X com rclone?"

## Como atualizar esta documentação

Quando alterares a tua configuração shell:

1. Pedir ao Copilot para re-analisar:
   ```
   "Analisa novamente ~/.zsh_custom.d/ e atualiza a documentação em
   ~/Obsidian/Vault/AI-context/shell-linux/"
   ```

2. Ou atualizar ficheiros específicos:
   ```
   "Atualiza o ficheiro 02-aliases.md com base no estado atual de ~/.zsh_custom.d/"
   ```

## Estrutura

```
shell-linux/
├── README.md                    ← este ficheiro
├── 00-shell-index.md            ← índice principal
├── 01-shell-overview.md         ← visão geral do setup
├── 02-aliases.md                ← todos os aliases
├── 03-functions.md              ← todas as funções
├── 04-navigation-and-files.md   ← navegação e ficheiros
├── 05-modern-terminal-tools.md  ← ferramentas modernas
├── 06-git-and-dotfiles.md       ← git e dotfiles
├── 07-gpu-nvidia.md             ← GPU NVIDIA
├── 08-rclone-cloud.md           ← rclone e cloud
├── 09-clipboard.md              ← clipboard
├── 10-maintenance.md            ← manutenção
├── 11-cheatsheet.md             ← cheat sheet
├── 12-troubleshooting.md        ← troubleshooting
```

## Licença

Documentação pessoal. Gerada para uso privado.
