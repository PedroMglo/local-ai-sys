# Auditoria Técnica — Sistema Linux/Zorin OS

**Data:** 2026-05-01  
**Sistema:** Zorin OS 18.1 (Ubuntu Noble)  
**Kernel:** 6.17.0-20-generic  
**Sessão:** Wayland (zorin:GNOME)  
**Shell:** zsh 5.9  

---

## 1. Resumo Executivo

O sistema está em bom estado geral. As principais áreas de atenção são:

- **Docker** ocupa ~80 GB (images + build cache) — principal candidato a limpeza
- **Múltiplos drivers NVIDIA** instalados (535, 580, 590) — apenas o 580 está ativo
- **6 kernels** instalados — podem ser reduzidos a 2-3
- **PostgreSQL** está ativo no arranque mas sem clusters configurados
- **Boot time** de ~1m19s — pode ser melhorado
- **Segurança** está razoável: firewall UFW ativo, fail2ban configurado, SSH com chaves Ed25519

**Nada crítico encontrado.** As recomendações são de otimização e limpeza.

---

## 2. Estado Geral do Sistema

| Componente | Estado | Nota |
|-----------|--------|------|
| OS | Zorin OS 18.1 (Noble) | Atual |
| Kernel | 6.17.0-20-generic | Atual (6.17.0-22 disponível) |
| Sessão | Wayland | ✅ |
| Shell | zsh 5.9 | ✅ |
| RAM | 30 GB (6.6 GB usada) | ✅ Excelente |
| Swap | 6 GB (zram, quase sem uso) | ✅ |
| Disco | 745 GB, 330 GB usados (47%) | ⚠️ Crescente |
| GPU | RTX 4060 Max-Q, driver 580.126.09 | ✅ |
| Docker | Ativo, 80+ GB em images/cache | ⚠️ |
| Pacotes APT | ~3035 instalados | Normal |
| Pacotes manuais | 618 | Normal |
| Pacotes atualizáveis | 6 | ✅ Poucos |
| Pacotes órfãos | 0 (autoremove vazio) | ✅ |
| Snaps | 8 (maioria são bases/runtime) | ✅ |
| Flatpaks | ~90 (muitas apps criativas) | Normal |
| Boot time | 1m 19s | ⚠️ Lento |

---

## 3. Atualizações Recomendadas

### Pacotes APT pendentes (6)
- `libnetplan1` → 1.1.2-8ubuntu1~24.04.2
- `libpam-sss` → 2.9.4-1.1ubuntu6.4
- `lshw` → 02.19.git.2021.06.19.996aaad9c7-2ubuntu0.24.04.1
- `netplan-generator` → 1.1.2-8ubuntu1~24.04.2
- `netplan.io` → 1.1.2-8ubuntu1~24.04.2
- `python3-netplan` → 1.1.2-8ubuntu1~24.04.2

**Risco:** Baixo. São atualizações de segurança/bugfix.

### Kernel disponível
- Kernel 6.17.0-22 está instalado mas não é o ativo (a correr 6.17.0-20)
- Requer reboot para usar o mais recente

---

## 4. Limpeza Segura Recomendada

### Alta prioridade — Docker (~56 GB recuperáveis)
| Item | Tamanho | Recuperável |
|------|---------|-------------|
| Build cache não utilizado | 38.6 GB | ~16.6 GB |
| Images não utilizadas | 42 GB | ~17.6 GB |
| Containers parados | 250 KB | 250 KB |
| Volumes não utilizados | 713 MB | ~390 MB |
| **Total estimado** | | **~35 GB** |

### Média prioridade — Kernels antigos
| Kernel | Estado |
|--------|--------|
| 6.17.0-22-generic | Instalado (mais recente) |
| 6.17.0-20-generic | **Em uso** |
| 6.17.0-19-generic | Pode remover |
| 6.17.0-14-generic | Pode remover |
| 6.14.0-37-generic | Pode remover |
| 6.8.0-110-generic | Pode remover |
| 6.8.0-107-generic | Pode remover |

**Manter:** 6.17.0-22 + 6.17.0-20 (atual). Remover restantes = ~2-3 GB.

### Média prioridade — Drivers NVIDIA redundantes
| Driver | Estado |
|--------|--------|
| nvidia-driver-580-open | **Ativo** ✅ |
| nvidia-dkms-535 / nvidia-compute-utils-535 | ❌ Desnecessário |
| nvidia-dkms-590 / nvidia-compute-utils-590 | ❌ Desnecessário |
| linux-modules-nvidia-535-server-* | ❌ Desnecessário |
| linux-modules-nvidia-590-open-* | ❌ Desnecessário (exceto kernel ativo) |

### Baixa prioridade
| Item | Tamanho | Nota |
|------|---------|------|
| ~/.cache | 2.4 GB | Normal, pode limpar thumbnails |
| Journalctl | 282 MB | Normal (14 dias é razoável) |
| /snap | 2.6 GB | Normal para 8 snaps |
| Lixo | 84 KB | Praticamente vazio |

---

## 5. Coisas a NÃO Remover

