# Sistema Linux

## Distribuição
- Zorin OS 18.1 (baseado em Ubuntu 24.04 Noble)
- Repositórios compatíveis com Ubuntu/Debian (apt)
- Suporte LTS até 2029

## Kernel
- Linux 6.17.0 (PREEMPT_DYNAMIC)
- Suporte moderno para hardware recente (NVMe, Wi-Fi 6, etc.)
- Kernel preemptivo: bom para responsividade em desktop

## Ambiente gráfico
- GNOME (variante Zorin)
- Sessão Wayland (XDG_SESSION_TYPE=wayland)
- Implicação: algumas apps legacy podem precisar de XWayland; screen sharing pode ter quirks

## Shell e terminal
- zsh 5.9 com starship prompt
- Ferramentas modernas: fzf, zoxide, eza, yazi (ver [[05-dev-environment]])

## Implicações práticas
- Base Ubuntu garante compatibilidade com a maioria dos tutoriais, Docker images, e ferramentas
- Wayland é mais moderno mas pode causar problemas com: screen recording, clipboard em SSH remoto, apps Electron antigas
- Kernel 6.17 suporta bem o hardware NVIDIA + AMD híbrido
- zsh + starship + fzf = terminal produtivo para desenvolvimento
