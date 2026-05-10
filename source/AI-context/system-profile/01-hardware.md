# Hardware

## CPU
- 24 threads (1 socket)
- Arquitetura x86_64
- Adequado para compilações paralelas, Docker multi-container, builds pesados

## RAM
- 32 GB total (~25 GB disponível em uso normal)
- Suficiente para Docker com múltiplos containers, DuckDB com datasets médios, Spark local
- Limitação: para datasets muito grandes em memória (>20 GB), considerar spill-to-disk

## GPU
- NVIDIA GeForce RTX 4060 Max-Q (Mobile)
- 8 GB VRAM (GDDR6)
- GPU integrada AMD (para display)
- Ver detalhes em [[04-gpu-nvidia]]

## Disco
- NVMe ~954 GB (single drive)
- Ver detalhes em [[03-storage]]

## Implicações práticas
- Máquina capaz para desenvolvimento full-stack, data engineering local, ML com modelos pequenos/médios
- 24 threads permitem builds paralelos rápidos (make -j, cargo, webpack)
- 32 GB RAM é confortável para Docker + IDE + browser + DB local
- Limitação principal: VRAM de 8 GB limita treino de modelos grandes (fine-tuning de LLMs >7B parâmetros será difícil)