| Item | Razão |
|------|-------|
| `preload` | Otimiza arranque de apps frequentes |
| `tlp` + `thermald` | Gestão de energia laptop — essenciais |
| `fail2ban` | Proteção SSH ativa |
| `zram-tools` | Swap comprimido — melhor que swap em disco |
| `nvidia-persistenced` | Mantém driver carregado, reduz latência GPU |
| `containerd.service` | Necessário para Docker |
| `snapd` | Necessário para ChatGPT Linux e runtimes |
| `mullvad-daemon` | VPN — manter se usas |
| `unattended-upgrades` | Segurança automática |
| `apparmor` | Segurança do sistema |
| `auditd` | Auditoria de segurança — bom ter |
| Flatpaks criativos | Kdenlive, Blender, Krita, etc. — mantém se usas |
| `openjdk-11-jdk` / `openjdk-17-jdk` | Necessários para Spark/apps Java |
| `r-base` / `rstudio` | Manter se usas R |
| `postgresql` | Manter, mas considerar desativar arranque automático |

---

## 6. Riscos de Segurança Encontrados

### 🟢 Baixo risco

| Item | Estado | Nota |
|------|--------|------|
| Firewall UFW | ✅ Ativo (enabled) | Configuração não verificável sem sudo |
| Fail2ban | ✅ Ativo | Proteção contra brute-force SSH |
| SSH | Chaves Ed25519 | ✅ Boas práticas |
| Permissões SSH | 600 (privadas), 644 (públicas) | ✅ Corretas |
| rclone.conf | Permissões 600 | ✅ Só o utilizador pode ler |
| Dotfiles (.zshrc) | Permissões 644 | ✅ Normal |

### 🟡 Atenção

| Item | Risco | Recomendação |
|------|-------|--------------|
| X11Forwarding=yes (sshd) | Médio-baixo | Desativar se não usas X forwarding |
| `gnome-remote-desktop` ativo | Médio | Verificar se está configurado/necessário |
| OpenSSH server ativo | Médio-baixo | Normal se acedes remotamente |
| Portas em escuta | Apenas DNS local (53) | ✅ Mínimo |
| `authorized_keys` tem 1 chave | Info | Verificar se é tua |
| Scripts em ~/.local/bin | Baixo | São ferramentas conhecidas (copilot, mise, lazygit, etc.) |

### 🟢 Sem problemas

| Item | Nota |
|------|------|
| Portas expostas | Nenhuma externamente (apenas 127.0.0.x) |
| Executáveis suspeitos | Nenhum encontrado |
| Dotfiles | Todos com permissões normais |
| rclone | Bem configurado, ficheiro protegido |

---

## 7. Melhorias de Performance

### Boot time (1m 19s → potencial <30s)

| Serviço | Tempo | Ação sugerida |
|---------|-------|---------------|
| `NetworkManager-wait-online` | 1m 0s | Desativar (raramente necessário) |
| `plymouth-quit-wait` | 8s | Normal (splash screen) |
| `snapd.seeded` | 2s | Normal |
| `snapd` | 2s | Normal |
| `gpu-manager` | 1.8s | Normal (hybrid GPU) |
| `docker.service` | ~1s | Considerar socket activation |

**Maior ganho:** Desativar `NetworkManager-wait-online.service` (1 minuto!)

### Disco

| Ação | Ganho estimado |
|------|----------------|
| Docker prune | ~35 GB |
| Kernels antigos | ~2-3 GB |
| Drivers NVIDIA antigos | ~500 MB |
| Logs (se >14 dias) | Já limitado |

### RAM
- Uso atual: 6.6 GB / 30 GB — excelente, sem problemas

---

## 8. Melhorias para Desenvolvimento/Data Engineering

### Docker
- Build cache de 38.6 GB é excessivo — limpar periodicamente
- 9 containers parados — podem ser removidos
- Considerar usar `docker system prune --filter "until=720h"` mensal

### Python
- Versão 3.12.3 (sistema) — atual
- `uv` instalado via mise — ✅ excelente
- `pipx` disponível — ✅

### Java/Spark
- OpenJDK 11 + 17 + 21 instalados — redundante ter 3 versões
- OpenJDK 21 é suficiente para Spark moderno
- Considerar remover JDK 11 (a menos que projeto específico exija)

### Node.js
- v18.19.1 (LTS antigo, EOL abril 2025) — **desatualizado**
- Recomendação: atualizar para Node 20 LTS ou 22 LTS via mise

### DuckDB
- Instalado em ~/.local/bin — ✅
- Sem problemas

### Git
- v2.43.0 — ligeiramente antigo (2.45+ disponível) mas funcional
- `git-delta` instalado — ✅ boas práticas

### PostgreSQL
- Serviço ativo mas sem clusters visíveis
- Se não usas ativamente, desativar arranque automático economiza recursos

### Ferramentas via mise
- atuin, uv, yazi, zellij — ✅ bem gerido

---

## 9. Melhorias para Terminal/Zsh

### Estado atual: Muito bom ✅
- zsh 5.9 + starship + fzf + zoxide + eza
- Scripts organizados em ~/.zsh_custom.d/ (15 ficheiros, numerados)
- Funções de manutenção (`health`, `doctor`, `cleanup`, `updateall`)

