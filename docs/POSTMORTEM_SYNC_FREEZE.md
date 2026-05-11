# Post-mortem: `rag sync --all` causa freeze total da máquina

**Data:** 2026-05-10
**Severidade:** Crítica — máquina inutilizável, requer hard reset
**Componente:** `obsidian_rag/pipeline/sync.py` → `sync_repos()`
**Hardware:** Zorin OS 18.1, 32 GB RAM, 24 threads (i7), RTX 4060 Max-Q 8 GB VRAM
**Estado:** ✅ RESOLVIDO — Bounded Ingest Pipeline (v0.5.0, 2026-05-10) + hotfixes adicionais (v0.5.1, 2026-05-11)

---

## 0. Estado de resolução

> **O problema descrito neste post-mortem está completamente resolvido.** O freeze da máquina foi eliminado pela reescrita arquitetural do pipeline (Fase 13 — Bounded Ingest Pipeline, v0.5.0, 2026-05-10). Adicionalmente, em 2026-05-11, durante a primeira execução de `rag sync --all` pós-reescrita, foram descobertos e corrigidos 3 bugs críticos adicionais (ver Secção 12).
>
> O documento é preservado como referência de arquitectura e para documentar as lições aprendidas.

---

## 1. Resumo executivo

Ao executar `rag sync --all` com 5 repositórios Git configurados, a máquina ficou completamente bloqueada em menos de 40 segundos — RAM subiu de ~22% para >90%, CPU saturou em todos os cores, e o sistema operativo ficou sem recursos para manter o desktop responsivo. O utilizador teve de cancelar o processo manualmente (Ctrl+C) para evitar um hard reset.

O sistema de protecção de recursos (`should_throttle()`) estava implementado mas **não conseguiu prevenir o problema** porque verificava recursos _entre_ operações, enquanto o pico acontecia _dentro_ de uma operação massiva e ininterruptível.

---

## 2. Timeline do incidente

```
t=0s    rag sync --all inicia
        RAM: 22% (~7.3 GB usados de 32.7 GB)
        CPU: 5-17% por core

t=0-2s  sync_notes() executa
        537 chunks já existentes, nenhum novo — completa instantaneamente
        _wait_for_resources() verifica: tudo OK ✅

t=2s    sync_repos() inicia
        should_throttle() verifica: tudo OK ✅
        Lança ThreadPoolExecutor(max_workers=4)
        Submete 4 repos simultaneamente:
          - SPEECH-LAB (577 chunks)
          - ApacheSpark-CD
          - obsidian-rag
          - Git_Concepts (26 chunks)
        5.º repo (Python_Stud, 323 chunks) fica na fila

t=2-15s Fase de chunking paralelo
        4 threads fazem ast.parse() simultaneamente em 4 repos
        Cada thread:
          1. Lê TODOS os ficheiros .py do repo para memória
          2. Faz ast.parse() de cada um (cria AST completo em memória)
          3. Extrai código fonte de cada nó (strings grandes)
          4. Cria objectos Chunk com texto + metadata + hash
        CPU satura: todos os 12 cores físicos (24 threads) activos
        RAM começa a subir: ASTs + código fonte × 4 repos simultâneos

t=15-25s Chunks acumulam-se
        3 repos completam: SPEECH-LAB (577), Git_Concepts (26), Python_Stud (323)
        all_repo_chunks.extend() acumula 926+ chunks na lista
        Cada chunk contém: texto completo da função/classe + metadata
        Memória estimada: ~926 chunks × ~2000 chars × ~2 bytes = ~3.7 MB de texto puro
        MAS: objectos Python têm overhead — cada Chunk, dict, str = ~500 bytes overhead
        Total estimado em objectos: ~10-15 MB
        MAIS: os chunks dos repos ainda em processamento também em memória

t=25-35s Embedding em massa
        sync_repo_to_chroma(all_repo_chunks) → sync_to_chroma()
        batch_size=100 (auto_tune calculou 100 para 32 GB RAM)
        embed_texts() envia 100 textos de uma vez ao Ollama via HTTP POST
        Ollama carrega bge-m3 na GPU (se não estiver loaded)
        Ollama processa 100 textos → gera 100 × 1024 floats
        Resposta JSON: 100 embeddings × 1024 dims × 8 bytes = ~800 KB por batch
        Mas Ollama internamente aloca:
          - Tokenização de 100 textos (~200K tokens)
          - Forward pass do modelo para cada texto
          - Pico de VRAM + RAM partilhada
        ChromaDB recebe 100 embeddings + 100 documentos + 100 metadatas
        ChromaDB indexa no HNSW (cosine) — operação CPU-intensiva

t=35-40s 💀 RAM > 90%, CPU saturado
        O utilizador vê no monitor: RAM 90%+, CPU todos os cores ao máximo
        Desktop fica irresponsivo
        Ctrl+C consegue cancelar a tempo

        SEM INTERVENÇÃO: o próximo batch de 100 embeddings causaria OOM killer
        ou o kernel começaria a fazer heavy swap → freeze total → hard reset
```

