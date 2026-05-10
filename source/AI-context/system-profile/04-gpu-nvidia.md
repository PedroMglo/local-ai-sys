# GPU NVIDIA

## Especificações
- **Modelo**: NVIDIA GeForce RTX 4060 Max-Q (Mobile)
- **Arquitetura**: Ada Lovelace (AD107M)
- **VRAM**: 8 GB GDDR6
- **TDP**: 55W (variante mobile)
- **Driver**: 580.126.09
- **CUDA**: 13.0

## GPU integrada
- AMD (device 150e) — usada para display/desktop
- Sistema híbrido: AMD para desktop, NVIDIA para compute/gaming

## Capacidades CUDA
- CUDA 13.0 permite usar as versões mais recentes de PyTorch, TensorFlow, e RAPIDS
- Tensor Cores de 4ª geração (útil para inferência FP16/INT8)
- RT Cores (ray tracing, menos relevante para dev)
- Suporta NVIDIA Container Toolkit para GPU em Docker

## Implicações práticas

### Machine Learning
- Inferência de modelos até ~7B parâmetros (quantizados INT4/INT8)
- Fine-tuning de modelos pequenos (<3B) com LoRA/QLoRA
- Limitação: 8 GB VRAM insuficiente para treino de modelos >7B sem offloading
- Frameworks: PyTorch, TensorFlow, ONNX Runtime GPU

### Data Engineering
- RAPIDS cuDF para acelerar operações Pandas em GPU
- cuDNN disponível para deep learning
- Spark com RAPIDS plugin possível mas limitado pela VRAM

### Docker
- Suporta `--gpus all` com NVIDIA Container Toolkit
- Verificar se nvidia-container-toolkit está instalado
- Imagens base: nvidia/cuda:13.0-runtime, nvidia/cuda:13.0-devel

### Limitações
- 8 GB VRAM é o bottleneck principal para ML pesado
- TDP 55W limita performance sustentada vs desktop (throttling possível)
- Max-Q = variante de menor consumo, ~15-20% mais lenta que desktop RTX 4060
