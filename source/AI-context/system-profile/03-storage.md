# Armazenamento

## Disco NVMe (~954 GB)

Layout dual-boot Windows/Linux:

| Partição | Tamanho | Tipo | Uso |
|----------|---------|------|-----|
| p1 | 260 MB | EFI (vfat) | Boot EFI |
| p2 | 16 MB | — | Reservada Windows |
| p3 | 195 GB | NTFS | Windows |
| p4 | 1.1 GB | NTFS | Recovery Windows |
| p5 | 260 MB | vfat | — |
| p6 | 757 GB | ext4 | Linux (/) |

## Espaço disponível (Linux)
- Total utilizável: ~745 GB
- Usado: ~226 GB (32%)
- Livre: ~482 GB
- Confortável para Docker images, datasets locais, e projetos

## Swap
- zram: 4 GB (comprimido em RAM)
- Total swap: 6 GB
- Adequado para evitar OOM em cargas médias

## Armazenamento cloud (rclone)
- OneDrive: ~1.1 TB disponível
- Google Drive: ~5 TB disponível
- Montados em ~/Drives/ via rclone mount
- Útil para backup e datasets grandes que não cabem localmente

## Implicações práticas
- 482 GB livres são suficientes para Docker, datasets Parquet médios, e múltiplos projetos
- Para datasets muito grandes (>100 GB), usar cloud mounts ou armazenamento externo
- NVMe garante I/O rápido para DuckDB, Parquet scans, e Docker layer caching
- Dual-boot: cuidado ao redimensionar partições
- rclone mounts não são tão rápidos como disco local — evitar queries DuckDB diretamente sobre cloud mounts