---

## 3. Causa raiz

### 3.1. Problema arquitectural: acumular → processar em vez de processar → libertar

O fluxo era:

```
TODOS os repos → chunk em paralelo → acumular TUDO na lista → embed TUDO → store TUDO
```

Isto significava que **todos os dados de todos os repos existiam em memória simultaneamente** durante toda a fase de embedding.

#### Código que causava o problema (`sync_repos()` antes da correcção):

```python
# 1. ThreadPoolExecutor lança 4 repos EM PARALELO
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(_chunk_single_repo, p): p for p in valid_paths}
    for future in as_completed(futures):
        name, repo_chunks = future.result()
        all_repo_chunks.extend(repo_chunks)  # ← ACUMULA TUDO

# 2. Só DEPOIS de TODOS os repos, faz embedding de TUDO de uma vez
sync_repo_to_chroma(all_repo_chunks)  # ← 926+ chunks × 100 batch = 10 chamadas ao Ollama
```

### 3.2. Problema de concorrência: 4 AST parsers simultâneos

`chunk_repo()` para cada repo:

1. Faz `Path(repo).rglob("*.py")` — lista todos os ficheiros Python
2. Para cada ficheiro: `open().read()` → carrega código fonte completo para memória
3. `ast.parse(source)` → cria árvore AST completa em memória (2-5× o tamanho do source)
4. Percorre a AST e extrai texto de cada função/classe

Com 4 repos em paralelo, isto é 4× a memória de ASTs + source code.

### 3.3. Problema do batch size: 100 textos por chamada HTTP ao Ollama

`auto_tune()` calculava `batch_size=100` para máquinas com ≥16 GB RAM. Isto significava que `embed_texts()` enviava 100 textos (cada um até 2000 chars) numa única chamada HTTP POST ao Ollama. O Ollama processava internamente:

- Tokenização de ~100 textos (~200K tokens estimados)
- Forward pass do bge-m3 (567M parâmetros) para cada texto
- Alocação de memória para 100 × 1024 embeddings na resposta

### 3.4. O throttle não conseguia actuar

O `should_throttle()` era chamado:

| Onde                                             | Quando                    | Resultado                           |
| ------------------------------------------------ | ------------------------- | ----------------------------------- |
| Antes de `ThreadPoolExecutor`                    | Uma vez                   | RAM 22% → OK                        |
| Entre submissões de repos (iterativo)            | Antes de cada `.submit()` | RAM 25% → OK (chunking mal começou) |
| Entre batches de embedding em `sync_to_chroma()` | A cada 100 chunks         | Já tarde — RAM já a 80%+            |

**O gap fatal:** nenhuma verificação existia _durante_ a fase de chunking paralelo. Os 4 threads corriam livremente até completarem, acumulando memória sem controlo. O throttle entre submissões era inútil porque os repos eram submetidos instantaneamente (`.submit()` é non-blocking) — a RAM só subia depois, quando os threads realmente executavam.

---

## 4. Composição da memória no pico

Estimativa do que estava em memória no momento do crash:

