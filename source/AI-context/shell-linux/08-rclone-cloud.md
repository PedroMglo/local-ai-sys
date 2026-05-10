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
  - rclone
  - cloud
  - onedrive
  - googledrive
---

# ☁️ Shell — Rclone e Cloud

## Contexto

O sistema usa rclone para montar OneDrive e Google Drive como pastas locais, geridos por serviços systemd do utilizador.

Definido em: `30-rclone.zsh`

---

## Pontos de Montagem

| Serviço | Pasta Local |
|---------|-------------|
| `rclone-onedrive.service` | `~/Drives/OneDrive` |
| `rclone-googledrive.service` | `~/Drives/GoogleDrive` |

---

## Comandos Disponíveis

### `mounts` — Ver mounts ativos

```zsh
mounts
```

Mostra linhas de `mount` que contêm "rclone". Se nada aparecer, os mounts não estão ativos.

### `rclone_status` — Estado dos serviços

```zsh
rclone_status
```

Mostra o estado systemd de ambos os serviços.

### `rclone_restart` — Reiniciar serviços

```zsh
rclone_restart
```

Reinicia ambos os serviços rclone.

---

## Navegação Rápida

```zsh
drives          # cd ~/Drives
o_drive         # cd ~/Drives/OneDrive
g_drive         # cd ~/Drives/GoogleDrive
```

---

## Gestão dos Serviços

### Ver logs

```zsh
journalctl --user -u rclone-onedrive.service -f
journalctl --user -u rclone-googledrive.service -f
```

### Parar/iniciar manualmente

```zsh
systemctl --user stop rclone-onedrive.service
systemctl --user start rclone-onedrive.service
systemctl --user enable rclone-onedrive.service   # arranque automático
systemctl --user disable rclone-onedrive.service  # sem arranque automático
```

### Ver configuração rclone

```zsh
rclone config show
rclone listremotes
```

---

## Boas Práticas

1. **Não editar ficheiros grandes diretamente no mount** — copiar localmente, editar, copiar de volta
2. **Não usar `rm -rf` em pastas montadas** — pode eliminar no cloud permanentemente
3. **Verificar conectividade** antes de assumir que os ficheiros estão atualizados
4. **Usar `rclone_status`** para confirmar se os serviços estão a correr

---

## ⚠️ Comandos Perigosos a Evitar

| Comando | Risco |
|---------|-------|
| `rm -rf ~/Drives/OneDrive/` | Pode eliminar tudo no OneDrive |
| `rclone sync local remote:` | Pode sobrescrever remote com local vazio |
| `rclone delete remote:` | Apaga tudo no remote |
| `rclone purge remote:path` | Apaga pasta e conteúdo no remote |

### Comandos seguros

| Comando | Descrição |
|---------|-----------|
| `rclone ls remote:` | Lista ficheiros (read-only) |
| `rclone lsd remote:` | Lista pastas (read-only) |
| `rclone copy local remote:` | Copia sem apagar destino |
| `rclone check local remote:` | Compara sem alterar |
| `rclone size remote:` | Mostra espaço usado |

---

## Troubleshooting

### Mounts não aparecem

```zsh
mounts                    # verificar se há output
rclone_status             # verificar serviços
systemctl --user status rclone-onedrive.service
```

Se o serviço falhou:
```zsh
journalctl --user -u rclone-onedrive.service --no-pager -n 50
```

### Permissão negada nos mounts

```zsh
# Verificar que a pasta existe
ls -la ~/Drives/

# Verificar opções de mount
cat ~/.config/systemd/user/rclone-onedrive.service
```

### Token expirado

```zsh
# Reconfigurar remote
rclone config reconnect onedrive:
```

### Ficheiros desatualizados

O rclone mount pode ter cache. Para forçar refresh:

```zsh
rclone_restart
# ou
ls ~/Drives/OneDrive/   # trigger lazy refresh
```