### Sugestões

| Melhoria | Prioridade | Nota |
|----------|-----------|------|
| Instalar `bat` | Alta | Único gap no toolkit moderno |
| Instalar `nvtop` | Média | Monitor GPU dedicado |
| Instalar `btop` | Baixa | Já tens htop |
| Considerar tmux/zellij | Info | zellij já instalado via mise ✅ |
| atuin para histórico | Info | Já instalado via mise ✅ |

### Performance do shell
- Testar com `time zsh -i -c exit` — se >500ms, investigar plugins
- 15 ficheiros em .zsh_custom.d — número razoável
- zinit como plugin manager — bom para lazy loading

---

## 10. Plano de Ação por Prioridade

### 🔴 Alta (fazer esta semana)

1. **Limpar Docker** — recuperar ~35 GB
2. **Desativar NetworkManager-wait-online** — reduzir boot em ~1 minuto
3. **Atualizar 6 pacotes APT pendentes** — segurança
4. **Verificar se gnome-remote-desktop é necessário** — segurança

### 🟡 Média (fazer este mês)

5. **Remover kernels antigos** (manter 6.17.0-20 e 6.17.0-22) — ~2-3 GB
6. **Remover drivers NVIDIA 535 e 590** — limpeza
7. **Atualizar Node.js** para v20 ou v22 LTS via mise
8. **Desativar PostgreSQL do arranque** (se não usas ativamente)
9. **Instalar bat** (`sudo apt install bat`)
10. **Considerar desativar X11Forwarding** no sshd

### 🟢 Baixa (quando conveniente)

11. **Remover OpenJDK 11** se nenhum projeto o exige
12. **Instalar nvtop** para monitorização GPU
13. **Limpar snap cores antigos** (core20/2717 se 2769 já existe)
14. **Verificar se ChatGPT Linux snap é necessário** (última versão 1.0.0)
15. **Considerar mover Flatpaks pouco usados** para apt (se disponíveis)
16. **Rever flatpaks** — 90 apps é muito; identificar as não usadas

---

## 11. Comandos Sugeridos

### ✅ Comandos seguros (executar sem preocupação)

```bash
# Atualizar pacotes pendentes
sudo apt update && sudo apt upgrade -y

# Limpar Docker (images não usadas + build cache antigo)
docker system prune -a --filter "until=720h"

# Ver espaço Docker antes/depois
docker system df

# Verificar gnome-remote-desktop
systemctl is-active gnome-remote-desktop
gsettings get org.gnome.desktop.remote-desktop.rdp enable

# Verificar tempo de arranque do zsh
time zsh -i -c exit

# Ver que kernels estão instalados
dpkg --list | grep linux-image
```

### ⚠️ Comandos que precisam de confirmação

```bash
# Desativar NetworkManager-wait-online (melhora boot em ~1 min)
# RISCO: Pode afetar serviços que dependem de rede no boot
sudo systemctl disable NetworkManager-wait-online.service

# Remover kernels antigos (VERIFICAR PRIMEIRO qual está ativo com uname -r)
sudo apt purge linux-image-6.8.0-107-generic linux-image-6.8.0-110-generic
sudo apt purge linux-image-6.14.0-37-generic linux-image-6.17.0-14-generic linux-image-6.17.0-19-generic

# Remover drivers NVIDIA antigos
sudo apt purge nvidia-dkms-535 nvidia-compute-utils-535 nvidia-kernel-common-535
sudo apt purge nvidia-dkms-590 nvidia-compute-utils-590 nvidia-kernel-common-590

# Desativar PostgreSQL do arranque (ainda podes iniciar manualmente)
sudo systemctl disable postgresql.service

# Desativar gnome-remote-desktop (se não usas)
sudo systemctl disable gnome-remote-desktop.service
sudo systemctl stop gnome-remote-desktop.service

# Desativar X11Forwarding no SSH
# Editar /etc/ssh/sshd_config: X11Forwarding no
# Depois: sudo systemctl restart sshd

# Limpar build cache Docker agressivamente
docker builder prune --all

# Instalar bat
sudo apt install bat
```

### ⛔ Comandos perigosos — EVITAR

```bash
# NÃO fazer sem backup verificado:
docker system prune -a --volumes  # Remove TODOS os volumes (pode perder dados)
sudo apt autoremove --purge       # Pode remover dependências necessárias se mal configurado
rm -rf ~/.cache                   # Pode causar problemas em apps
sudo purge-old-kernels            # Prefere remover um a um com apt purge
```

---

## Notas Finais

- O sistema está bem mantido e com boas práticas de segurança
- O maior "desperdício" é o Docker (80+ GB) — limpeza regular resolve
- O boot time pode melhorar drasticamente com uma alteração (NetworkManager-wait-online)
- Stack de terminal está moderna e bem organizada
- Não há riscos de segurança graves
- As funções `health`, `doctor`, `cleanup` que já tens cobrem manutenção rotineira

**Próximo passo recomendado:** Executar os comandos de "Alta prioridade" um a um, começando pela limpeza Docker.