| Componente                 | Estimativa                            | Nota                       |
| -------------------------- | ------------------------------------- | -------------------------- |
| **Chunks finalizados**     | ~926 Chunk objects × ~3 KB cada       | `all_repo_chunks` lista    |
| **ASTs em processamento**  | 2 repos × ~50 ficheiros × ~100 KB AST | Threads ainda activos      |
| **Source code em memória** | ~50 ficheiros × ~20 KB                | `open().read()`            |
| **Embeddings (Ollama)**    | 100 × 1024 × 8 bytes = ~800 KB        | Por batch                  |
| **Ollama inference**       | ~500 MB - 2 GB                        | bge-m3 model + activations |
| **ChromaDB HNSW index**    | ~200 MB                               | Coleção existente loaded   |
| **Python overhead**        | ~500 MB                               | GC, interpreter, imports   |
| **OS + desktop**           | ~5-7 GB                               | Base antes do sync         |
| **Total estimado**         | ~8-12 GB usado pelo sync              | Sobre os ~7 GB base        |

Com 32.7 GB totais e ~7 GB base, o sync podia usar ~25 GB antes de problemas. Mas a combinação de:

- Ollama inference (que pode alocar blocos grandes de RAM temporariamente)
- ChromaDB indexing (HNSW constrói grafo em memória)
- Python GC não libertar objectos a tempo
- OS memory fragmentation

... levou a RAM para >90% em ~40 segundos.

---

## 5. Factores agravantes

### 5.1. `for range()` bug (pré-existente)

Antes da correcção do loop em `chroma.py`, havia um bug adicional:

```python
for i in range(0, total, batch_size):  # step fixo = 100
    # ... batch_size podia ser reduzido para 50 aqui ...
    batch = chunks_to_add[i : i + batch_size]  # slice de 50
    # Próximo i salta 100 → 50 chunks perdidos silenciosamente
```

Se o throttle reduzisse `batch_size` de 100 para 50 durante o loop, os chunks nas posições intermédias eram **silenciosamente ignorados** — nunca embedded nem armazenados.

### 5.2. Sem `os.nice()` — prioridade normal do processo

O processo `rag sync` corria com prioridade normal (nice 0), competindo igualmente com o desktop, o compositor gráfico (Wayland), e o Ollama serve pela CPU e memória.

### 5.3. Sem `KeyboardInterrupt` handling

Se o Ctrl+C não funcionasse a tempo (ex: kernel em I/O wait, swap thrashing), o único recurso seria SysRq+REISUB ou hard reset.

### 5.4. Sem `gc.collect()` entre repos

O garbage collector do Python opera de forma não-determinística. Objectos dos repos anteriores (chunks, ASTs, source code) podiam permanecer em memória até o GC decidir fazer uma colecção — que podia não acontecer a tempo.

---

## 6. Correcções aplicadas

### 6.1. Eliminação do ThreadPoolExecutor — processamento sequencial por repo

**Antes:**

```python
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = {executor.submit(_chunk_single_repo, p): p for p in valid_paths}
    for future in as_completed(futures):
        all_repo_chunks.extend(future.result()[1])
sync_repo_to_chroma(all_repo_chunks)
```

**Depois:**

```python
for idx, repo_path in enumerate(valid_paths, 1):
    # Throttle check antes de cada repo
    advice = should_throttle(...)

    repo_chunks = chunk_repo(repo_path, ...)          # chunk UM repo
    sync_repo_to_chroma(repo_chunks)                  # embed + store
    del repo_chunks                                    # libertar referência
    gc.collect()                                       # forçar GC
```

**Impacto na memória:** Em vez de ter chunks de 5 repos + 4 ASTs em memória simultaneamente, agora só existe 1 repo em memória de cada vez. Pico estimado: ~3-5 GB vs. ~8-12 GB.

**Impacto na velocidade:** ~20-30% mais lento (sequencial vs. 4 workers paralelos), mas completamente seguro.

### 6.2. Auto-tune mais conservador

| Parâmetro                                   | Antes                    | Depois                   | Razão                                |
| ------------------------------------------- | ------------------------ | ------------------------ | ------------------------------------ |
| `embedding_batch_size` (≥16 GB)             | 100                      | 50                       | Reduz pico de RAM por chamada Ollama |
| `embedding_batch_size` (8-16 GB)            | 50                       | 25                       |                                      |
| `embedding_batch_size` (<8 GB)              | 25                       | 15                       |                                      |
| `max_parallel_jobs`                         | `cpu_cores // 4` (max 8) | `cpu_cores // 6` (max 4) | Menos concorrência                   |
| Na máquina do utilizador (24 cores, 32 GB): | jobs=6, batch=100        | jobs=4, batch=50         |                                      |

