# Notas de Performance e Sugestões

## Limitações conhecidas

### VRAM (8 GB)
- Insuficiente para treino de LLMs >7B parâmetros sem quantização agressiva
- Fine-tuning limitado a modelos <3B (LoRA/QLoRA) ou ~7B com INT4
- Inferência confortável até ~13B quantizado (depende do modelo)
- Para ML pesado, considerar cloud (Colab Pro, Lambda, Vast.ai)

### TDP Mobile (55W)
- RTX 4060 Max-Q pode fazer throttling em cargas sustentadas
- Monitorizar temperaturas com `nvidia-smi` ou `nvtop`
- Performance ~15-20% abaixo da versão desktop

### RAM (32 GB)
- Confortável para a maioria dos cenários
- Pode ser limitante com: múltiplos containers Docker grandes + IDE + browser pesado + dataset em memória
- DuckDB faz spill-to-disk automaticamente quando a RAM não chega
- Spark local: configurar `spark.driver.memory` para não exceder ~20 GB

### Disco
- 482 GB livres — confortável mas não ilimitado
- Docker images acumulam-se rapidamente (usar `docker system prune` regularmente)
- Datasets grandes: preferir formatos colunares (Parquet) e usar cloud mounts para arquivo

## Sugestões de ferramentas em falta

| Ferramenta | Propósito | Instalação |
|------------|-----------|------------|
| bat | cat com syntax highlighting | `sudo apt install bat` |
| nvtop | Monitor GPU no terminal | `sudo apt install nvtop` |
| htop/btop | Monitor sistema avançado | `sudo apt install btop` |
| lazydocker | UI terminal para Docker | `go install github.com/jesseduffield/lazydocker@latest` ou mise |
| Node.js/npm | Runtime JavaScript (necessário para muitos projetos) | `mise use node@lts` |
| Java/JVM | Necessário para Apache Spark local | `mise use java@21` |
| uv | Gestor de pacotes Python ultrarrápido | `pipx install uv` ou `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| just | Task runner moderno (alternativa a make) | `sudo apt install just` ou mise |

## Notas por tecnologia

### Docker
- 32 GB RAM permite correr vários containers em simultâneo
- Usar `--memory` limits para evitar que um container monopolize RAM
- GPU em Docker: instalar nvidia-container-toolkit, usar `--gpus all`
- Espaço: monitorizar com `docker system df`

### DuckDB
- Excelente para queries sobre Parquet/CSV locais
- Usa memória disponível eficientemente, com spill-to-disk
- NVMe garante scans rápidos de ficheiros grandes
- Evitar queries sobre cloud mounts (rclone) — copiar localmente primeiro

### Parquet
- Formato ideal para datasets analíticos nesta máquina
- DuckDB lê Parquet nativamente sem carregar tudo em memória
- Compressão Snappy/Zstd reduz uso de disco e acelera I/O
- Para datasets >10 GB, particionar por coluna relevante

### Apache Spark (local)
- Possível correr em modo local com 24 threads
- Configurar: `spark.driver.memory=16g`, `spark.executor.memory=8g`
- Limitação: sem cluster real, útil apenas para dev/test
- Requer Java/JVM (ver sugestões acima)
- RAPIDS Accelerator possível mas limitado pela VRAM de 8 GB

### GPU / NVIDIA
- Inferência ML: confortável para modelos até ~13B quantizados
- Treino: limitado a modelos pequenos ou fine-tuning com LoRA
- Monitorizar: `nvidia-smi`, `nvtop`
- Docker GPU: verificar `nvidia-smi` dentro do container
- CUDA 13.0: compatível com PyTorch 2.x, TensorFlow 2.x, RAPIDS

### Terminal Linux
- zsh + starship + fzf + zoxide = setup produtivo
- ripgrep + fd = pesquisa rápida em projetos grandes
- Considerar tmux ou zellij para multiplexing de terminal
- eza + yazi = navegação moderna de ficheiros
