# IMPROVEMENTS AND RISKS — obsidian-rag

> **Versão:** 0.5.1 → v1.1 (plano)
> **Última atualização:** 2026-05-11
> **Âmbito:** Análise crítica de falhas, riscos, melhorias e roadmap

---

## Índice

1. [Falhas na arquitetura](#1-falhas-na-arquitetura)
2. [Problemas técnicos](#2-problemas-técnicos)
3. [Dívida técnica](#3-dívida-técnica)
4. [Possíveis bugs e inconsistências](#4-possíveis-bugs-e-inconsistências)
5. [Segurança](#5-segurança)
6. [Privacidade e dados locais](#6-privacidade-e-dados-locais)
7. [Performance](#7-performance)
8. [Escalabilidade](#8-escalabilidade)
9. [Organização do código](#9-organização-do-código)
10. [Melhorias recomendadas](#10-melhorias-recomendadas)
11. [Roadmap sugerido](#11-roadmap-sugerido)

---

## 1. Falhas na arquitetura

### 1.1 ~~Ausência de testes automatizados~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                               |
| ---------------------- | --------------------------------------------------------------------- |
| **Prioridade**         | ~~Alta~~ — Resolvido                                                  |
| **Impacto**            | Elevado — qualquer refatoração pode introduzir regressões silenciosas |
| **Complexidade**       | Média                                                                 |
| **Ficheiros afetados** | `tests/`, `pyproject.toml`                                            |

**Resolução (2026-05-10):** Implementados 83 unit tests com pytest em 5 ficheiros (`test_chunking_markdown.py`, `test_chunking_code.py`, `test_router.py`, `test_budget.py`, `test_api.py`) + `conftest.py` com fixtures partilhadas. Dependências de dev adicionadas ao `pyproject.toml` (`pytest>=8.0`, `pytest-asyncio>=0.23`, `coverage>=7.0`). Todos os testes passam em <1s sem dependências externas (Ollama, ChromaDB). Total atual: 329 testes (18 skipped) em 20 ficheiros (inclui 42 novos testes para vault_sync + cross-platform security + 25 para manifest + 10 para ingest pipeline + 21 para ResourceGovernor + 34 para VectorStore protocol + 22 para tree-sitter chunking + 6 para Dask engine). Faltam integration tests e2e com Ollama.

### 1.2 ~~Singletons mutáveis para coleções ChromaDB~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                                                                        |
| ---------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Prioridade**         | ~~Média~~ — Resolvido                                                                                          |
| **Impacto**            | Médio — dificulta testes e pode causar state leaks                                                             |
| **Complexidade**       | Baixa                                                                                                          |
| **Ficheiros afetados** | `obsidian_rag/retrieval/rag.py` (`_store`), `obsidian_rag/store/base.py`, `obsidian_rag/store/chroma_store.py` |

**Resolução (2026-05-10):** Inicialmente `_get_collection()` e `_get_code_collection()` aceitavam parâmetro `_override`. Na Phase 3, substituídos por singleton `_get_store()` que devolve um `VectorStore`. Testes usam `_get_store` mock com `ChromaVectorStore` in-memory. `_reset_collections()` renomeado para reset do `_store`. 16 integration tests validam o padrão.

### 1.3 ~~Acoplamento entre retrieval e ChromaDB~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                                                                                                                                                                                           |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Resolvido                                                                                                                                                                                                             |
| **Impacto**            | Médio — dificulta trocar o vector store por alternativas (Qdrant, Weaviate, etc.)                                                                                                                                                 |
| **Complexidade**       | Alta                                                                                                                                                                                                                              |
| **Ficheiros afetados** | `obsidian_rag/store/base.py`, `obsidian_rag/store/chroma_store.py`, `obsidian_rag/store/qdrant_store.py`, `obsidian_rag/retrieval/rag.py`, `obsidian_rag/api/app.py`, `obsidian_rag/config.py`, `obsidian_rag/cli/migrate_cmd.py` |

**Resolução (2026-05-10 — Phase 3, v0.5.0):** Implementado `VectorStore` Protocol (`@runtime_checkable`) em `store/base.py` com 5 métodos (`upsert_batch`, `delete_ids`, `get_existing_ids`, `query`, `count`) e parâmetro `collection` para suporte multi-coleção. `QueryResult` dataclass para resultados uniformes. Factory `create_store(backend=None)` lê `settings.store.backend`. Duas implementações: `ChromaVectorStore` (default, `chroma_store.py`) e `QdrantVectorStore` (opcional, `qdrant_store.py` — modo embedded ou server, 1024d cosine, `qdrant-client>=1.9` como dep opcional). `rag.py` e `app.py` refatorados para usar `_get_store()` singleton via protocolo — sem imports diretos de ChromaDB. Novo comando `rag migrate --from X --to Y --collections ...` para migração entre backends com re-embedding. Nova secção `[store]` em `rag.toml` e `StoreConfig` dataclass em `config.py`. 34 testes parametrizados em `test_vector_store.py` (19 pass Chroma, 15 skip sem qdrant-client).

### 1.4 ~~Dependência de subprocess para Graphify~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                              |
| ---------------------- | ---------------------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Resolvido                                |
| **Impacto**            | Baixo — funciona, mas era frágil e difícil de testar |
| **Complexidade**       | Baixa                                                |
| **Ficheiros afetados** | `obsidian_rag/graph/builder.py`                      |

**Resolução (2026-05-10):** Todos os `print()` substituídos por `log.info()`/`log.warning()`/`log.error()` usando logging standard. `subprocess.run` agora usa `capture_output=True, text=True` com `timeout=settings.performance.graph_timeout` (configurável, defeito 600s). Trata `TimeoutExpired` graciosamente com log de erro e skip do repo. `should_throttle()` adicionado antes de cada repo em `build_graphs()`. Erros estruturados em vez de output ao stdout.

---

## 2. Problemas técnicos

### 2.0 ~~`qdrant-client` ausente na imagem Docker~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                              |
| ---------------------- | -------------------------------------------------------------------- |
| **Prioridade**         | ~~Alta~~ — Resolvido                                                 |
| **Impacto**            | Crítico — aplicação não iniciava no Docker; `ImportError` no startup |
| **Complexidade**       | Baixa                                                                |
| **Ficheiros afetados** | `Dockerfile`, `requirements.txt`                                     |

**Causa raiz (2026-05-11):** `rag.toml` configura `[store] backend = "qdrant"` mas o Dockerfile instalava com `pip install .`, que omite extras opcionais. `qdrant-client>=1.9` está declarado em `[project.optional-dependencies] qdrant` no `pyproject.toml`.

**Resolução (2026-05-11):** Dockerfile atualizado para `pip install '.[qdrant]'`. `qdrant-client>=1.9` adicionado também a `requirements.txt` para instalações manuais.

### 2.1 ~~Estimativa de tokens por contagem de caracteres~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                                  |
| ---------------------- | ------------------------------------------------------------------------ |
| **Prioridade**         | ~~Média~~ — Resolvido                                                    |
| **Impacto**            | Médio — pode truncar contexto útil prematuramente ou ultrapassar limites |
| **Complexidade**       | Média                                                                    |
| **Ficheiros afetados** | `obsidian_rag/retrieval/budget.py`                                       |

**Resolução (2026-05-10):** `estimate_tokens()` agora usa tokenização regex word-boundary (`re.findall(r'\b\w+\b', text)`) com multiplicador 1.3× em vez de `len(text) // 4`. Mais preciso para textos multilíngues (PT + EN) e código.

### 2.2 ~~Embedding cache com LRU fixo~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                  |
| ---------------------- | -------------------------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Resolvido                                    |
| **Impacto**            | Baixo — podia desperdiçar memória ou causar cache misses |
| **Complexidade**       | Baixa                                                    |
| **Ficheiros afetados** | `obsidian_rag/embeddings/ollama.py`                      |

**Resolução (2026-05-10):** Adicionada função `clear_embed_cache()` que invoca `_cached_embed.cache_clear()`. Chamada no início de `sync_notes()` para garantir embeddings frescos após sync. O LRU continua ativo para queries repetidas durante uma sessão.

### 2.3 ~~Timeouts hardcoded no embed_texts~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                               |
| ---------------------- | --------------------------------------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Resolvido                                                 |
| **Impacto**            | Baixo — o timeout de 120s podia ser insuficiente para batches grandes |
| **Complexidade**       | Baixa                                                                 |
| **Ficheiros afetados** | `obsidian_rag/embeddings/ollama.py`, `obsidian_rag/config.py`         |

**Resolução (2026-05-10):** Novo campo `embedding_timeout: int` (default 120) em `PerformanceConfig`. Usado em `embed_texts()` em vez do valor hardcoded. Configurável via `[performance] embedding_timeout` em `rag.toml`.

### 2.4 ~~Graphify `OLLAMA_API_KEY=ollama` hardcoded~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                        |
| ---------------------- | ---------------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Resolvido                          |
| **Impacto**            | Baixo — funcionava localmente, mas era confuso |
| **Complexidade**       | Baixa                                          |
| **Ficheiros afetados** | `obsidian_rag/graph/builder.py`                |

**Resolução (2026-05-10):** Adicionado comentário inline em `builder.py` explicando que `OLLAMA_API_KEY=ollama` é um placeholder obrigatório para litellm usado pelo graphify, não uma credencial real.

---

## 3. Dívida técnica

### 3.1 ~~Sem type checking configurado~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                |
| ---------------------- | ------------------------------------------------------ |
| **Prioridade**         | ~~Média~~ — Resolvido                                  |
| **Impacto**            | Médio — bugs de tipos não são detectados estaticamente |
| **Complexidade**       | Baixa                                                  |
| **Ficheiros afetados** | `pyproject.toml`, todos os módulos                     |

**Resolução (2026-05-10):** Configurados `mypy>=1.10` e `ruff>=0.4` como dependências de desenvolvimento. `[tool.mypy]` (python_version=3.11, ignore_missing_imports=true) e `[tool.ruff]` (line-length=120, select E/F/W/I) adicionados ao `pyproject.toml`.

**Atualização (2026-05-11):** Corrigidos 15 erros de tipo reportados por mypy em 6 ficheiros: `manifest.py` (no-any-return), `governor.py` (IO[str] | None annotation), `treesitter.py` (variável `lang_module` para evitar conflito de tipo), `chroma_store.py` (type: ignore[arg-type], assert not None, dict(meta)), `migrate_cmd.py` (dict(m) para converter Mapping→dict) e `app.py` (type: ignore[dict-item], store.\_models, int(result.count)). `mypy obsidian_rag/` reporta 0 erros.

### 3.2 ~~Sem linter/formatter configurado~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                          |
| ---------------------- | ------------------------------------------------ |
| **Prioridade**         | ~~Baixa~~ — Resolvido                            |
| **Impacto**            | Baixo — inconsistências de estilo podem acumular |
| **Complexidade**       | Baixa                                            |
| **Ficheiros afetados** | `pyproject.toml`                                 |

**Resolução (2026-05-10):** `ruff>=0.4` configurado em `[tool.ruff]` com `line-length=120`, `select=["E","F","W","I"]`. Adicionado como dependência de desenvolvimento em `pyproject.toml`.

### 3.3 ~~Sem CI/CD pipeline~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                         |
| ---------------------- | ----------------------------------------------- |
| **Prioridade**         | ~~Média~~ — Resolvido                           |
| **Impacto**            | Médio — sem validação automática em commits/PRs |
| **Complexidade**       | Média                                           |
| **Ficheiros afetados** | `.github/workflows/ci.yml`                      |

**Resolução (2026-05-10):** Pipeline CI/CD completa com 3 workflows GitHub Actions:

- **`ci.yml`** — 5 jobs: lint (ruff + mypy), test matrix (ubuntu/macos/windows × Python 3.11/3.12 com pytest-cov --fail-under=30), CLI smoke (3 OS), config & vault_sync tests, security audit (secrets, .env, .gitignore, Docker host binding)
- **`docker.yml`** — Docker build com Buildx cache, compose config, sanity check (import + CLI no container)
- **`release.yml`** — Trigger em tags `v*`, reutiliza CI, build wheel/sdist, GitHub Release automático, Docker image build

Triggers: push/PR na branch main. Sem dependências de Ollama, GPU, rsync ou systemd. `Makefile` com targets `lint`, `typecheck`, `test-cov`, `ci`, `docker-build`, `docker-check`. `pyproject.toml` com `pytest-cov>=5.0` e `types-requests>=2.31` nas dev extras.

### 3.4 ~~Versão hardcoded em múltiplos locais~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                                 |
| ---------------------- | ----------------------------------------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Resolvido                                                   |
| **Impacto**            | Baixo — risco de dessincronização de versões eliminado                  |
| **Complexidade**       | Baixa                                                                   |
| **Ficheiros afetados** | `pyproject.toml`, `obsidian_rag/__init__.py`, `obsidian_rag/api/app.py` |

**Resolução (2026-05-10):** `__version__` centralizado em `__init__.py` via `importlib.metadata.version("obsidian-rag")`. `app.py` importa `__version__` em vez de hardcodar. Fonte única de verdade: `pyproject.toml`.

---

## 3.5 `PipelineConfig.max_workers` — dead code (parcialmente resolvido)

| Campo                  | Detalhe                                                                |
| ---------------------- | ---------------------------------------------------------------------- |
| **Prioridade**         | Baixa                                                                  |
| **Impacto**            | Baixo — confuso para quem lê o código, mas sem impacto funcional       |
| **Complexidade**       | Baixa                                                                  |
| **Ficheiros afetados** | `obsidian_rag/config.py` (`PipelineConfig`), `rag.toml` (`[pipeline]`) |

Desde a Phase 1 (v0.5.0), `PipelineConfig.max_workers` é **efectivamente dead code**. O controlo real de paralelismo do pipeline de ingest é `PerformanceConfig.parser_workers`. O campo `max_workers` é referido apenas pelo `auto_tune()` mas já não influencia o pipeline de repos. Deveria ser removido ou consolidado com `parser_workers` para evitar confusão.

**Atualização (Phase 5):** A secção `[pipeline]` em `rag.toml` já não é dead code — agora contém os campos `engine` ("local" ou "dask") e `dask_scheduler` (URL do scheduler remoto), usados pelo `create_parser_pool()` em `dask_engine.py`. Apenas `max_workers` continua sem efeito real.

---

## 4. Possíveis bugs e inconsistências

### 4.1 ~~Race condition na inicialização de singletons~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                                         |
| ---------------------- | ------------------------------------------------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Resolvido                                                           |
| **Impacto**            | Baixo — improvável em single-worker, mas possível com múltiplos workers uvicorn |
| **Complexidade**       | Baixa                                                                           |
| **Ficheiros afetados** | `obsidian_rag/retrieval/rag.py`                                                 |

**Resolução (2026-05-10):** Adicionado `threading.Lock()` com padrão double-checked locking em `_get_store()` (anteriormente `_get_collection()` e `_get_code_collection()`). Reset thread-safe para cleanup em testes.

### 4.2 ~~Keyword search sem normalização Unicode~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                              |
| ---------------------- | -------------------------------------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Resolvido                                                |
| **Impacto**            | Baixo — queries com acentos podiam falhar na correspondência keyword |
| **Complexidade**       | Baixa                                                                |
| **Ficheiros afetados** | `obsidian_rag/retrieval/rag.py` (`_extract_keywords()`)              |

**Resolução (2026-05-10):** `_extract_keywords()` aplica `unicodedata.normalize("NFC", text)` antes do processamento. Garante consistência entre caracteres compostos e decompostos.

### 4.3 ~~Stop words exclusivamente em português~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                              |
| ---------------------- | -------------------------------------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Resolvido                                                |
| **Impacto**            | Baixo — keyword search em inglês era menos eficaz                    |
| **Complexidade**       | Baixa                                                                |
| **Ficheiros afetados** | `obsidian_rag/retrieval/rag.py` (`_PT_STOP_WORDS`, `_EN_STOP_WORDS`) |

**Resolução (2026-05-10):** Adicionado `_EN_STOP_WORDS` frozenset (~70 stop words em inglês). Unificado em `_STOP_WORDS = _PT_STOP_WORDS | _EN_STOP_WORDS`, usado em `_extract_keywords()`.

### 4.4 ~~Batch loop no chroma.py saltava chunks~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                                                                               |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------- |
| **Prioridade**         | ~~Alta~~ — Resolvido                                                                                                  |
| **Impacto**            | Alto — chunks silenciosamente não eram embeddidos nem armazenados quando o batch era reduzido sob pressão de recursos |
| **Complexidade**       | Baixa                                                                                                                 |
| **Ficheiros afetados** | `obsidian_rag/store/chroma.py` (posteriormente eliminado na Phase 3.1)                                                |

**Resolução (2026-05-10):** O loop `for i in range(0, total, batch_size)` usava step fixo. Quando `batch_size` era reduzido dinamicamente pelo throttle (ex: de 50 para 25), o loop continuava a avançar com o step original (50), saltando chunks que nunca eram processados. Substituído por `while i < total` com `i += len(batch)` — o índice avança agora pelo tamanho real do batch processado, garantindo que nenhum chunk é saltado. Adicionado `import logging` e `log = logging.getLogger(__name__)` com chamadas `log.warning()`/`log.info()` estruturadas para eventos de throttle.

### 4.5 ~~KeyboardInterrupt no sync deixava estado inconsistente~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                                                     |
| ---------------------- | ------------------------------------------------------------------------------------------- |
| **Prioridade**         | ~~Média~~ — Resolvido                                                                       |
| **Impacto**            | Médio — Ctrl+C durante sync podia deixar subprocessos graphify e ChromaDB em estado parcial |
| **Complexidade**       | Baixa                                                                                       |
| **Ficheiros afetados** | `obsidian_rag/pipeline/sync.py`                                                             |

**Resolução (2026-05-10):** O corpo de `main()` foi extraído para `_main_inner()`. `main()` envolve `_main_inner()` num `try/except KeyboardInterrupt` que imprime mensagem clara ("⚠ Interrompido pelo utilizador (Ctrl+C). Sync parcial pode ter sido gravado.") e sai com código 130 (convenção UNIX para SIGINT).

---

## 5. Segurança

### 5.1 ~~API sem autenticação~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                         |
| ---------------------- | --------------------------------------------------------------- |
| **Prioridade**         | ~~Alta~~ — Resolvido                                            |
| **Impacto**            | Alto — qualquer dispositivo na rede podia aceder à API          |
| **Complexidade**       | Média                                                           |
| **Ficheiros afetados** | `obsidian_rag/api/app.py`, `obsidian_rag/config.py`, `rag.toml` |

**Resolução (2026-05-10):**

- **Bind default alterado** de `0.0.0.0` para `127.0.0.1` — a API já não é acessível na rede local por defeito.
- **Autenticação via API key** implementada como middleware HTTP:
  - Campo `api_key` adicionado a `[api]` em `rag.toml` e `ApiConfig` em `config.py`
  - Header `Authorization: Bearer <key>` obrigatório quando `api_key` está configurado
  - Endpoints isentos: `/health`, `/docs`, `/openapi.json`, `/redoc`
  - Comparação timing-safe com `secrets.compare_digest()`
  - Retrocompatível: quando `api_key` está vazio (defeito), a auth é desativada
  - Override via variável de ambiente: `RAG_API_API_KEY`
  - Retorna `401 JSONResponse` em caso de falha de autenticação

### 5.2 ~~Sem rate limiting~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                            |
| ---------------------- | -------------------------------------------------- |
| **Prioridade**         | ~~Média~~ — Resolvido                              |
| **Impacto**            | Médio — susceptível a DoS acidental ou intencional |
| **Complexidade**       | Baixa                                              |
| **Ficheiros afetados** | `obsidian_rag/api/app.py`                          |

**Resolução (2026-05-10):** Adicionado `slowapi>=0.1.9` como dependência. Rate limiting configurável via `[api] rate_limit = 60` (global) e `chat_rate_limit = 20` (endpoint `/chat`) em `rag.toml`. Exception handler para HTTP 429. Desativável com `rate_limit = 0`.

### 5.3 ~~Sem validação de comprimento de input~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                    |
| ---------------------- | ---------------------------------------------------------- |
| **Prioridade**         | ~~Média~~ — Resolvido                                      |
| **Impacto**            | Médio — queries muito longas podem causar OOM no embedding |
| **Complexidade**       | Baixa                                                      |
| **Ficheiros afetados** | `obsidian_rag/api/app.py`, `obsidian_rag/api/schemas.py`   |

**Resolução (2026-05-10):** Adicionadas validações `min_length`/`max_length` a todos os campos string dos modelos Pydantic: `QueryRequest.query` (1–10000), `ChatMessage.role` (max 20), `ChatMessage.content` (max 50000), `ChatRequest.messages` (max 200 msgs), `ChatRequest.model` (max 100). Pydantic retorna HTTP 422 automaticamente.

### 5.4 ~~Subprocess sem sanitização de paths~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                         |
| ---------------------- | --------------------------------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Resolvido                                           |
| **Impacto**            | Baixo — os paths vêm de `rag.toml`, controlado pelo utilizador  |
| **Complexidade**       | Baixa                                                           |
| **Ficheiros afetados** | `obsidian_rag/graph/builder.py`, `obsidian_rag/cli/init_cmd.py` |

**Resolução (v0.4.0 + v0.4.1):** `rag init` agora valida paths contra locações perigosas com lógica cross-platform: raízes de disco Windows (`C:\`), dirs de sistema Windows (`Program Files`, `ProgramData`), dirs macOS (`/System`, `/Library`, `~/Library`), dirs Linux (`/bin`, `/usr`, etc.) com resolução de symlinks via `os.path.realpath()`. Paths iCloud (macOS) e OneDrive (Windows) são detectados como candidatos válidos para vaults. Os paths em `builder.py` continuam sem validação runtime (risco baixo pois vêm de `rag.toml`).

### 5.4b ~~Imagem Docker com vulnerabilidades (falha Trivy)~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                                                       |
| ---------------------- | --------------------------------------------------------------------------------------------- |
| **Prioridade**         | ~~Alta~~ — Resolvido                                                                          |
| **Impacto**            | Alto — bloqueava os workflows `release-gate.yml` e `security-scheduled.yml` no GitHub Actions |
| **Complexidade**       | Baixa                                                                                         |
| **Ficheiros afetados** | `Dockerfile`                                                                                  |

**Causa raiz (2026-05-11):** Duas categorias de vulnerabilidades na imagem Docker:

1. **Pacotes OS desatualizados:** A imagem base `python:3.11-slim` (Debian) contém pacotes com vulnerabilidades HIGH/CRITICAL.
2. **Build tools Python no runtime:** Após copiar `site-packages` do builder stage, a imagem final continha `setuptools` e `wheel` — ferramentas de build desnecessárias em runtime que traziam vulnerabilidades vendored:
   - **CVE-2026-23949** (HIGH): `jaraco.context 5.3.0` — path traversal, vendored dentro do `setuptools`
   - **CVE-2026-24049** (HIGH): `wheel 0.45.1` — privilege escalation, presente como pacote standalone e vendored dentro do `setuptools`

**Resolução (2026-05-11):**

- **OS-level:** Adicionado `apt-get update && apt-get upgrade -y --no-install-recommends && rm -rf /var/lib/apt/lists/*` em **ambos os stages** do Dockerfile (builder e runtime). A limpeza de `/var/lib/apt/lists/*` mantém a imagem final pequena.
- **Python-level:** Após copiar `site-packages` do builder, o runtime stage faz `pip install --no-cache-dir --upgrade setuptools wheel` (atualiza para versões sem CVEs) seguido de `pip uninstall -y pip setuptools wheel` (remove completamente as ferramentas de build do runtime). Isto elimina tanto as versões vulneráveis standalone como as vendored, reduzindo a superfície de ataque da imagem final.

### 5.5 ChromaDB telemetria desativada mas sem validação — ⏸️ DEFERRED

| Campo                  | Detalhe                                               |
| ---------------------- | ----------------------------------------------------- |
| **Prioridade**         | Baixa                                                 |
| **Impacto**            | Baixo — `anonymized_telemetry=False` está configurado |
| **Complexidade**       | Baixa                                                 |
| **Ficheiros afetados** | `obsidian_rag/store/chroma_store.py`                  |

A telemetria do ChromaDB é desativada explicitamente (`anonymized_telemetry=False`), o que é correto. Mantém-se como nota de verificação.

**Decisão (2026-05-10):** Deferred — já está correto (`anonymized_telemetry=False`), sem ação necessária.

---

## 6. Privacidade e dados locais

### 6.1 Dados nunca saem da máquina (positivo)

O projeto é 100% local: Ollama local, ChromaDB local, sem APIs externas. Este é o ponto forte da arquitetura.

### 6.2 ~~Backup dos dados ChromaDB~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                 |
| ---------------------- | ------------------------------------------------------- |
| **Prioridade**         | ~~Média~~ — Resolvido                                   |
| **Impacto**            | Médio — perda de `data/chroma/` requer re-sync completo |
| **Complexidade**       | Baixa                                                   |
| **Ficheiros afetados** | `data/chroma/`, `obsidian_rag/pipeline/backup.py`       |

**Resolução (2026-05-10):** Novo módulo `obsidian_rag/pipeline/backup.py` com função `backup_store()` (renomeada de `backup_chroma()` na Phase 3.1). Cria cópias timestamped do diretório do vector store via `shutil.copytree` com rotação automática (mantém últimas 3 cópias). Ficheiros nomeados `store_backup_*` (era `chroma_backup_*`). Novo entry point CLI `rag backup`.

### 6.3 ~~Ficheiros source/ contêm cópia do vault~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                       |
| ---------------------- | --------------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Resolvido                         |
| **Impacto**            | Baixo — duplicação de dados sensíveis evitada |
| **Complexidade**       | Baixa                                         |
| **Ficheiros afetados** | `source/`, `.gitignore`                       |

**Resolução (2026-05-10 + v0.4.1):** Adicionado `source/` ao `.gitignore` para prevenir commits acidentais de dados pessoais do vault. Desde v0.4.1, o backend `direct` (default) lê o vault in-place sem criar cópia em `source/`, eliminando a duplicação por defeito. A pasta `source/` só é usada quando o backend é `python` ou `rsync`.

---

## 7. Performance

### 7.1 ~~Sync síncrono e sequencial~~ ✅ RESOLVIDO → REVERTIDO → BOUNDED PIPELINE (v0.5.0)

| Campo                  | Detalhe                                                                                                                                                                                                                                                                                                   |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Prioridade**         | ~~Média~~ — Resolvido                                                                                                                                                                                                                                                                                     |
| **Impacto**            | Alto — pipeline paralelo com backpressure resolve o problema de memória                                                                                                                                                                                                                                   |
| **Complexidade**       | Alta                                                                                                                                                                                                                                                                                                      |
| **Ficheiros afetados** | `obsidian_rag/pipeline/sync.py`, `obsidian_rag/pipeline/ingest.py`, `obsidian_rag/pipeline/manifest.py`, `obsidian_rag/config.py`, `obsidian_rag/tuning.py`, `obsidian_rag/chunking/code.py`, `obsidian_rag/chunking/markdown.py`, `obsidian_rag/store/chroma.py` (posteriormente eliminado na Phase 3.1) |

**Resolução inicial (2026-05-10):** `sync_repos()` usava `ThreadPoolExecutor(max_workers=4)` para processar repos em paralelo. Cada repo era submetido individualmente com `should_throttle()` entre submissões.

**Reversão (2026-05-10):** A abordagem paralela foi **arquiteturalmente defeituosa**: o ThreadPoolExecutor chunkava todos os 5 repos em paralelo, acumulava todos os chunks numa única lista `all_repo_chunks` em memória, e enviava-os todos de uma vez ao Ollama para embedding. Os throttle checks só corriam entre operações, mas o pico de RAM acontecia DURANTE o chunking paralelo + embedding em bloco — passando de 22% a 90%+ em ~40 segundos, causando freeze completo da máquina. Revertido para processamento sequencial.

**Solução final — Bounded Ingest Pipeline (Phase 1, v0.5.0):** Reescrita arquitetural completa do pipeline de repos. Em vez de processar todos os repos sequencialmente (chunk→embed→store→gc) ou em paralelo descontrolado, implementado um **pipeline de 4 estágios com bounded queues e backpressure**:

1. **Scanner thread** — descobre ficheiros alterados via `iter_repo_files()`/`iter_note_files()` (generators), verifica `mtime/size/SHA256` contra SQLite manifest para skip incremental
2. **Parser pool** — `ProcessPoolExecutor(spawn, max_tasks_per_child=100)` parse ficheiros em chunks com isolamento de memória por processo. Workers limitados por `parser_workers` (default 3)
3. **Embedding batcher** — acumula micro-batches (≤24 count, ≤48k chars, ou ≥1s timeout), chama `embed_texts()`, envia para write queue. Verifica `should_throttle()` antes de cada batch
4. **Writer thread** — upserts via `VectorStore.upsert_batch()` com embeddings pré-calculados (Phase 3.1: sem import direto de ChromaDB), atualiza manifest SQLite

Backpressure via `Queue(maxsize=...)` entre cada estágio: `files_queue(256)` → `chunks_queue(128)` → `write_queue(4)`. Quando o embedder é lento, os parsers bloqueiam em `chunks_queue.put()`. Quando o writer é lento, o embedder bloqueia em `write_queue.put()`. Isto previne crescimento ilimitado de memória.

SQLite manifest (`IngestManifest`) com WAL mode e `threading.Lock` permite crash recovery — syncs interrompidos retomam do último checkpoint.

### 7.2 ~~Embedding batch size fixo~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                                |
| ---------------------- | ---------------------------------------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Resolvido                                                  |
| **Impacto**            | Baixo — batch size de 50 pode não ser ótimo para todos os casos        |
| **Complexidade**       | Baixa                                                                  |
| **Ficheiros afetados** | `obsidian_rag/store/chroma.py` (posteriormente eliminado na Phase 3.1) |

**Resolução (2026-05-10):** O batch size de embeddings é agora configurável via `[performance] embedding_batch_size` em `rag.toml`. O `BATCH_SIZE=50` hardcoded em `chroma.py` foi removido — agora usa `settings.performance.embedding_batch_size`. Quando `auto_tune=true` (default), o valor é ajustado automaticamente com base na RAM disponível: 25 (<8GB), 50 (8-16GB), 100 (>16GB). Adicionado `should_throttle()` entre cada batch de embeddings: aborta se disco cheio, pausa se RAM alta, reduz batch size se CPU alta. Novo `PerformanceConfig` em `config.py`, com auto-tuning em `tuning.py`.

### 7.3 ~~Router LLM adiciona latência~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                              |
| ---------------------- | -------------------------------------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Resolvido                                                |
| **Impacto**            | Baixo — gemma3:4b é rápido (~77 tok/s) mas adiciona 0.5-2s por query |
| **Complexidade**       | Baixa                                                                |
| **Ficheiros afetados** | `obsidian_rag/retrieval/router.py`                                   |

**Resolução (2026-05-10):** `_llm_route()` agora usa `settings.performance.query_timeout_seconds` em vez de `timeout=15.0` hardcoded. O timeout é configurável via `[performance] query_timeout_seconds` em `rag.toml`. Latência mitigada pelo timeout configurável e heuristic fallback.

### 7.4 Graphify timeout + subutilização GPU ✅ RESOLVIDO (v0.5.1)

| Campo                  | Detalhe                                                                                                                         |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **Prioridade**         | ~~Média~~ — Resolvido                                                                                                           |
| **Impacto**            | Alto — `rag sync --all` falhava com timeout para repos; GPU NVIDIA subutilizada                                                 |
| **Complexidade**       | Média                                                                                                                           |
| **Ficheiros afetados** | `rag.toml`, `obsidian_rag/config.py`, `obsidian_rag/graph/enrich.py`, `obsidian_rag/graph/builder.py`, `obsidian_rag/tuning.py` |

**Problema:** `graphify extract` para `Git_Concepts` excedia `graph_timeout=600s` porque o modelo configurado era `deepseek-r1:8b` (reasoning model que gera tokens `<think>...</think>` extras, 3-5x mais lento por chamada LLM). Adicionalmente, o sistema não aproveitava a VRAM real da GPU para dimensionar batches e paralelismo.

**Resolução (2026-05-11):**

1. **Modelo graphify trocado** para `qwen2.5-coder:7b` — code-optimized, sem overhead de reasoning, ~43 tok/s
2. **Timeout enrich.py configurável** — `enrich_timeout: int = 180` em `PerformanceConfig`, substituindo `timeout=120` hardcoded em `_call_ollama()`
3. **graph_timeout bumped** para 900s (margem de segurança)
4. **Graphify paralelo** — `build_graphs()` refatorado para `ThreadPoolExecutor(max_workers=graph_parallel_jobs)` com guarda VRAM (free ≥ 1.5GB via pynvml). Thread-safe porque cada worker chama `subprocess.run()`. Se `graph_parallel_jobs ≤ 1`, mantém sequencial
5. **Auto-tune GPU-aware** — `detect_resources()` agora query VRAM real via `_read_vram()` (pynvml). `auto_tune()`: quando VRAM ≥ 6GB → `embedding_batch_size=50`, `embedding_batch_max_chars=60000`, `graph_parallel_jobs=2`
6. **Sumarização paralela** — `summarize_communities()` usa `ThreadPoolExecutor(max_workers=min(3, n))` para chamadas LLM I/O-bound em paralelo
7. **Embedding batch boost** — defaults bumped para `batch_size=50`, `max_chars=60000`

---

## 8. Escalabilidade

### 8.1 Single-process, single-user

| Campo                  | Detalhe                           |
| ---------------------- | --------------------------------- |
| **Prioridade**         | Baixa                             |
| **Impacto**            | Baixo — adequado para uso pessoal |
| **Complexidade**       | Alta                              |
| **Ficheiros afetados** | `obsidian_rag/api/app.py`         |

A arquitetura é single-process (uvicorn sem workers configurados). O httpx pool tem limit de 10 conexões. Para uso pessoal é adequado; para multi-utilizador seria necessário redesenhar.

### 8.2 ~~ChromaDB como único vector store~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                                                                  |
| ---------------------- | -------------------------------------------------------------------------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Resolvido                                                                                    |
| **Impacto**            | Baixo — ChromaDB escala bem até ~1M chunks                                                               |
| **Complexidade**       | Alta                                                                                                     |
| **Ficheiros afetados** | `obsidian_rag/store/base.py`, `obsidian_rag/store/chroma_store.py`, `obsidian_rag/store/qdrant_store.py` |

**Resolução (2026-05-10 — Phase 3):** Implementado `VectorStore` Protocol com `create_store()` factory. Qdrant disponível como backend alternativo (embedded ou server mode, `qdrant-client>=1.9` como dep opcional). Migração entre backends via `rag migrate`. Para vaults muito grandes, Qdrant em modo server é recomendado.

### 8.3 ~~`sync_notes()` não usa bounded pipeline~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                                                                                                                                  |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Prioridade**         | ~~Alta~~ — Resolvido                                                                                                                                                     |
| **Impacto**            | Crítico — com 2000+ notas, `chunk_all_notes()` acumulava todos os chunks em memória antes de embedar, replicando o padrão que causou o freeze dos repos (ver postmortem) |
| **Complexidade**       | Média                                                                                                                                                                    |
| **Ficheiros afetados** | `obsidian_rag/pipeline/sync.py`, `obsidian_rag/chunking/markdown.py`                                                                                                     |

**Resolução (2026-05-11):** `sync_notes()` reescrito para usar `IngestPipeline` com `collection_name="obsidian_vault"` e `IngestSource(source_type="vault")`. O scanner usa `iter_note_files()` (generator), o parser chama `chunk_note()`, e o pipeline aplica backpressure via bounded queues — mesmo padrão que `sync_repos()`. `_sync_chunks_to_store()` removido (dead code). `chunk_all_notes()` mantida com deprecation docstring para backward compat em testes. Notas usam agora o `IngestManifest` para skip incremental (§8.4 resolvido automaticamente). 366 testes passam.

### 8.4 ~~Notas Obsidian sem tracking incremental (manifest)~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                                                              |
| ---------------------- | ---------------------------------------------------------------------------------------------------- |
| **Prioridade**         | ~~Alta~~ — Resolvido                                                                                 |
| **Impacto**            | Alto — cada `rag sync -l` re-chunkava e re-embedava **todas** as notas mesmo que nada tivesse mudado |
| **Complexidade**       | Baixa                                                                                                |
| **Ficheiros afetados** | `obsidian_rag/pipeline/sync.py`, `obsidian_rag/pipeline/manifest.py`                                 |

**Resolução (2026-05-11):** Resolvido automaticamente pela migração de `sync_notes()` para o `IngestPipeline` (§8.3). Notas partilham o mesmo `manifest.db` que os repos — sem colisão porque `source.name` é diferente ("vault" vs nome do repo). Na primeira execução pós-migração, todas as notas são reprocessadas (manifest vazio para vault); em execuções subsequentes, apenas ficheiros alterados são reprocessados via `mtime/size/SHA256`.

### 8.5 Retrieval perde precisão a escala — falta hybrid search

| Campo                  | Detalhe                                                                                                                                                                                                           |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Prioridade**         | Média                                                                                                                                                                                                             |
| **Impacto**            | Médio — com >5000 chunks, pesquisa puramente vectorial perde precisão para termos técnicos exactos (nomes de funções, variáveis, erros). Qdrant suporta nativamente sparse vectors (BM25-like) para hybrid search |
| **Complexidade**       | Média — requer sparse embedding + alteração ao `VectorStore` protocol + query fusion                                                                                                                              |
| **Ficheiros afetados** | `obsidian_rag/store/base.py`, `obsidian_rag/store/qdrant_store.py`, `obsidian_rag/retrieval/rag.py`                                                                                                               |

**Estado:** Aberto — planeado para v1.1 (Fase 20, tarefa #182).

### 8.6 ~~Queries de código diluídas — falta filtering por metadata~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                                                                                                                                                            |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Prioridade**         | ~~Média~~ — Resolvido                                                                                                                                                                              |
| **Impacto**            | Médio — com 10+ repos, queries de código ficam diluídas. Qdrant suporta payload filtering no `query()` — filtro por `repo_name` permitiria pesquisa scoped sem coleções separadas                  |
| **Complexidade**       | Baixa — alteração ao `VectorStore.query()` para aceitar `filters: dict` opcional                                                                                                                   |
| **Ficheiros afetados** | `obsidian_rag/store/base.py`, `obsidian_rag/store/qdrant_store.py`, `obsidian_rag/store/chroma_store.py`, `obsidian_rag/retrieval/rag.py`, `obsidian_rag/api/app.py`, `obsidian_rag/cli/_query.py` |

**Resolução (2026-05-11):** `VectorStore.query()` Protocol aceita `filters: dict | None = None`. QdrantVectorStore converte para `models.Filter(must=[FieldCondition(...)])`. ChromaVectorStore converte para `where` dict. `/query/code` usa filtros query-time (eliminado filtro pós-retrieval). CLI `rag query --repo X` direciona para `/query/code`. 10 novos testes (2 filter + parametrizados Chroma/Qdrant).

### 8.7 Reranker sequencial — bottleneck de latência

| Campo                  | Detalhe                                                                                                                                                                                                      |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Prioridade**         | Baixa                                                                                                                                                                                                        |
| **Impacto**            | Baixo-Médio — reranker chama Ollama **uma vez por chunk candidato** sequencialmente. Com `top_k_candidates=30`, são 30 chamadas HTTP. Paralelizar com ThreadPoolExecutor (I/O-bound) reduziria latência 3-5× |
| **Complexidade**       | Baixa — mesmo padrão já aplicado em `enrich.py` `summarize_communities()`                                                                                                                                    |
| **Ficheiros afetados** | `obsidian_rag/retrieval/reranker.py`                                                                                                                                                                         |

**Estado:** Aberto — planeado para v1.1 (Fase 20, tarefa #185).

### 8.8 Graphify sem incrementalidade real

| Campo                  | Detalhe                                                                                                                                                                                             |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Prioridade**         | Baixa                                                                                                                                                                                               |
| **Impacto**            | Baixo-Médio — `build_graph()` faz rebuild por repo inteiro (ou skip total). Com repos grandes (100+ ficheiros), tracking de quais ficheiros mudaram e rebuild parcial reduziria o tempo de graphify |
| **Complexidade**       | Média — depende do suporte da lib graphifyy para rebuild parcial                                                                                                                                    |
| **Ficheiros afetados** | `obsidian_rag/graph/builder.py`, `obsidian_rag/pipeline/manifest.py`                                                                                                                                |

**Estado:** Aberto — planeado para v1.1 (Fase 20, tarefa #186).

### 8.9 Qdrant embedded vs. server mode para bases grandes

| Campo                  | Detalhe                                                                                                                                                                                   |
| ---------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Prioridade**         | Baixa                                                                                                                                                                                     |
| **Impacto**            | Baixo — com >50k chunks, Qdrant embedded fica lento no startup e consome mais RAM. Migrar para server mode (já suportado via `qdrant_url`) dá indexação assíncrona e queries mais rápidas |
| **Complexidade**       | Baixa — infraestrutura já existe, falta documentação operacional                                                                                                                          |
| **Ficheiros afetados** | `docker-compose.yml`, documentação                                                                                                                                                        |

**Estado:** Aberto — planeado para v1.1 (Fase 20, tarefa #187).

### 8.10 Multi-vault Obsidian

| Campo                  | Detalhe                                                                                                                                                                |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Prioridade**         | Baixa                                                                                                                                                                  |
| **Impacto**            | Baixo — `vault_dir` é singular. Suportar `vault_dirs = [...]` (lista) com coleções separadas por vault permitiria pesquisa scoped (pessoal vs. trabalho vs. projectos) |
| **Complexidade**       | Média — alteração a `PathsConfig`, `sync_notes()`, `rag.toml`, e lógica de coleções                                                                                    |
| **Ficheiros afetados** | `obsidian_rag/config.py`, `obsidian_rag/pipeline/sync.py`, `rag.toml`, `obsidian_rag/retrieval/rag.py`                                                                 |

**Estado:** Aberto — planeado para v1.1 (Fase 20, tarefa #188).

---

## 9. Organização do código

### 9.1 Estrutura modular (positivo)

O código está bem organizado em módulos temáticos (`cli/`, `chunking/`, `embeddings/`, `retrieval/`, `graph/`, `store/`, `api/`, `pipeline/`, `prompts/`). A separação de responsabilidades é clara.

### 9.2 Config centralizada com lazy loading (positivo)

Toda a configuração está em `rag.toml` com env overrides, frozen dataclasses e path resolution. Desde v0.4.0, `settings` é um `_LazySettings` proxy que só carrega no primeiro acesso, permitindo que `rag init` e `rag doctor` funcionem sem `rag.toml`. Helper `config_exists()` adicionado.

### 9.3 CLI unificado (positivo — v0.4.0)

Desde v0.4.0, existe um único entry point `rag` com subcomandos em vez de 5 comandos separados. O dispatcher em `cli/main.py` usa imports lazy para não carregar `settings` em comandos que não precisam (ex: `rag init`, `rag doctor`).

### 9.4 ~~Falta de `__all__` exports~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                       |
| ---------------------- | ------------------------------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Resolvido                                         |
| **Impacto**            | Baixo — API pública dos módulos agora definida explicitamente |
| **Complexidade**       | Baixa                                                         |
| **Ficheiros afetados** | Todos os `__init__.py`                                        |

**Resolução (2026-05-10):** Adicionado `__all__` a todos os ficheiros `__init__.py` do projeto, definindo explicitamente a API pública de cada módulo.

---

## 10. Melhorias recomendadas

### 10.1 ~~Testes automatizados~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                |
| ---------------------- | -------------------------------------- |
| **Prioridade**         | ~~Alta~~ — Resolvido                   |
| **Impacto**            | Alto — permite refatorar com confiança |
| **Complexidade**       | Média                                  |
| **Ficheiros afetados** | `tests/`, `pyproject.toml`             |

**Resolução (2026-05-10):** 329 testes (18 skipped) implementados com pytest (83 unit iniciais + funcionalidades médias + 16 integration + CLI dispatch + init + security + 10 performance + 16 adaptive top_k + 27 low-priority + 42 vault_sync/cross-platform + 25 manifest + 10 ingest pipeline + 21 governor + 34 vector store protocol + 22 tree-sitter chunking + 6 dask engine). Cobertura de chunking (markdown + code + tree-sitter multi-linguagem), router heuristic, budget allocation, API auth, backup, sync paralelo, logging JSON, tokenizer regex, CLI dispatcher, path validation (cross-platform), bind validation, `PerformanceConfig`, `auto_tune`, `should_throttle`, `_estimate_complexity`, adaptive top_k scaling, thread-safe singletons, Unicode normalization, bilingual stop words, `__all__` exports, reranker cache, embedding timeout, vault_sync backends (direct/python/rsync/auto), exclude patterns, incremental copy, delete_missing, `IngestManifest` (SQLite CRUD, crash recovery), `IngestPipeline` (bounded stages, backpressure), `ResourceGovernor` (thresholds, lifecycle, wait_until_safe, metrics JSONL, tuning backward compat), `VectorStore` protocol (upsert, query, delete, count, collection isolation, factory, Chroma/Qdrant parametrizado), Dask engine factory (`create_parser_pool`, `DaskParserPool`) e integration tests com TestClient + ChromaVectorStore in-memory. Fixtures partilhadas em `conftest.py`. Nenhum teste depende de serviços externos.

### 10.2 ~~Autenticação da API~~ ✅ RESOLVIDO

| Campo | Detalhe |\n| ---------------------- | ----------------------------------------------------------------------- |\n| **Prioridade** | ~~Alta~~ — Resolvido |\n| **Impacto** | Alto — protege dados pessoais |\n| **Complexidade** | Baixa |\n| **Ficheiros afetados** | `obsidian_rag/api/app.py`, `obsidian_rag/config.py`, `rag.toml` |

**Resolução (2026-05-10):** Implementada autenticação via API key (`Bearer`) com middleware HTTP + bind default alterado para `127.0.0.1`. Ver secção 5.1 para detalhes completos.

### 10.3 ~~Tokenizer real para budget~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                   |
| ---------------------- | ----------------------------------------- |
| **Prioridade**         | ~~Média~~ — Resolvido                     |
| **Impacto**            | Médio — alocação de contexto mais precisa |
| **Complexidade**       | Média                                     |
| **Ficheiros afetados** | `obsidian_rag/retrieval/budget.py`        |

**Resolução (2026-05-10):** `estimate_tokens()` substituído por tokenizer regex word-boundary com multiplicador 1.3×. Mais preciso que `chars ÷ 4` para textos multilíngues e código, sem dependências externas.

### 10.4 ~~Containerização (Docker)~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                         |
| ---------------------- | ----------------------------------------------- |
| **Prioridade**         | ~~Média~~ — Resolvido                           |
| **Impacto**            | Médio — facilita deployment e reprodutibilidade |
| **Complexidade**       | Baixa                                           |
| **Ficheiros afetados** | `Dockerfile`, `docker-compose.yml`              |

**Resolução (2026-05-10):** Criados `Dockerfile` (multi-stage, `python:3.11-slim`) e `docker-compose.yml`. Expõe porta 8000, monta volume `./data`, conecta ao Ollama do host via `extra_hosts: host.docker.internal:host-gateway`.

### 10.5 ~~Logging estruturado~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                       |
| ---------------------- | ------------------------------------------------------------- |
| **Prioridade**         | ~~Média~~ — Resolvido                                         |
| **Impacto**            | Médio — melhor observabilidade em produção                    |
| **Complexidade**       | Baixa                                                         |
| **Ficheiros afetados** | `obsidian_rag/retrieval/observe.py`, `obsidian_rag/config.py` |

**Resolução (2026-05-10):** Adicionada classe `_JsonFormatter` em `observe.py` que emite JSON lines. File handler usa sempre JSON. Consola usa JSON quando `log_format = "json"` na secção `[debug]` de `rag.toml`. Novo campo `log_format` no dataclass `DebugConfig`.

### 10.6 ~~Rate limiting na API~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                   |
| ---------------------- | ----------------------------------------- |
| **Prioridade**         | ~~Média~~ — Resolvido                     |
| **Impacto**            | Médio — protege contra overload acidental |
| **Complexidade**       | Baixa                                     |
| **Ficheiros afetados** | `obsidian_rag/api/app.py`                 |

**Resolução (2026-05-10):** Implementado com `slowapi`. Limites configuráveis: `rate_limit=60/min` (global), `chat_rate_limit=20/min` (endpoint `/chat`). Ver §5.2.

### 10.7 ~~Validação de input nos endpoints~~ ✅ RESOLVIDO

| Campo                  | Detalhe                         |
| ---------------------- | ------------------------------- |
| **Prioridade**         | ~~Média~~ — Resolvido           |
| **Impacto**            | Médio — previne crashes e abuso |
| **Complexidade**       | Baixa                           |
| **Ficheiros afetados** | `obsidian_rag/api/schemas.py`   |

**Resolução (2026-05-10):** `max_length` e `min_length` adicionados a todos os campos string dos modelos Pydantic. Ver §5.3.

### 10.8 ~~Chunking multi-linguagem~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                                                  |
| ---------------------- | ---------------------------------------------------------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Resolvido                                                                    |
| **Impacto**            | Médio — suporta repos não-Python                                                         |
| **Complexidade**       | Alta                                                                                     |
| **Ficheiros afetados** | `obsidian_rag/chunking/code.py`, `obsidian_rag/chunking/treesitter.py`, `pyproject.toml` |

**Resolução (2026-05-10 — Phase 4):** Implementado chunking semântico multi-linguagem via tree-sitter. Novo módulo `treesitter.py` com suporte para 10 linguagens: JavaScript (.js/.jsx/.mjs), TypeScript (.ts/.tsx), Java (.java), Go (.go), Rust (.rs), C (.c/.h), C++ (.cpp/.cxx/.cc/.hpp/.hxx), C# (.cs), Ruby (.rb). Language registry mapeia extensões → grammar modules tree-sitter. Extrai definições (funções, classes, métodos, structs, interfaces, enums, traits, impls, namespaces) como chunks individuais. Métodos de classes/structs/impls extraídos separadamente. Código module-level como chunk separado. Lazy loading via `importlib.import_module()`. Fallback automático para text chunking se tree-sitter não instalado. `code.py` dispatch: `.py` → AST, extensões tree-sitter → `chunk_treesitter()`, resto → markdown/text. `iter_repo_files()` atualizado para incluir extensões tree-sitter. Dependência opcional: `pip install obsidian-rag[treesitter]` (10 pacotes: `tree-sitter>=0.23` + 9 grammar packages). 22 testes em `test_chunking_treesitter.py` (skipped se tree-sitter não instalado).

### 10.9 ~~Reranker habilitado por defeito (com cache)~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                          |
| ---------------------- | ------------------------------------------------ |
| **Prioridade**         | ~~Baixa~~ — Resolvido                            |
| **Impacto**            | Médio — melhora qualidade das respostas          |
| **Complexidade**       | Baixa                                            |
| **Ficheiros afetados** | `obsidian_rag/retrieval/reranker.py`, `rag.toml` |

**Resolução (2026-05-10):** Reranker habilitado por defeito (`enabled=true` em `[reranker]`). Adicionado `@lru_cache` em `_score_chunk()` para evitar re-scoring de chunks idênticos. Impacto na latência mitigado pelo cache.

### 10.10 ~~Sync paralelo~~ ✅ IMPLEMENTADO → ⚠️ REVERTIDO → ✅ BOUNDED PIPELINE (Phase 1)

| Campo                  | Detalhe                                                                                                                                                                                                                                                                                                   |
| ---------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Resolvido (Phase 1)                                                                                                                                                                                                                                                                           |
| **Impacto**            | Alto — pipeline paralelo com backpressure e crash recovery                                                                                                                                                                                                                                                |
| **Complexidade**       | Alta                                                                                                                                                                                                                                                                                                      |
| **Ficheiros afetados** | `obsidian_rag/pipeline/sync.py`, `obsidian_rag/pipeline/ingest.py`, `obsidian_rag/pipeline/manifest.py`, `obsidian_rag/config.py`, `obsidian_rag/tuning.py`, `obsidian_rag/chunking/code.py`, `obsidian_rag/chunking/markdown.py`, `obsidian_rag/store/chroma.py` (posteriormente eliminado na Phase 3.1) |

**Implementação inicial (2026-05-10):** `sync_repos()` usava `ThreadPoolExecutor(max_workers=4)` para processar repos em paralelo.

**Reversão (2026-05-10):** O ThreadPoolExecutor chunkava todos os repos em paralelo e acumulava todos os chunks em memória antes do embedding, causando pico de RAM de 22% a 90%+ em ~40s. Revertido para processamento sequencial com `gc.collect()` entre repos.

**Solução final — Bounded Ingest Pipeline (Phase 1, v0.5.0):** Reescrita arquitetural com 4 estágios (scanner → parser pool → embedding batcher → writer) conectados por bounded queues com backpressure. Ficheiros são a unidade de processamento (não repos). SQLite manifest para crash recovery. `ProcessPoolExecutor` com `spawn` context e `max_tasks_per_child=100` para isolamento de memória. Ver §7.1 para detalhes.

### 10.11 ~~Stop words bilíngues~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                |
| ---------------------- | -------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Resolvido                  |
| **Impacto**            | Baixo — keyword search melhorado em EN |
| **Complexidade**       | Baixa                                  |
| **Ficheiros afetados** | `obsidian_rag/retrieval/rag.py`        |

**Resolução (2026-05-10):** Adicionado `_EN_STOP_WORDS` frozenset (~70 stop words em inglês). Unificado em `_STOP_WORDS = _PT_STOP_WORDS | _EN_STOP_WORDS`, usado em `_extract_keywords()`. Ver §4.3.

### 10.12 ~~Health check do Ollama no lifespan~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                        |
| ---------------------- | -------------------------------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Resolvido                                          |
| **Impacto**            | Baixo — diagnóstico mais claro quando Ollama está indisponível |
| **Complexidade**       | Baixa                                                          |
| **Ficheiros afetados** | `obsidian_rag/cli/up_cmd.py`, `obsidian_rag/cli/doctor_cmd.py` |

**Resolução (v0.4.0):** O `rag up` faz pre-flight checks (Ollama online, modelos disponíveis, ChromaDB acessível) antes de iniciar a API. O `rag doctor` faz diagnóstico completo com output ✓/✗ incluindo conectividade Ollama e modelos instalados.

---

## 11. Roadmap sugerido

### Fase 1 — Fundações (Alta prioridade)

| #   | Tarefa                                               | Complexidade | Estado       |
| --- | ---------------------------------------------------- | ------------ | ------------ |
| 1   | ~~Configurar pytest + primeiras fixtures~~           | Média        | ✅ Concluído |
| 2   | ~~Unit tests para chunking (markdown + code)~~       | Média        | ✅ Concluído |
| 3   | ~~Unit tests para router heuristic~~                 | Baixa        | ✅ Concluído |
| 4   | ~~Mudar bind default de `0.0.0.0` para `127.0.0.1`~~ | Baixa        | ✅ Concluído |
| 5   | ~~Validação / auth da API (API key + bind local)~~   | Baixa        | ✅ Concluído |

> **Fase 1 concluída em 2026-05-10.** Todas as tarefas de alta prioridade foram implementadas.

### Fase 2 — Robustez (Média prioridade)

| #   | Tarefa                                                    | Complexidade | Estado                        |
| --- | --------------------------------------------------------- | ------------ | ----------------------------- |
| 6   | ~~Integration tests com TestClient + ChromaDB in-memory~~ | Média        | ✅ Concluído                  |
| 7   | ~~Configurar ruff/mypy no pyproject.toml~~                | Baixa        | ✅ Concluído                  |
| 8   | ~~CI/CD básico (GitHub Actions: lint + test)~~            | Média        | ✅ Concluído                  |
| 9   | ~~Rate limiting com slowapi~~                             | Baixa        | ✅ Concluído                  |
| 10  | ~~Tokenizer real para budget~~                            | Média        | ✅ Concluído                  |
| C3  | ~~Sync paralelo de repos (ThreadPoolExecutor)~~           | Média        | ✅ Bounded Pipeline (Fase 13) |
| D1  | ~~Logging estruturado JSON~~                              | Baixa        | ✅ Concluído                  |
| D2  | ~~Backup ChromaDB com rotação~~                           | Baixa        | ✅ Concluído                  |
| D3  | ~~Containerização Docker~~                                | Baixa        | ✅ Concluído                  |

> **Fase 2 concluída em 2026-05-10.** Todas as tarefas de média prioridade foram implementadas. 226 testes passam sem deps externas.

### Fase 3 — Evolução (Baixa prioridade)

| #   | Tarefa                                       | Complexidade | Estado                                          |
| --- | -------------------------------------------- | ------------ | ----------------------------------------------- |
| 11  | ~~Dockerfile + docker-compose~~              | Baixa        | ✅ Concluído                                    |
| 12  | ~~Logging estruturado (JSON)~~               | Baixa        | ✅ Concluído                                    |
| 13  | ~~Habilitar reranker com cache~~             | Baixa        | ✅ Concluído                                    |
| 14  | ~~Sync paralelo para múltiplos repos~~       | Média        | ✅ Bounded Pipeline (Fase 13)                   |
| 15  | ~~Chunking multi-linguagem (tree-sitter)~~   | Alta         | ✅ Concluído (Phase 4)                          |
| 16  | ~~Versão centralizada (importlib.metadata)~~ | Baixa        | ✅ Concluído                                    |
| 17  | ~~Health check do Ollama no startup~~        | Baixa        | ✅ Concluído (v0.4.0 — `rag up` + `rag doctor`) |
| 18  | ~~Stop words bilíngues (PT + EN)~~           | Baixa        | ✅ Concluído                                    |

### Fase 4 — DX e Onboarding (v0.4.0) ✅

| #   | Tarefa                                                                      | Complexidade | Estado       |
| --- | --------------------------------------------------------------------------- | ------------ | ------------ |
| 19  | ~~CLI unificado (`rag` com subcommands)~~                                   | Média        | ✅ Concluído |
| 20  | ~~`rag init` — wizard interactivo com path validation~~                     | Média        | ✅ Concluído |
| 21  | ~~`rag up` — pre-flight checks + start~~                                    | Baixa        | ✅ Concluído |
| 22  | ~~`rag doctor` — diagnóstico do sistema~~                                   | Baixa        | ✅ Concluído |
| 23  | ~~`rag graph build/status` — gestao de grafos~~                             | Baixa        | ✅ Concluído |
| 24  | ~~Config lazy loading (`_LazySettings`)~~                                   | Baixa        | ✅ Concluído |
| 25  | ~~Graphify como dep obrigatória (opt-in na execução)~~                      | Baixa        | ✅ Concluído |
| 26  | ~~`install.sh` + `Makefile`~~                                               | Baixa        | ✅ Concluído |
| 27  | ~~Segurança: bind validation, path validation, \_EXCLUDED_DIRS~~            | Média        | ✅ Concluído |
| 28  | ~~Testes CLI + init + security + performance + adaptive top_k (226 total)~~ | Média        | ✅ Concluído |

> **Fase 4 concluída em 2026-05-10.** Major DX refactoring (v0.4.0): CLI unificado, wizard de setup, diagnóstico, pre-flight checks, config lazy loading, melhorias de segurança.

### Fase 5 — Performance adaptativa (v0.4.1) ✅

| #   | Tarefa                                                           | Complexidade | Estado       |
| --- | ---------------------------------------------------------------- | ------------ | ------------ |
| 29  | ~~Auto-tuning de recursos (`detect_resources`, `auto_tune`)~~    | Média        | ✅ Concluído |
| 30  | ~~`PerformanceConfig` + secção `[performance]` em `rag.toml`~~   | Baixa        | ✅ Concluído |
| 31  | ~~Adaptive top_k (`_estimate_complexity` + scaling automático)~~ | Média        | ✅ Concluído |
| 32  | ~~Proteção de recursos no sync (`should_throttle`)~~             | Média        | ✅ Concluído |
| 33  | ~~Verificação de disco em `rag up` (<500MB recusa, <1GB avisa)~~ | Baixa        | ✅ Concluído |
| 34  | ~~`rag doctor`: secções Recursos e Performance~~                 | Baixa        | ✅ Concluído |
| 35  | ~~Dependência `psutil>=5.9`~~                                    | Baixa        | ✅ Concluído |
| 36  | ~~Embedding batch size configurável via `[performance]`~~        | Baixa        | ✅ Concluído |
| 37  | ~~26 novos testes (performance + adaptive top_k) — 226 total~~   | Média        | ✅ Concluído |

> **Fase 5 concluída em 2026-05-10.** Auto-tuning de recursos, adaptive top_k, proteção de recursos no sync, verificação de disco, nova dependência `psutil`.

### Fase 6 — Polimento e robustez (Baixa prioridade) ✅

| #   | Tarefa                                                              | Complexidade | Estado       |
| --- | ------------------------------------------------------------------- | ------------ | ------------ |
| 38  | ~~Versão centralizada (`importlib.metadata.version()`)~~            | Baixa        | ✅ Concluído |
| 39  | ~~Normalização Unicode em `_extract_keywords()`~~                   | Baixa        | ✅ Concluído |
| 40  | ~~Stop words bilíngues (PT + EN)~~                                  | Baixa        | ✅ Concluído |
| 41  | ~~Embedding timeout configurável (`PerformanceConfig`)~~            | Baixa        | ✅ Concluído |
| 42  | ~~`OLLAMA_API_KEY` documentado como placeholder litellm~~           | Baixa        | ✅ Concluído |
| 43  | ~~`source/` adicionado ao `.gitignore`~~                            | Baixa        | ✅ Concluído |
| 44  | ~~`__all__` exports em todos os `__init__.py`~~                     | Baixa        | ✅ Concluído |
| 45  | ~~Thread-safe singletons (`threading.Lock()`)~~                     | Baixa        | ✅ Concluído |
| 46  | ~~`clear_embed_cache()` chamado no início de `sync_notes()`~~       | Baixa        | ✅ Concluído |
| 47  | ~~Router timeout via `settings.performance.query_timeout_seconds`~~ | Baixa        | ✅ Concluído |
| 48  | ~~Graphify subprocess com `logging` em vez de `print()`~~           | Baixa        | ✅ Concluído |
| 49  | ~~Reranker habilitado por defeito + LRU cache em `_score_chunk()`~~ | Baixa        | ✅ Concluído |
| 50  | ~~27 novos testes (`test_low_priority.py`) — 226 total~~            | Média        | ✅ Concluído |

> **Fase 6 concluída em 2026-05-10.** Polimento de baixa prioridade: thread safety, normalização Unicode, stop words bilíngues, `__all__` exports, timeouts configuráveis, reranker com cache LRU, logging estruturado em subprocess. §10.8 (tree-sitter chunking) resolvido na Fase 17. §8.1 (escalabilidade single-user) deferred.

### Fase 7 — Cross-platform e sync refactoring (v0.4.1) ✅

| #   | Tarefa                                                                                         | Complexidade | Estado       |
| --- | ---------------------------------------------------------------------------------------------- | ------------ | ------------ |
| 51  | ~~`vault_sync.py` — 4 backends de sync (direct, python, rsync, auto)~~                         | Média        | ✅ Concluído |
| 52  | ~~Secção `[sync]` em `rag.toml`: backend, delete_missing, follow_symlinks, exclude~~           | Baixa        | ✅ Concluído |
| 53  | ~~Default backend `direct` — sem dependência de rsync, cross-platform~~                        | Baixa        | ✅ Concluído |
| 54  | ~~Detecção cross-platform de vault/repos em `rag init` (obsidian.json, iCloud, OneDrive)~~     | Média        | ✅ Concluído |
| 55  | ~~Path validation cross-platform (Windows drives, macOS /System, Linux /bin + symlinks)~~      | Média        | ✅ Concluído |
| 56  | ~~`install.ps1` — instalador nativo Windows (PowerShell)~~                                     | Baixa        | ✅ Concluído |
| 57  | ~~`rag schedule install/remove/status` — scheduler cross-platform (systemd/launchd/schtasks)~~ | Média        | ✅ Concluído |
| 58  | ~~Default exclude patterns (.obsidian, .trash, .git, .DS_Store, Thumbs.db, etc.)~~             | Baixa        | ✅ Concluído |
| 59  | ~~`rag doctor` — mostra sync backend info~~                                                    | Baixa        | ✅ Concluído |
| 60  | ~~42 novos testes (`test_vault_sync.py` + cross-platform security) — 226 total~~               | Média        | ✅ Concluído |

> **Fase 7 concluída em 2026-05-10.** Major cross-platform refactoring: sync vault com 4 backends configuráveis (default `direct` elimina dependência de rsync), detecção automática de vault Obsidian via ficheiro de configuração nativo, validação de paths cross-platform com resolução de symlinks, `install.ps1` para Windows, scheduler cross-platform via `rag schedule`, e 42 novos testes. O projeto suporta agora Linux, macOS e Windows nativamente.

### Fase 8 — CI/CD pipeline completa (v0.4.1) ✅

| #   | Tarefa                                                                                                   | Complexidade | Estado       |
| --- | -------------------------------------------------------------------------------------------------------- | ------------ | ------------ |
| 61  | ~~`ci.yml`: lint (ruff + mypy), test matrix (3 OS × 2 Python), CLI smoke, config tests, security audit~~ | Alta         | ✅ Concluído |
| 62  | ~~`docker.yml`: Docker build com Buildx cache, compose config, sanity check~~                            | Média        | ✅ Concluído |
| 63  | ~~`release.yml`: CI → build wheel/sdist → GitHub Release → Docker image~~                                | Média        | ✅ Concluído |
| 64  | ~~`pyproject.toml`: adicionar `pytest-cov>=5.0`, `types-requests>=2.31` a dev extras~~                   | Baixa        | ✅ Concluído |
| 65  | ~~`Makefile`: targets `lint`, `typecheck`, `test-cov`, `ci`, `docker-build`, `docker-check`~~            | Baixa        | ✅ Concluído |
| 66  | ~~README: secção CI/CD com matriz de plataformas e comandos locais~~                                     | Baixa        | ✅ Concluído |
| 67  | ~~Corrigir 3 erros ruff existentes (f-string, import sort, unused import)~~                              | Baixa        | ✅ Concluído |
| 68  | ~~Dockerfile: user não-root `rag` (UID 1000) com `chown` do `/app/data`~~                                | Baixa        | ✅ Concluído |
| 69  | ~~`ci.yml`: adicionar `workflow_call:` para reutilização em `release.yml`~~                              | Baixa        | ✅ Concluído |
| 70  | ~~`docker.yml`: health endpoint test real (`/health` sem Ollama, api_key=ci-test-key)~~                  | Média        | ✅ Concluído |
| 71  | ~~`config.py`: `_find_project_root()` com fallback CWD para funcionar em containers~~                    | Baixa        | ✅ Concluído |

> **Fase 8 concluída em 2026-05-10.** Pipeline CI/CD completa com GitHub Actions: testes em matrix 3 OS × 2 Python (sem Ollama/GPU/rsync), CLI smoke test cross-platform, security audit (secrets, .env, .gitignore, Docker), Docker build + compose config + health endpoint test, release workflow com GitHub Release automático. Dockerfile com user não-root (UID 1000). `_find_project_root()` com fallback CWD para containers. `ci.yml` com `workflow_call` para reutilização em `release.yml`. `make ci` para validação local completa. Cobertura: 61%. Posteriormente adicionados `release-gate.yml` (Trivy image scan + OWASP ZAP baseline) e `security-scheduled.yml` (scans semanais de source e container). Total: 5 workflows.

### Fase 9 — Security hardening (v0.4.1) ✅

| #   | Tarefa                                                                                                                      | Complexidade | Estado       |
| --- | --------------------------------------------------------------------------------------------------------------------------- | ------------ | ------------ |
| 72  | ~~`SECURITY.md`: política de segurança profissional com modelo local-first, reporting, scope~~                              | Média        | ✅ Concluído |
| 73  | ~~`codeql.yml`: análise de segurança Python (path traversal, subprocess, credentials)~~                                     | Média        | ✅ Concluído |
| 74  | ~~`dependabot.yml`: adicionar ecosystem `docker` para monitorizar `python:3.11-slim`~~                                      | Baixa        | ✅ Concluído |
| 75  | ~~`Dockerfile`: `HEALTHCHECK` com Python stdlib (sem instalar curl)~~                                                       | Baixa        | ✅ Concluído |
| 76  | ~~`docker-compose.yml`: bind `127.0.0.1`, api_key default `changeme`, comentários de segurança~~                            | Baixa        | ✅ Concluído |
| 76b | ~~`Dockerfile`: `apt-get upgrade` + remoção de setuptools/wheel/pip do runtime (fix Trivy CVE-2026-23949, CVE-2026-24049)~~ | Baixa        | ✅ Concluído |

> **Fase 9 concluída em 2026-05-10, atualizada em 2026-05-11.** Security hardening: `SECURITY.md` com política de disclosure e modelo local-first, CodeQL para análise automática de segurança Python, Dependabot para imagens Docker, `HEALTHCHECK` no Dockerfile (Python stdlib), `docker-compose.yml` com bind local por defeito e api_key obrigatória. Dockerfile atualizado com `apt-get upgrade` em ambos os stages (builder e runtime) para patches OS-level, e remoção de `pip`, `setuptools` e `wheel` do runtime stage para eliminar CVE-2026-23949 (jaraco.context path traversal) e CVE-2026-24049 (wheel privilege escalation) — corrige falhas nos scans Trivy dos workflows `release-gate.yml` e `security-scheduled.yml`.

### Fase 12 — Rewrite do sync: sequencial + proteção real de recursos (v0.4.1) ✅

| #   | Tarefa                                                                                                                         | Complexidade | Estado       |
| --- | ------------------------------------------------------------------------------------------------------------------------------ | ------------ | ------------ |
| 91  | ~~`sync.py`: eliminar `ThreadPoolExecutor` — processar repos sequencialmente (chunk→embed→store→gc.collect()→próximo)~~        | Média        | ✅ Concluído |
| 92  | ~~`sync.py`: remover `_chunk_single_repo()` helper (desnecessário com abordagem sequencial)~~                                  | Baixa        | ✅ Concluído |
| 93  | ~~`sync.py`: `os.nice(10)` em `main()` — processo corre com prioridade inferior~~                                              | Baixa        | ✅ Concluído |
| 94  | ~~`sync.py`: `gc.collect()` explícito após embed+store de cada repo~~                                                          | Baixa        | ✅ Concluído |
| 95  | ~~`tuning.py`: auto-tune mais conservativo (≥16GB: batch 100→50, 8-16GB: 50→25, <8GB: 25→15; workers cpu//4→cpu//6, max 8→4)~~ | Baixa        | ✅ Concluído |
| 96  | ~~`test_performance.py`: atualizar asserções para novos valores do auto-tune~~                                                 | Baixa        | ✅ Concluído |

> **Fase 12 concluída em 2026-05-10.** Solução intermédia que resolveu o freeze da máquina ao eliminar o paralelismo descontrolado. Substituída pela Fase 13 (bounded pipeline) que reintroduz paralelismo de forma segura.

### Fase 13 — Bounded Ingest Pipeline (Phase 1, v0.5.0) ✅

| #   | Tarefa                                                                                                                                                                                  | Complexidade | Estado       |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | ------------ |
| 97  | ~~`manifest.py`: SQLite manifest com WAL mode para tracking incremental (tabelas files, chunks, ingest_runs)~~                                                                          | Alta         | ✅ Concluído |
| 98  | ~~`ingest.py`: `IngestPipeline` com 4 estágios bounded: scanner thread → ProcessPoolExecutor parser → embedding batcher → writer thread~~                                               | Alta         | ✅ Concluído |
| 99  | ~~`ingest.py`: backpressure via `Queue(maxsize=...)` entre todos os estágios~~                                                                                                          | Média        | ✅ Concluído |
| 100 | ~~`ingest.py`: ProcessPoolExecutor com `spawn` context e `max_tasks_per_child=100` para isolamento de memória~~                                                                         | Média        | ✅ Concluído |
| 101 | ~~`ingest.py`: embedding batcher com 3 critérios de flush: count (24), chars (48k), time (1s)~~                                                                                         | Média        | ✅ Concluído |
| 102 | ~~`sync.py`: `sync_repos()` cria `IngestPipeline` e chama `pipeline.run(sources)` em vez de for-loop sequencial~~                                                                       | Média        | ✅ Concluído |
| 103 | ~~`config.py`: novos campos `PerformanceConfig`: `parser_workers`, `embedding_batch_max_chars`, `chunks_queue_max`, `files_queue_max`, `pause_memory_percent`, `abort_memory_percent`~~ | Baixa        | ✅ Concluído |
| 104 | ~~`tuning.py`: `auto_tune()` passa novos campos bounded pipeline~~                                                                                                                      | Baixa        | ✅ Concluído |
| 105 | ~~`code.py`: `iter_repo_files()` generator para descoberta streaming de ficheiros em repos~~                                                                                            | Baixa        | ✅ Concluído |
| 106 | ~~`markdown.py`: `iter_note_files()` generator para descoberta streaming de notas~~                                                                                                     | Baixa        | ✅ Concluído |
| 107 | ~~`chroma.py`: `upsert_embedded_batch()` — upsert com embeddings pré-calculados (sem chamar embed_texts())~~                                                                            | Baixa        | ✅ Concluído |
| 108 | ~~`chroma.py`: `delete_stale_from_collection()` — remoção de chunks obsoletos em batches de 500~~                                                                                       | Baixa        | ✅ Concluído |
| 109 | ~~`rag.toml`: secção `[performance]` com campos bounded pipeline (parser*workers, *\_queue*max, *\_memory_percent, etc.)~~                                                              | Baixa        | ✅ Concluído |
| 110 | ~~`test_manifest.py`: 25 testes para IngestManifest (CRUD, crash recovery, stale detection, WAL mode)~~                                                                                 | Média        | ✅ Concluído |
| 111 | ~~`test_ingest_pipeline.py`: 10 testes para IngestPipeline (4 estágios, backpressure, abort, metrics)~~                                                                                 | Média        | ✅ Concluído |

> **Fase 13 concluída em 2026-05-10.** Reescrita arquitetural do pipeline de ingest de repos. A unidade de processamento mudou de repos para ficheiros. O pipeline de 4 estágios com bounded queues resolve o problema de memória da Fase 12 ao introduzir backpressure real entre parsing, embedding e escrita. SQLite manifest com WAL mode permite crash recovery — syncs interrompidos retomam do último checkpoint. `ProcessPoolExecutor` com `spawn` context garante isolamento de memória por worker. `PipelineConfig.max_workers` é efectivamente dead code — `PerformanceConfig.parser_workers` é o controlo real. Total: 282 testes em 17 ficheiros. Ficheiros afetados: `sync.py`, `ingest.py` (novo), `manifest.py` (novo), `config.py`, `tuning.py`, `code.py`, `markdown.py`, `chroma.py` (posteriormente eliminado na Fase 16), `rag.toml`, `test_manifest.py` (novo), `test_ingest_pipeline.py` (novo).

### Fase 14 — Resource Governor (Bounded Pipeline Phase 2, v0.5.0) ✅

| #   | Tarefa                                                                                                                                                                 | Complexidade | Estado       |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | ------------ |
| 112 | ~~`governor.py`: `ResourceGovernor` com daemon thread psutil (1s), `check()` não-bloqueante, `wait_until_safe(timeout)`, `ResourceSnapshot` dataclass~~                | Alta         | ✅ Concluído |
| 113 | ~~`governor.py`: `GovernorAction` enum (CONTINUE/REDUCE/PAUSE/ABORT) com 3 thresholds RAM + CPU + disco~~                                                              | Média        | ✅ Concluído |
| 114 | ~~`governor.py`: ficheiro JSONL de métricas opcional (`metrics_path`) para análise post-mortem~~                                                                       | Baixa        | ✅ Concluído |
| 115 | ~~`ingest.py`: `IngestPipeline.__init__()` aceita `governor` opcional; `run()` cria governor automaticamente se não fornecido~~                                        | Média        | ✅ Concluído |
| 116 | ~~`ingest.py`: embedder stage usa `governor.check()` / `governor.wait_until_safe()` em vez de `should_throttle()` ad-hoc~~                                             | Média        | ✅ Concluído |
| 117 | ~~`sync.py`: `sync_notes()`, `sync_repos()`, `_wait_for_resources()` usam `ResourceGovernor` diretamente em vez de `should_throttle()`~~                               | Média        | ✅ Concluído |
| 118 | ~~`sync.py`: `sync_repos()` passa governor ao `IngestPipeline` — instância única monitoriza todo o pipeline~~                                                          | Baixa        | ✅ Concluído |
| 119 | ~~`tuning.py`: `should_throttle()` convertido em thin wrapper backward-compatible que delega ao `ResourceGovernor`~~                                                   | Baixa        | ✅ Concluído |
| 120 | ~~`scripts/rag-cgroup.sh`: wrapper systemd-run com MemoryMax e CPUQuota (defaults: 60% RAM, 75% CPU; configurável via `--mem`/`--cpu` ou env vars)~~                   | Média        | ✅ Concluído |
| 121 | ~~`test_governor.py`: 21 testes — `TestGovernorEvaluate` (9), `TestGovernorLifecycle` (4), `TestWaitUntilSafe` (3), `TestMetrics` (2), `TestTuningIntegration` (3)~~   | Média        | ✅ Concluído |
| 122 | ~~`test_performance.py`: testes `TestShouldThrottle` atualizados para patch `obsidian_rag.pipeline.governor.psutil` em vez de `obsidian_rag.tuning.detect_resources`~~ | Baixa        | ✅ Concluído |

> **Fase 14 concluída em 2026-05-10.** Phase 2 do bounded ingest pipeline: `ResourceGovernor` centraliza toda a lógica de monitorização de recursos num único componente com daemon thread. Substitui chamadas ad-hoc a `should_throttle()` no pipeline e sync por um monitor contínuo que amostra psutil a cada 1s e expõe `check()` não-bloqueante. `should_throttle()` mantido como thin wrapper backward-compatible. `sync_repos()` partilha a mesma instância de governor com o `IngestPipeline`. Novo script `rag-cgroup.sh` para proteção de recursos ao nível do OS via cgroups v2. Total: 282 testes em 17 ficheiros. Ficheiros afetados: `governor.py` (novo), `ingest.py`, `sync.py`, `tuning.py`, `rag-cgroup.sh` (novo), `test_governor.py` (novo), `test_performance.py`.

### Fase 15 — VectorStore Protocol + Qdrant (Phase 3, v0.5.0) ✅

| #   | Tarefa                                                                                                                                              | Complexidade | Estado       |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | ------------ |
| 123 | ~~`base.py`: `VectorStore` Protocol (`@runtime_checkable`) com 5 métodos + `QueryResult` dataclass + `create_store()` factory~~                     | Alta         | ✅ Concluído |
| 124 | ~~`chroma_store.py`: `ChromaVectorStore` — ChromaDB PersistentClient behind VectorStore protocol, lazy collection, cosine→similarity~~              | Média        | ✅ Concluído |
| 125 | ~~`qdrant_store.py`: `QdrantVectorStore` — embedded/server mode, 1024d cosine, SHA256 string→uint64 ID mapping, dep opcional~~                      | Alta         | ✅ Concluído |
| 126 | ~~`config.py`: `StoreConfig` dataclass (`backend`, `qdrant_url`, `qdrant_api_key`) + parsing `[store]` de `rag.toml`~~                              | Baixa        | ✅ Concluído |
| 127 | ~~`rag.toml`: nova secção `[store]` com `backend = "chroma"`, `qdrant_url`, `qdrant_api_key`~~                                                      | Baixa        | ✅ Concluído |
| 128 | ~~`rag.py`: refatorar `_get_collection()`/`_get_code_collection()` → `_get_store()` singleton via VectorStore protocol~~                            | Média        | ✅ Concluído |
| 129 | ~~`app.py`: refatorar `_query_collection()` → `_query_store()` via VectorStore protocol; `stats()`, `repos()` adaptados~~                           | Média        | ✅ Concluído |
| 130 | ~~`migrate_cmd.py`: `rag migrate --from X --to Y --collections ...` — migração com re-embedding entre backends~~                                    | Média        | ✅ Concluído |
| 131 | ~~`docker-compose.yml`: serviço Qdrant (v1.13.2) com `profiles: [qdrant]` nas portas 6333/6334~~                                                    | Baixa        | ✅ Concluído |
| 132 | ~~`pyproject.toml`: `[project.optional-dependencies] qdrant = ["qdrant-client>=1.9"]`~~                                                             | Baixa        | ✅ Concluído |
| 133 | ~~`test_vector_store.py`: 34 testes parametrizados (Chroma/Qdrant): upsert, count, get_existing_ids, delete, query, collection isolation, factory~~ | Média        | ✅ Concluído |
| 134 | ~~`test_integration.py`: fixture `integration_client` adaptada para `ChromaVectorStore` + `_get_store` mock~~                                       | Baixa        | ✅ Concluído |
| 135 | ~~`test_low_priority.py`: testes de singletons atualizados para `_store` em vez de `_chroma_client`/`_chroma_collection`/`_code_collection`~~       | Baixa        | ✅ Concluído |

> **Fase 15 concluída em 2026-05-10.** VectorStore Protocol (Phase 3) desacopla o retrieval e a API do ChromaDB. `VectorStore` é um `@runtime_checkable` Protocol com factory `create_store()`. Duas implementações: `ChromaVectorStore` (default) e `QdrantVectorStore` (opcional, modo embedded ou server). Qdrant usa `qdrant-client>=1.9` como dependência opcional (`pip install obsidian-rag[qdrant]`). `rag.py` e `app.py` refatorados para usar `_get_store()` singleton — sem imports diretos de ChromaDB. Novo comando `rag migrate` para migração entre backends. `docker-compose.yml` com serviço Qdrant ativável via profile. Total: 301 testes (15 skipped) em 18 ficheiros. Ficheiros afetados: `base.py` (novo), `chroma_store.py` (novo), `qdrant_store.py` (novo), `migrate_cmd.py` (novo), `config.py`, `rag.toml`, `rag.py`, `app.py`, `docker-compose.yml`, `pyproject.toml`, `test_vector_store.py` (novo), `test_integration.py`, `test_low_priority.py`.

### Fase 10 — Proteção de recursos no sync (v0.4.1) ✅

| #   | Tarefa                                                                                                                       | Complexidade | Estado       |
| --- | ---------------------------------------------------------------------------------------------------------------------------- | ------------ | ------------ |
| 77  | ~~`chroma.py`: remover `BATCH_SIZE=50` hardcoded, usar `settings.performance.embedding_batch_size`~~                         | Baixa        | ✅ Concluído |
| 78  | ~~`chroma.py`: adicionar `should_throttle()` entre cada batch de embeddings (pausa/reduz/aborta)~~                           | Média        | ✅ Concluído |
| 79  | ~~`sync.py`: throttle check em `sync_notes()` antes de iniciar~~                                                             | Baixa        | ✅ Concluído |
| 80  | ~~`sync.py`: reescrever `sync_repos()` com submissão iterativa de repos (throttle entre cada submission)~~                   | Média        | ✅ Concluído |
| 81  | ~~`sync.py`: `_wait_for_resources()` helper para transições de fase (notas→repos, local→graphify)~~                          | Média        | ✅ Concluído |
| 82  | ~~`builder.py`: adicionar `timeout=settings.performance.graph_timeout` ao `subprocess.run()` com `TimeoutExpired` handling~~ | Baixa        | ✅ Concluído |
| 83  | ~~`builder.py`: adicionar `should_throttle()` antes de cada repo em `build_graphs()`~~                                       | Baixa        | ✅ Concluído |
| 84  | ~~`config.py`: novo campo `graph_timeout: int = 600` em `PerformanceConfig`~~                                                | Baixa        | ✅ Concluído |
| 85  | ~~`tuning.py`: passar `graph_timeout` em `auto_tune()`~~                                                                     | Baixa        | ✅ Concluído |
| 86  | ~~`rag.toml`: adicionar opção `graph_timeout = 600` em `[performance]`~~                                                     | Baixa        | ✅ Concluído |

> **Fase 10 concluída em 2026-05-10.** Correcção inicial do sistema de proteção de recursos. `BATCH_SIZE=50` hardcoded removido de `chroma.py`. `subprocess.run()` no graphify tem timeout configurável (`graph_timeout=600`). **Nota:** A proteção de recursos desta fase ainda não resolvia o problema de freeze da máquina — a causa raiz (ThreadPoolExecutor + acumulação de chunks em memória) foi corrigida na Fase 12. O módulo `chroma.py` foi posteriormente eliminado na Fase 16 (Phase 3.1).

### Fase 11 — Bug fixes e operações (v0.4.1) ✅

| #   | Tarefa                                                                                               | Complexidade | Estado       |
| --- | ---------------------------------------------------------------------------------------------------- | ------------ | ------------ |
| 87  | ~~`chroma.py`: corrigir batch loop que saltava chunks quando batch_size era reduzido dinamicamente~~ | Baixa        | ✅ Concluído |
| 88  | ~~`chroma.py`: adicionar `logging` estruturado para eventos de throttle~~                            | Baixa        | ✅ Concluído |
| 89  | ~~`sync.py`: tratamento de `KeyboardInterrupt` com mensagem clara e exit code 130~~                  | Baixa        | ✅ Concluído |
| 90  | ~~`scripts/monitor_rag.sh`: script de monitorização de recursos em tempo real~~                      | Baixa        | ✅ Concluído |

> **Fase 11 concluída em 2026-05-10.** Correcção de bug crítico no batch loop de `chroma.py` que saltava chunks silenciosamente quando o batch era reduzido pelo throttle. Adicionado logging estruturado ao módulo. Tratamento gracioso de `KeyboardInterrupt` em `sync.py`. Novo script `monitor_rag.sh` para monitorização em tempo real de RAM, CPU, disco, GPU e processos RAG/Ollama/Graphify durante sync. **Nota:** O módulo `chroma.py` foi posteriormente eliminado na Fase 16 (Phase 3.1).

### Fase 16 — VectorStore write-path migration (Phase 3.1, v0.5.0) ✅

| #   | Tarefa                                                                                                                                                | Complexidade | Estado       |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | ------------ |
| 136 | ~~**ELIMINADO `store/chroma.py`**: módulo legacy removido — funcionalidade absorvida por `chroma_store.py` e `pipeline/sync.py`~~                     | Média        | ✅ Concluído |
| 137 | ~~`sync.py`: import `from store.base import VectorStore, create_store`; novo `_sync_chunks_to_store()` helper para sync incremental via VectorStore~~ | Média        | ✅ Concluído |
| 138 | ~~`sync.py`: `sync_notes()` usa `_sync_chunks_to_store(chunks, collection="obsidian_vault")` + `create_store().count()`~~                             | Baixa        | ✅ Concluído |
| 139 | ~~`sync.py`: `sync_repos()` cria store via `create_store()`, passa `store` + `collection_name` ao IngestPipeline~~                                    | Baixa        | ✅ Concluído |
| 140 | ~~`ingest.py`: construtor alterado — `collection` → `store` (VectorStore) + `collection_name: str`; writer usa `store.upsert_batch()`~~               | Média        | ✅ Concluído |
| 141 | ~~`ingest.py`: `_cleanup_stale()` usa `store.get_existing_ids()` + `store.delete_ids()` em vez de ChromaDB direto~~                                   | Baixa        | ✅ Concluído |
| 142 | ~~`backup.py`: `backup_chroma()` → `backup_store()`; ficheiros nomeados `store_backup_*`~~                                                            | Baixa        | ✅ Concluído |
| 143 | ~~`cli/_backup.py`: import `backup_store` em vez de `backup_chroma`~~                                                                                 | Baixa        | ✅ Concluído |
| 144 | ~~`cli/up_cmd.py`: secção "Vector store status" com `create_store().count()` e nome do backend~~                                                      | Baixa        | ✅ Concluído |
| 145 | ~~`cli/doctor_cmd.py`: secção "Vector Store (backend)" com `create_store().count()`~~                                                                 | Baixa        | ✅ Concluído |
| 146 | ~~`api/app.py`: novo `_count_repo_chunks()` helper com lógica backend-specific (Chroma via `where=`, Qdrant via `count_filter=`)~~                    | Média        | ✅ Concluído |
| 147 | ~~`test_ingest_pipeline.py`: `mock_store` VectorStore-compatible + `noop_governor` fixture~~                                                          | Baixa        | ✅ Concluído |
| 148 | ~~`test_medium_features.py`: import `backup_store`; glob pattern `store_backup_*`~~                                                                   | Baixa        | ✅ Concluído |

> **Fase 16 concluída em 2026-05-10.** Migração completa do write-path para o protocolo VectorStore. O módulo legacy `store/chroma.py` (`get_client()`, `get_collection()`, `sync_to_chroma()`, `sync_repo_to_chroma()`, `upsert_embedded_batch()`, `delete_stale_from_collection()`, `get_existing_ids()`) foi **eliminado**. Toda a funcionalidade de sync incremental foi absorvida pelo `VectorStore` protocol e pelo novo helper `_sync_chunks_to_store()` em `pipeline/sync.py`. `IngestPipeline` agora recebe `store` (VectorStore) + `collection_name` em vez de `collection` ChromaDB. `settings.store.backend` controla o backend para leituras **e** escritas. Todas as referências a "ChromaDB" na UI (CLI, prints) foram substituídas por "vector store" / "Store". Total: 301 testes (15 skipped) em 18 ficheiros. Ficheiros afetados: `store/chroma.py` (eliminado), `pipeline/sync.py`, `pipeline/ingest.py`, `pipeline/backup.py`, `cli/_backup.py`, `cli/up_cmd.py`, `cli/doctor_cmd.py`, `api/app.py`, `tests/test_ingest_pipeline.py`, `tests/test_medium_features.py`.

### Fase 17 — Multi-language tree-sitter chunking (Phase 4, v0.5.0) ✅

| #   | Tarefa                                                                                                                                   | Complexidade | Estado       |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------- | ------------ | ------------ |
| 149 | ~~`treesitter.py`: chunking semântico multi-linguagem via tree-sitter (10 linguagens, 17 extensões)~~                                    | Alta         | ✅ Concluído |
| 150 | ~~`treesitter.py`: language registry (extensões → grammar modules) + definition node types por linguagem~~                               | Média        | ✅ Concluído |
| 151 | ~~`treesitter.py`: `chunk_treesitter()` — extração de funções, classes, métodos, structs, interfaces, enums, traits, impls, namespaces~~ | Alta         | ✅ Concluído |
| 152 | ~~`treesitter.py`: `_extract_name()` com handling específico por linguagem (Rust impl, Go type_declaration, JS export_statement, etc.)~~ | Média        | ✅ Concluído |
| 153 | ~~`treesitter.py`: `is_available()` / `supported_extensions()` para feature detection~~                                                  | Baixa        | ✅ Concluído |
| 154 | ~~`treesitter.py`: lazy loading via `importlib.import_module()` + fallback para text chunking~~                                          | Baixa        | ✅ Concluído |
| 155 | ~~`code.py`: `_TREESITTER_EXTENSIONS` dict (17 extensões → language keys) + dispatch para `chunk_treesitter()`~~                         | Média        | ✅ Concluído |
| 156 | ~~`code.py`: `iter_repo_files()` atualizado — `valid_extensions` inclui extensões tree-sitter~~                                          | Baixa        | ✅ Concluído |
| 157 | ~~`pyproject.toml`: grupo de dependências opcionais `[treesitter]` (10 pacotes: tree-sitter + 9 grammars)~~                              | Baixa        | ✅ Concluído |
| 158 | ~~`test_chunking_treesitter.py`: 22 testes (availability, JS/TS/Java/Go/Rust/C, dispatch, edge cases)~~                                  | Média        | ✅ Concluído |

> **Fase 17 concluída em 2026-05-10.** Chunking semântico multi-linguagem via tree-sitter (Phase 4). Novo módulo `treesitter.py` com suporte para 10 linguagens (JavaScript, TypeScript, Java, Go, Rust, C, C++, C#, Ruby) mapeadas via 17 extensões de ficheiro. Extrai definições semânticas (funções, classes, métodos, structs, interfaces, enums, traits, impls, namespaces) como chunks individuais. Métodos de classes/structs/impls extraídos separadamente. Código module-level (imports, constantes) como chunk separado. `_extract_name()` com lógica específica por linguagem. Dependência opcional (`pip install obsidian-rag[treesitter]`): `tree-sitter>=0.23` + 9 grammar packages. Fallback automático para text chunking se tree-sitter não instalado. `code.py` atualizado com dispatch e descoberta de ficheiros expandida. 22 novos testes com `pytest.importorskip("tree_sitter")`. Total: 323 testes (15 skipped) em 19 ficheiros. Ficheiros afetados: `chunking/treesitter.py` (novo), `chunking/code.py`, `pyproject.toml`, `tests/test_chunking_treesitter.py` (novo).

### Fase 18 — Optional Dask Distributed Engine (Phase 5, v0.5.0) ✅

| #   | Tarefa                                                                                                                             | Complexidade | Estado       |
| --- | ---------------------------------------------------------------------------------------------------------------------------------- | ------------ | ------------ |
| 159 | ~~`dask_engine.py`: `DaskParserPool` — drop-in replacement para `ProcessPoolExecutor` usando Dask distributed~~                    | Média        | ✅ Concluído |
| 160 | ~~`dask_engine.py`: `create_parser_pool()` factory — retorna `ProcessPoolExecutor` (local) ou `DaskParserPool` (dask)~~            | Baixa        | ✅ Concluído |
| 161 | ~~`dask_engine.py`: suporte para cluster local auto-criado ou scheduler remoto via `dask_scheduler` URL~~                          | Média        | ✅ Concluído |
| 162 | ~~`config.py`: `PipelineConfig.engine` (`"local"` default) e `PipelineConfig.dask_scheduler` (`""` default)~~                      | Baixa        | ✅ Concluído |
| 163 | ~~`rag.toml`: campos `engine = "local"` e `dask_scheduler = ""` na secção `[pipeline]`~~                                           | Baixa        | ✅ Concluído |
| 164 | ~~`ingest.py`: `IngestPipeline.__init__` aceita `pipeline_config` opcional; `_parser_stage()` usa `create_parser_pool()` factory~~ | Média        | ✅ Concluído |
| 165 | ~~`ingest.py`: removidos imports `ProcessPoolExecutor` e `get_context` (movidos para `dask_engine.py`)~~                           | Baixa        | ✅ Concluído |
| 166 | ~~`sync.py`: `sync_repos()` passa `pipeline_config=settings.pipeline` ao `IngestPipeline`~~                                        | Baixa        | ✅ Concluído |
| 167 | ~~`pyproject.toml`: grupo `dask = ["dask[distributed]>=2024.1"]` em `[project.optional-dependencies]`~~                            | Baixa        | ✅ Concluído |
| 168 | ~~`test_dask_engine.py`: testes para factory local/dask, import error handling, integração com IngestPipeline~~                    | Média        | ✅ Concluído |

> **Fase 18 concluída em 2026-05-10.** Engine Dask distribuído opcional (Phase 5). Novo módulo `dask_engine.py` com `DaskParserPool` (drop-in replacement para `ProcessPoolExecutor`) e factory `create_parser_pool()`. Quando `engine = "local"` (default), usa `ProcessPoolExecutor` com `spawn` context e `max_tasks_per_child=100`. Quando `engine = "dask"`, cria `DaskParserPool` que suporta cluster local (auto-criado) ou scheduler remoto (via `dask_scheduler` URL). `IngestPipeline` agora aceita `pipeline_config` para selecção de engine. Dependência opcional: `pip install obsidian-rag[dask]` (`dask[distributed]>=2024.1`). Imports de `ProcessPoolExecutor`/`get_context` movidos de `ingest.py` para `dask_engine.py`. `sync.py` passa `pipeline_config=settings.pipeline` ao pipeline. 6 novos testes em `test_dask_engine.py` (3 skipped se dask não instalado). Total: 329 testes (18 skipped) em 20 ficheiros. Ficheiros afetados: `pipeline/dask_engine.py` (novo), `pipeline/ingest.py`, `pipeline/sync.py`, `config.py`, `rag.toml`, `pyproject.toml`, `tests/test_dask_engine.py` (novo).

---

### Fase 19 — Hotfixes de robustez (v0.5.1, 2026-05-11) ✅

| #   | Tarefa                                                                                                                                                                                              | Complexidade | Estado       |
| --- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | ------------ |
| 169 | ~~`qdrant_store.py`: `_is_meta_valid()` — valida se `meta.json` existe e contém JSON válido~~                                                                                                       | Baixa        | ✅ Concluído |
| 170 | ~~`qdrant_store.py`: `_backup_meta()` — cópia atómica de `meta.json` → `meta.json.bak` via `tempfile` + `os.replace`~~                                                                              | Baixa        | ✅ Concluído |
| 171 | ~~`qdrant_store.py`: `_recover_meta_if_corrupt()` — restaura de `.bak` se disponível; caso contrário semeia `{"collections": {}, "aliases": {}}` para evitar crash~~                                | Média        | ✅ Concluído |
| 172 | ~~`qdrant_store.py`: `__init__` chama `_recover_meta_if_corrupt()` ANTES de `QdrantClient(path=...)` e `_backup_meta()` APÓS inicialização bem-sucedida~~                                           | Baixa        | ✅ Concluído |
| 173 | ~~`ingest.py`: `_cleanup_stale(source)` substituído por `_cleanup_stale_global(all_manifest_ids)` que recolhe union de IDs de todos os repos antes de deletar~~                                     | Média        | ✅ Concluído |
| 174 | ~~`ingest.py`: `_cleanup_stale(source)` preservado para retrocompatibilidade com testes~~                                                                                                           | Baixa        | ✅ Concluído |
| 175 | ~~`markdown.py`: `_split_long_text()` — adicionado guard `start = next_start if next_start > start else end` para evitar loop infinito quando `rfind` falha ou retorna boundary próximo do início~~ | Baixa        | ✅ Concluído |
| 176 | ~~`ingest.py`: parse errors registados com `{e!r}` + `traceback.format_exc()` nos dois code paths (in-process e `_harvest_futures()`)~~                                                             | Baixa        | ✅ Concluído |
| 177 | ~~`ingest.py`: logs de progresso `[scan]`/`[parse]`/`[embed]`/`[write]` por etapa com contadores~~                                                                                                  | Baixa        | ✅ Concluído |

> **Fase 19 concluída em 2026-05-11.** Três bugs críticos descobertos e corrigidos em produção durante execução de `rag sync --all`.
>
> **Bug 1 — `_cleanup_stale` delecia chunks de todos os repos (CRÍTICO):**
> `_cleanup_stale(source)` era chamada 5× (uma vez por repo). Cada chamada calculava `existing_in_store − this_repo_manifest_ids`, eliminando todos os chunks de todos os outros repos. Após 5 iterações a `code_repos` ficava vazia (0 chunks). Causa: lógica assumia que `get_existing_ids()` só retornava IDs do repo atual, mas retorna IDs de toda a coleção. Correcção: novo método `_cleanup_stale_global(all_manifest_ids)` que recolhe a union de IDs de todos os repos primeiro e corre uma única vez no final. `_cleanup_stale(source)` preservado para compatibilidade com testes. **Impacto:** `code_repos` passou de 0 para 150 chunks após a correcção.
>
> **Bug 2 — `_split_long_text` loop infinito em markdown.py (CRÍTICO):**
> `_split_long_text(text, max_chars, overlap)` entrava em loop infinito ao processar ficheiros Markdown longos (ex: `PROJECT_OVERVIEW.md`, ~10 000 chars). Quando `rfind(". ")` encontrava um boundary muito próximo do `start`, o cálculo `end - overlap` produzia `next_start <= start`. O cursor nunca avançava → loop infinito → `MemoryError()` com `str(e) == ""` → parse error sem mensagem. Correcção: `start = next_start if next_start > start else end`. `PROJECT_OVERVIEW.md` produz agora 114 chunks sem travar.
>
> **Bug 3 — Qdrant `meta.json` corrupção no startup (CRÍTICO):**
> `QdrantClient(path=...)` no modo embedded crashava com `json.decoder.JSONDecodeError` se `meta.json` ficasse truncado (0 bytes) após um processo ser morto a meio de uma escrita. Correcção: `_recover_meta_if_corrupt()` chamado antes da inicialização — verifica se o ficheiro é válido; se não for, tenta restaurar de `meta.json.bak`; se também inválido, semeia `{"collections": {}, "aliases": {}}`. `_backup_meta()` chamado após inicialização bem-sucedida para manter a cópia de segurança actualizada.
>
> **Melhoria 4 — Logs de progresso no IngestPipeline:**
> Cada etapa do pipeline (`[scan]`, `[parse]`, `[embed]`, `[write]`) emite agora prints com contadores. Parse errors incluem `repr(e)` + traceback completo em vez de mensagem vazia. Permite acompanhar `rag sync --all` em tempo real sem depender de debug mode.
>
> Ficheiros afetados: `store/qdrant_store.py`, `pipeline/ingest.py`, `chunking/markdown.py`. Testes validados: 34 (`test_vector_store.py`) + 35 (`test_ingest_pipeline.py` + `test_manifest.py`) + 62 (`test_chunking_markdown.py`) — todos passam.

---

### Fase 20 — Escalabilidade para bases de conhecimento maiores (v1.1)

> **Objectivo:** Preparar o obsidian-rag para crescer de centenas para milhares de notas e dezenas de repos, sem degradação de performance ou qualidade de retrieval.

#### Prioridade 1 — Bottlenecks de escala (bloqueantes)

| #   | Tarefa                                                                                                                                                                                                           | Complexidade | Estado       | Ref  |
| --- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | ------------ | ---- |
| 178 | ~~**Migrar `sync_notes()` para `IngestPipeline`**~~ — `sync_notes()` usa agora bounded pipeline 4-estágios com `iter_note_files()` generator. `_sync_chunks_to_store()` removido. `chunk_all_notes()` deprecated | Média        | ✅ Concluído | §8.3 |
| 179 | ~~**Manifest incremental para notas**~~ — resolvido automaticamente por #178. Notas partilham `manifest.db` com repos sem colisão                                                                                | Baixa        | ✅ Concluído | §8.4 |
| 180 | ~~**`gc.collect()` entre repos no graphify**~~ — `gc.collect()` adicionado após cada repo em `build_graphs()` (paths sequencial e paralelo)                                                                      | Baixa        | ✅ Concluído | —    |
| 181 | ~~**`rag doctor` métricas de escala**~~ — nova secção "Escala" no doctor: chunks por coleção, tamanho manifest, VRAM actual, disco (data dir)                                                                    | Baixa        | ✅ Concluído | —    |

#### Prioridade 2 — Qualidade de retrieval a escala

| #   | Tarefa                                                                                                                                                                                                                                      | Complexidade | Estado       | Ref  |
| --- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | ------------ | ---- |
| 182 | **Hybrid search (sparse + dense)** — adicionar sparse vectors (BM25-like) ao pipeline de embedding e ao `VectorStore.query()`. Qdrant suporta nativamente `SparseVector`. Requer: tokenizer BM25 local, alteração ao Protocol, query fusion | Média        | Não iniciado | §8.5 |
| 183 | ~~**Query filtering por metadata**~~ — `VectorStore.query()` aceita `filters: dict` (Qdrant payload filter + ChromaDB `where`). `/query/code` usa filtro query-time por `repo_name`/`symbol_type`. CLI: `rag query --repo X "texto"`        | Baixa        | ✅ Concluído | §8.6 |
| 184 | ~~**Adaptive top_k por tamanho de coleção**~~ — `_scale_k_by_size()` escala `effective_k` por `1 + log10(size/1000)` quando >1000 chunks. Cache TTL 60s via `_cached_count()`. Bounds: min 3, max 30                                        | Baixa        | ✅ Concluído | —    |

#### Prioridade 3 — Latência e throughput

| #   | Tarefa                                                                                                                                                                                                                              | Complexidade | Estado       | Ref  |
| --- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | ------------ | ---- |
| 185 | **Reranker paralelo** — paralelizar chamadas LLM do reranker com `ThreadPoolExecutor(max_workers=min(3, n))`, mesmo padrão de `enrich.py`. Cada chamada é I/O-bound HTTP. Reduz latência 3-5× com `top_k_candidates=30`             | Baixa        | Não iniciado | §8.7 |
| 186 | **Graphify incremental por ficheiro** — tracking de ficheiros alterados por repo (via manifest ou hash comparison) e rebuild parcial apenas dos ficheiros modificados. Depende de suporte da lib `graphifyy` para extracção parcial | Média        | Não iniciado | §8.8 |

#### Prioridade 4 — Infraestrutura e funcionalidades futuras

| #   | Tarefa                                                                                                                                                                                                                                 | Complexidade | Estado       | Ref   |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------ | ------------ | ----- |
| 187 | **Documentação operacional Qdrant server** — guia para migrar de embedded para server mode quando >50k chunks. Inclui `docker-compose.yml` (já tem profile), configuração de `qdrant_url`, benchmark embedded vs. server               | Baixa        | Não iniciado | §8.9  |
| 188 | **Multi-vault Obsidian** — suportar `vault_dirs = [...]` em `rag.toml` com coleções separadas por vault. Alteração a `PathsConfig`, `sync_notes()`, lógica de coleções, e queries scoped (`rag query --vault pessoal "texto"`)         | Média        | Não iniciado | §8.10 |
| 189 | **Ollama env vars no systemd** — automatizar configuração de `OLLAMA_NUM_PARALLEL=2` e `OLLAMA_MAX_LOADED_MODELS=2` via `rag init` ou `rag doctor --fix`. Verifica se as env vars estão definidas no serviço Ollama e sugere correcção | Baixa        | Não iniciado | —     |
| 190 | **Métricas de sync em dashboard** — exportar métricas do pipeline (chunks/s, tempo por fase, VRAM usage) para ficheiro JSON/Parquet consultável. Possibilidade futura de dashboard web via `/metrics` endpoint                         | Baixa        | Não iniciado | —     |

#### Ordem de execução recomendada

```
Fase 20 — Plano de execução v1.1
═══════════════════════════════════════════════════════════════════

Sprint 1 — Fundações de escala (bloqueante)
──────────────────────────────────────────────────────────────────
  #178  sync_notes → IngestPipeline        [Média]  ← O mais urgente
  #179  Manifest incremental p/ notas      [Baixa]  ← resolvido por #178
  #180  gc.collect() no graphify           [Baixa]  ← fix rápido
  #181  rag doctor métricas de escala      [Baixa]  ← observabilidade

Sprint 2 — Qualidade de retrieval
──────────────────────────────────────────────────────────────────
  #183  Query filtering por metadata       [Baixa]  ✅ Concluído
  #184  Adaptive top_k por coleção         [Baixa]  ✅ Concluído
  #182  Hybrid search (sparse + dense)     [Média]  ← maior impacto, mais complexo

Sprint 3 — Latência e throughput
──────────────────────────────────────────────────────────────────
  #185  Reranker paralelo                  [Baixa]  ← padrão já provado em enrich.py
  #186  Graphify incremental               [Média]  ← depende de lib graphifyy

Sprint 4 — Infraestrutura futura
──────────────────────────────────────────────────────────────────
  #187  Docs Qdrant server mode            [Baixa]  ← quando >50k chunks
  #188  Multi-vault Obsidian               [Média]  ← quando vaults múltiplos
  #189  Ollama env vars automation         [Baixa]  ← DX improvement
  #190  Métricas de sync em dashboard      [Baixa]  ← observabilidade avançada
```

#### Dependências entre tarefas

```
#178 ──→ #179 (manifest automático via IngestPipeline)
#182 ──→ precisa de #183 implementado primeiro (Protocol query com filters)
#186 ──→ investigar API da lib graphifyy para extracção parcial
#188 ──→ precisa de #183 (queries scoped por coleção/vault)
```

#### O que NÃO entra na v1.1

| Tecnologia              | Razão                                                                                        |
| ----------------------- | -------------------------------------------------------------------------------------------- |
| `sentence-transformers` | Ollama já faz embeddings GPU; duplicar = conflito de VRAM com modelos carregados             |
| `torch.cuda`            | Sem uso directo de CUDA no projecto; tudo delegado ao Ollama                                 |
| `Ray` / `Celery`        | Overkill para single-user local; bounded pipeline com backpressure é a arquitectura correcta |
| `Polars` / `DuckDB`     | SQLite manifest é adequado até ~1M ficheiros; não há ETL tabular pesado                      |
| `RAPIDS` / `cuDF`       | Zero processamento tabular na GPU; VRAM reservada para modelos LLM                           |
| `Faiss`                 | Qdrant já resolve busca vectorial; Faiss-GPU competiria por VRAM com Ollama                  |

---

## Regra de manutenção da documentação

> **Sempre que qualquer alteração for feita ao projeto** — código, configuração, modelos, prompts, arquitetura, dependências, novo agente, nova funcionalidade — **este documento e `docs/PROJECT_OVERVIEW.md` devem ser atualizados obrigatoriamente.**
>
> Uma tarefa só é considerada concluída quando a documentação relevante tiver sido revista e atualizada.