### 6.3. `os.nice(10)` no entry point

```python
def main() -> None:
    try:
        os.nice(10)  # prioridade mais baixa que o desktop
    except OSError:
        pass
```

O scheduler do Linux dá prioridade a processos com nice mais baixo. Com nice=10, o sync cede CPU ao desktop, Wayland compositor, e outros processos interactivos. Mesmo com CPU a 100%, o desktop permanece responsivo.

### 6.4. `gc.collect()` explícito após cada repo

```python
finally:
    del repo_chunks
    gc.collect()
```

Garante que a memória do repo anterior é libertada antes de processar o próximo. Sem isto, o Python pode adiar a libertação indefinidamente.

### 6.5. `while` loop em vez de `for range()` nos batches de embedding

```python
i = 0
while i < total:
    batch = chunks_to_add[i : i + batch_size]
    # ...
    i += len(batch)  # avança pelo tamanho REAL
```

Elimina a perda silenciosa de chunks quando `batch_size` é reduzido dinamicamente.

### 6.6. `KeyboardInterrupt` handling gracioso

```python
def main() -> None:
    try:
        _main_inner()
    except KeyboardInterrupt:
        print("\n\n⚠ Interrompido pelo utilizador (Ctrl+C).")
        raise SystemExit(130)
```

---

## 7. Diagrama: fluxo de memória antes e depois

### Antes (perigoso):

```
tempo →
RAM ▲
    │                                    ╱╲ ← embedding de TUDO
    │                          ╱────────╱  ╲
    │            ╱────────────╱  chunks     ╲
    │     ╱─────╱  4 ASTs       acumulados   ╲
    │    ╱  4 repos em paralelo               ╲
    │───╱────────────────────────────────────── → 90%+ 💀
    │  ╱
    │─╱  base do sistema (~22%)
    └──────────────────────────────────────────→ tempo

    t=0   t=5    t=15      t=25     t=35   t=40
    ↑              ↑                  ↑
    start     3 repos done      embedding
              chunks acumulam   batch=100
```

### Depois (seguro):

```
tempo →
RAM ▲
    │
    │   ╱╲     ╱╲     ╱╲     ╱╲     ╱╲
    │  ╱  ╲   ╱  ╲   ╱  ╲   ╱  ╲   ╱  ╲
    │─╱────╲─╱────╲─╱────╲─╱────╲─╱────╲── → ~40-50%
    │╱  gc  ╲╱  gc ╲╱  gc ╲╱  gc ╲╱  gc ╲
    │  repo1  repo2  repo3  repo4  repo5
    │─────────────────────────────────────── base ~22%
    └──────────────────────────────────────→ tempo

    Cada repo: chunk → embed → store → gc.collect() → próximo
    Pico: apenas 1 repo em memória de cada vez
```

---

## 8. Porque é que o throttle entre operações não era suficiente

O padrão de throttle advisory funciona bem quando:

- As operações individuais são **pequenas e rápidas**
- A memória sobe **gradualmente** entre operações
- Há **oportunidade de pausa** entre picos

O padrão falha quando:

- Uma operação individual é **massiva e ininterruptível** (ex: chunking de 4 repos em paralelo)
- A memória sobe **abruptamente** durante a operação
- O pico acontece **dentro** de uma chamada que não verifica recursos internamente

### Analogia

É como ter um sensor de temperatura entre andares de um edifício, mas o fogo começa _dentro_ de um andar:

```
Andar 3: should_throttle() → OK ✅
Andar 2: [ThreadPoolExecutor: 4 repos × ast.parse() × embed_texts()] → 🔥 RAM 90%+
Andar 1: should_throttle() → nunca chega aqui
```

A solução correcta não é adicionar mais sensores — é **não ter o fogo** (processar um repo de cada vez).

---

## 9. Lições aprendidas

1. **Throttle advisory não substitui design de memória.** O `should_throttle()` é útil como segunda linha de defesa, mas a primeira defesa tem de ser arquitectural — nunca acumular dados de forma ilimitada.

