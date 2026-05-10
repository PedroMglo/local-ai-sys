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
  - gpu
  - nvidia
  - gaming
---

# 🎮 Shell — GPU NVIDIA

## Contexto

Sistema híbrido Intel/AMD + NVIDIA com PRIME Render Offload. A GPU integrada é usada por defeito para poupar bateria; a NVIDIA é ativada on-demand para aplicações que precisam de mais desempenho.

Definido em: `40-gpu.zsh`

---

## Comandos Disponíveis

### `gpu` — Executar com NVIDIA

```zsh
gpu <comando> [argumentos...]
```

Define variáveis de offload e executa o comando:

```zsh
gpu blender
gpu steam
gpu python script.py
gpu glxinfo | grep OpenGL
```

**Variáveis definidas:**
- `__NV_PRIME_RENDER_OFFLOAD=1`
- `__GLX_VENDOR_LIBRARY_NAME=nvidia`
- `__VK_LAYER_NV_optimus=NVIDIA_only`

### `gpu_mode` — Ver modo atual

```zsh
gpu_mode
```

Mostra o modo configurado no `prime-select`:
- `on-demand` — GPU NVIDIA só quando pedida (normal)
- `nvidia` — GPU NVIDIA sempre ativa
- `intel` — apenas GPU integrada

### `gpu_status` — Estado da GPU

```zsh
gpu_status
```

Executa `nvidia-smi` e mostra:
- GPU(s) disponíveis
- Driver instalado
- Processos a usar a GPU
- Memória utilizada
- Temperatura

### `gpu_flatpak` — Apps Flatpak com NVIDIA

```zsh
gpu_flatpak com.valvesoftware.Steam
gpu_flatpak org.blender.Blender
```

Internamente executa: `gpu flatpak run <app-id>`

---

## Como Verificar se a NVIDIA Está Ativa

```zsh
# Ver se nvidia-smi está disponível
nvidia-smi

# Ver modo prime-select
gpu_mode

# Verificar qual GPU está a ser usada por uma app
gpu glxinfo | grep "OpenGL renderer"
# Deve mostrar algo como "NVIDIA GeForce..."

# Ver processos na GPU
nvidia-smi -l 1    # atualiza a cada segundo
```

---

## Jogos

### Steam (nativo)

```zsh
gpu steam
```

### Steam (Flatpak)

```zsh
gpu_flatpak com.valvesoftware.Steam
```

### Outros jogos/apps

```zsh
gpu ./jogo
gpu wine jogo.exe
```

### No Steam (per-game)

Nas propriedades do jogo, Launch Options:

```
__NV_PRIME_RENDER_OFFLOAD=1 __GLX_VENDOR_LIBRARY_NAME=nvidia __VK_LAYER_NV_optimus=NVIDIA_only %command%
```

---

## Troubleshooting

### `nvidia-smi` não encontrado

```zsh
# Verificar se o driver está instalado
dpkg -l | grep nvidia-driver
# ou
ubuntu-drivers list

# Instalar
sudo ubuntu-drivers install
# ou
sudo apt install nvidia-driver-XXX
```

### `prime-select` não encontrado

```zsh
sudo apt install nvidia-prime
```

### GPU não está a ser usada (mesmo com `gpu`)

```zsh
# Verificar módulo kernel
lsmod | grep nvidia

# Se vazio, o módulo pode não estar carregado
sudo modprobe nvidia

# Verificar se o sistema é Optimus
prime-select query
```

### Performance fraca mesmo com NVIDIA

```zsh
# Verificar se está em modo on-demand
gpu_mode

# Verificar driver
nvidia-smi

# Verificar se Vulkan reconhece a NVIDIA
gpu vulkaninfo | grep "GPU id"
```

### Mudar para NVIDIA sempre ativa (não recomendado para portáteis)

```zsh
sudo prime-select nvidia
# Requer logout/restart
```

### Voltar a on-demand

```zsh
sudo prime-select on-demand
# Requer logout/restart
```

---

## Notas Importantes

- O comando `gpu` **não** altera o modo global — apenas afeta a execução daquele comando
- Em modo `on-demand`, a NVIDIA pode estar em standby (poupa bateria)
- Para verificar consumo: `nvidia-smi` mostra potência e temperatura
- O ficheiro `40-gpu.zsh` começa com `unalias gpu 2>/dev/null` para evitar conflitos com plugins que possam definir o mesmo alias