2. **Paralelismo != velocidade quando o bottleneck é I/O.** O embedding via Ollama é single-threaded (GPU bound). Paralelizar o chunking apenas aumenta a memória sem acelerar o embedding.

3. **Auto-tune agressivo é perigoso.** `batch_size=100` era teoricamente seguro para 32 GB RAM, mas não contava com a memória do Ollama + ChromaDB + Python overhead + OS.

4. **`for range()` com step mutável é um bug.** O Python cria o `range()` uma vez — alterar a variável do step não tem efeito.

5. **`os.nice()` é essencial para processos batch.** Sem ele, um sync pesado compete igualmente com o desktop e pode tornar a máquina irresponsiva mesmo com RAM disponível.

6. **`gc.collect()` explícito é necessário entre operações pesadas.** O GC geracional do Python (3 gerações) pode adiar a libertação de objectos grandes se não forem detectados como lixo na geração jovem.

---

## 10. Estado actual do sistema de protecção

### Camada 1 — Design de memória (prevenção)

- Repos processados sequencialmente: chunk → embed → store → `gc.collect()`
- Apenas 1 repo em memória de cada vez
- `batch_size=50` (conservador para 32 GB)

### Camada 2 — `os.nice(10)` (responsividade)

- Processo sync com prioridade baixa
- Desktop e OS sempre responsivos

### Camada 3 — Throttle contínuo (defesa)

- `should_throttle()` antes de cada repo
- `should_throttle()` entre cada batch de embeddings
- `_wait_for_resources()` nas transições de fase

### Camada 4 — KeyboardInterrupt (escape)

- Ctrl+C sai limpo com código 130
- Mensagem clara ao utilizador

---

## 11. Ficheiros alterados (v0.4.1 → v0.5.0)

| Ficheiro                        | Alteração                                                                                                              | Impacto                 |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------- | ----------------------- |
| `obsidian_rag/pipeline/sync.py` | Eliminado ThreadPoolExecutor; processamento sequencial com `gc.collect()`; `os.nice(10)`; `KeyboardInterrupt` handling | Elimina causa raiz      |
| `obsidian_rag/store/chroma.py`  | `for range()` → `while` loop; `logging` estruturado                                                                    | Elimina perda de chunks |
| `obsidian_rag/tuning.py`        | Auto-tune conservador: batch 100→50, jobs cores÷4→cores÷6                                                              | Reduz picos             |
| `obsidian_rag/config.py`        | `graph_timeout: int = 600`                                                                                             | Timeout no graphify     |
| `obsidian_rag/graph/builder.py` | `timeout=` no subprocess; throttle em `build_graphs()`                                                                 | Graphify não pendura    |
| `rag.toml`                      | `graph_timeout = 600`                                                                                                  | Configurável            |
| `scripts/monitor_rag.sh`        | Novo script de monitorização em tempo real                                                                             | Observabilidade         |
| `tests/test_performance.py`     | Assertions actualizadas para novos valores de auto-tune                                                                | Testes                  |

---

## 12. Bugs adicionais descobertos em produção (v0.5.1, 2026-05-11)

Após a implementação do bounded ingest pipeline (v0.5.0), a primeira execução real de `rag sync --all` em produção revelou 3 bugs críticos adicionais que não foram detectados pelos testes unitários.

### 12.1 `_cleanup_stale` apagava chunks de todos os repos — CRÍTICO

**Sintoma:** Após `rag sync --all` completar com sucesso, a coleção `code_repos` ficava com 0 chunks em vez dos ~150 esperados.

**Causa raiz:**
```python
# Código com bug — chamado 5× (uma vez por repo)
def _cleanup_stale(self, source: IngestSource) -> None:
    manifest_ids = self._manifest.get_chunk_ids_for_repo(source.name)
    existing_in_store = self._store.get_existing_ids(self._collection_name)
    stale = existing_in_store - manifest_ids  # ← ERRADO: subtrai apenas IDs deste repo
    # → stale inclui chunks de TODOS os outros repos!
    self._store.delete_ids(self._collection_name, stale)
```

Em cada iteração, `existing_in_store` continha todos os IDs da coleção (5 repos), enquanto `manifest_ids` continha apenas os IDs do repo atual. A diferença apagava os chunks de todos os outros repos. Após 5 iterações: coleção vazia.

**Correcção:**
```python
# Depois da correcção — chamado UMA VEZ após todos os repos
def _cleanup_stale_global(self, all_manifest_ids: set[str]) -> None:
    existing_in_store = self._store.get_existing_ids(self._collection_name)
    stale = existing_in_store - all_manifest_ids  # union de todos os repos
    if stale:
        self._store.delete_ids(self._collection_name, stale)

# Em run():
all_manifest_ids: set[str] = set()
for source in sources:
    all_manifest_ids |= self._manifest.get_chunk_ids_for_repo(source.name)
self._cleanup_stale_global(all_manifest_ids)
```

**Impacto da correcção:** `code_repos` passou de 0 para 150 chunks.

### 12.2 `_split_long_text` loop infinito em markdown.py — CRÍTICO

**Sintoma:** Parse error silencioso para `PROJECT_OVERVIEW.md` com mensagem vazia (`Parse error for PROJECT_OVERVIEW.md: ''`). O ficheiro não era indexado.

**Causa raiz:**
```python
# Código com bug
def _split_long_text(text, max_chars, overlap):
    start = 0
    while start < len(text):
        end = start + max_chars
        if end < len(text):
            cut = text.rfind(". ", start, end)
            if cut != -1:
                end = cut + 1
        chunks.append(text[start:end])
        start = end - overlap if end < len(text) else end
        # ↑ BUG: se cut ≈ start, então end - overlap <= start
        # → start nunca avança → loop infinito → MemoryError("")
```

Quando `rfind(". ")` encontrava um boundary próximo do início do segmento, `end - overlap` podia ser ≤ `start`. O cursor ficava preso e a lista de chunks crescia indefinidamente até `MemoryError` com `str(e) == ""`.

**Correcção:**
```python
next_start = end - overlap if end < len(text) else end
start = next_start if next_start > start else end  # garante avanço
```

**Impacto da correcção:** `PROJECT_OVERVIEW.md` produz 114 chunks sem travar. RAM estável.

### 12.3 Qdrant `meta.json` corrupção — CRÍTICO

**Sintoma:** `rag sync --all` crashava imediatamente no startup com `json.decoder.JSONDecodeError: Expecting value: line 1 column 1 (char 0)` ao inicializar o `QdrantClient` em modo embedded.

**Causa raiz:** `data/qdrant/qdrant/meta.json` ficou com 0 bytes após um processo ser morto no meio de uma escrita (SIGKILL durante graphify).

**Correcção:**
```python
def _recover_meta_if_corrupt(qdrant_path: str) -> None:
    meta = Path(qdrant_path) / "meta.json"
    if _is_meta_valid(meta):
        return
    bak = meta.with_suffix(".json.bak")
    if _is_meta_valid(bak):
        shutil.copy2(bak, meta)  # restaurar de backup
        return
    # último recurso: semear estrutura mínima válida
    meta.write_text('{"collections": {}, "aliases": {}}')

# Em __init__:
_recover_meta_if_corrupt(qdrant_path)          # ANTES de QdrantClient()
self._client = QdrantClient(path=qdrant_path)
_backup_meta(qdrant_path)                      # APÓS init bem-sucedido
```

**Impacto da correcção:** Startup robusto mesmo após kills abruptos.

### 12.4 Ficheiros alterados (v0.5.1)

| Ficheiro                             | Alteração                                                        | Impacto                              |
| ------------------------------------ | ---------------------------------------------------------------- | ------------------------------------ |
| `obsidian_rag/pipeline/ingest.py`    | `_cleanup_stale_global()` substitui lógica per-repo             | `code_repos` com 150 chunks (era 0)  |
| `obsidian_rag/chunking/markdown.py`  | Guard de avanço em `_split_long_text()`                          | Sem loops infinitos em ficheiros longos |
| `obsidian_rag/store/qdrant_store.py` | `_recover_meta_if_corrupt()` + `_backup_meta()` em `__init__`   | Startup robusto após kills abruptos  |
| `obsidian_rag/pipeline/ingest.py`    | Logs `[scan]`/`[parse]`/`[embed]`/`[write]` + erros com traceback | Visibilidade em tempo real          |
