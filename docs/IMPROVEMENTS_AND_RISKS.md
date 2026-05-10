# IMPROVEMENTS AND RISKS — obsidian-rag

> **Versão:** 0.4.1  
> **Última atualização:** 2026-05-10  
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

**Resolução (2026-05-10):** Implementados 83 unit tests com pytest em 5 ficheiros (`test_chunking_markdown.py`, `test_chunking_code.py`, `test_router.py`, `test_budget.py`, `test_api.py`) + `conftest.py` com fixtures partilhadas. Dependências de dev adicionadas ao `pyproject.toml` (`pytest>=8.0`, `pytest-asyncio>=0.23`, `coverage>=7.0`). Todos os testes passam em <1s sem dependências externas (Ollama, ChromaDB). Total atual: 157 testes em 12 ficheiros. Faltam integration tests e2e com Ollama.

### 1.2 ~~Singletons mutáveis para coleções ChromaDB~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                                                                    |
| ---------------------- | ---------------------------------------------------------------------------------------------------------- |
| **Prioridade**         | ~~Média~~ — Resolvido                                                                                      |
| **Impacto**            | Médio — dificulta testes e pode causar state leaks                                                         |
| **Complexidade**       | Baixa                                                                                                      |
| **Ficheiros afetados** | `obsidian_rag/retrieval/rag.py` (`_chroma_collection`, `_code_collection`), `obsidian_rag/store/chroma.py` |

**Resolução (2026-05-10):** `_get_collection()` e `_get_code_collection()` aceitam agora parâmetro `_override` para injeção de dependências em testes. `_get_code_collection` partilha o `_chroma_client` global em vez de criar instância separada. Adicionada `_reset_collections()` para cleanup em testes. 16 integration tests validam o padrão com ChromaDB in-memory.

### 1.3 Acoplamento entre retrieval e ChromaDB

| Campo                  | Detalhe                                                                           |
| ---------------------- | --------------------------------------------------------------------------------- |
| **Prioridade**         | Baixa                                                                             |
| **Impacto**            | Médio — dificulta trocar o vector store por alternativas (Qdrant, Weaviate, etc.) |
| **Complexidade**       | Alta                                                                              |
| **Ficheiros afetados** | `obsidian_rag/retrieval/rag.py`, `obsidian_rag/store/chroma.py`                   |

O `rag.py` importa diretamente funções do `chroma.py`. Não existe abstração (interface/protocolo) para o vector store, o que torna a substituição do ChromaDB trabalhosa.

### 1.4 Dependência de subprocess para Graphify

| Campo                  | Detalhe                                            |
| ---------------------- | -------------------------------------------------- |
| **Prioridade**         | Baixa                                              |
| **Impacto**            | Baixo — funciona, mas é frágil e difícil de testar |
| **Complexidade**       | Baixa                                              |
| **Ficheiros afetados** | `obsidian_rag/graph/builder.py`                    |

O `builder.py` invoca `graphify extract` via `subprocess.run`. Erros do CLI são capturados apenas pelo return code e stdout/stderr. Não existe tratamento estruturado de erros da ferramenta.

---

## 2. Problemas técnicos

### 2.1 ~~Estimativa de tokens por contagem de caracteres~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                                  |
| ---------------------- | ------------------------------------------------------------------------ |
| **Prioridade**         | ~~Média~~ — Resolvido                                                    |
| **Impacto**            | Médio — pode truncar contexto útil prematuramente ou ultrapassar limites |
| **Complexidade**       | Média                                                                    |
| **Ficheiros afetados** | `obsidian_rag/retrieval/budget.py`                                       |

**Resolução (2026-05-10):** `estimate_tokens()` agora usa tokenização regex word-boundary (`re.findall(r'\b\w+\b', text)`) com multiplicador 1.3× em vez de `len(text) // 4`. Mais preciso para textos multilíngues (PT + EN) e código.

### 2.2 Embedding cache com LRU fixo

| Campo                  | Detalhe                                                 |
| ---------------------- | ------------------------------------------------------- |
| **Prioridade**         | Baixa                                                   |
| **Impacto**            | Baixo — pode desperdiçar memória ou causar cache misses |
| **Complexidade**       | Baixa                                                   |
| **Ficheiros afetados** | `obsidian_rag/embeddings/ollama.py`                     |

O `@lru_cache(maxsize=128)` em `_cached_embed()` é aplicado ao nível do módulo. O cache nunca é invalidado (exceto por eviction LRU). Em sessões longas, pode acumular embeddings desatualizados.

### 2.3 Timeouts hardcoded no embed_texts

| Campo                  | Detalhe                                                              |
| ---------------------- | -------------------------------------------------------------------- |
| **Prioridade**         | Baixa                                                                |
| **Impacto**            | Baixo — o timeout de 120s pode ser insuficiente para batches grandes |
| **Complexidade**       | Baixa                                                                |
| **Ficheiros afetados** | `obsidian_rag/embeddings/ollama.py`                                  |

O `httpx.post()` em `embed_texts()` usa `timeout=120.0` hardcoded. Deveria ser configurável via `rag.toml`.

### 2.4 Graphify `OLLAMA_API_KEY=ollama` hardcoded

| Campo                  | Detalhe                                    |
| ---------------------- | ------------------------------------------ |
| **Prioridade**         | Baixa                                      |
| **Impacto**            | Baixo — funciona localmente, mas é confuso |
| **Complexidade**       | Baixa                                      |
| **Ficheiros afetados** | `obsidian_rag/graph/builder.py`            |

O `builder.py` injeta `OLLAMA_API_KEY=ollama` no ambiente do subprocess. Este valor é um placeholder necessário pela ferramenta Graphify, mas está hardcoded sem documentação inline.

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

**Resolução (2026-05-10):** Criado `.github/workflows/ci.yml` com dois jobs: `lint` (ruff check + mypy) e `test` (pytest + coverage --fail-under=50). Triggers: push/PR na branch main.

### 3.4 ~~Versão hardcoded em múltiplos locais~~

| Campo                  | Detalhe                                                                                    |
| ---------------------- | ------------------------------------------------------------------------------------------ |
| **Prioridade**         | Baixa                                                                                      |
| **Impacto**            | Baixo — risco de dessincronização de versões                                               |
| **Complexidade**       | Baixa                                                                                      |
| **Ficheiros afetados** | `pyproject.toml` (v0.4.0), `obsidian_rag/api/app.py` (versão em `/health` e FastAPI title) |

A versão `0.3.0` está hardcoded em pelo menos 3 locais. Deveria usar-se `importlib.metadata.version()` ou uma variável centralizada.

---

## 4. Possíveis bugs e inconsistências

### 4.1 Race condition na inicialização de singletons

| Campo                  | Detalhe                                                                         |
| ---------------------- | ------------------------------------------------------------------------------- |
| **Prioridade**         | Baixa                                                                           |
| **Impacto**            | Baixo — improvável em single-worker, mas possível com múltiplos workers uvicorn |
| **Complexidade**       | Baixa                                                                           |
| **Ficheiros afetados** | `obsidian_rag/retrieval/rag.py`                                                 |

Os singletons `_chroma_collection` e `_code_collection` não são thread-safe. Se o uvicorn usar múltiplos workers, pode haver inicializações duplicadas.

### 4.2 Keyword search sem normalização Unicode

| Campo                  | Detalhe                                                             |
| ---------------------- | ------------------------------------------------------------------- |
| **Prioridade**         | Baixa                                                               |
| **Impacto**            | Baixo — queries com acentos podem falhar na correspondência keyword |
| **Complexidade**       | Baixa                                                               |
| **Ficheiros afetados** | `obsidian_rag/retrieval/rag.py` (`_extract_keywords()`)             |

A função `_extract_keywords()` faz `.lower()` mas não normaliza caracteres Unicode (NFD/NFC). Acentos e diacríticos podem impedir matches legítimos.

### 4.3 Stop words exclusivamente em português

| Campo                  | Detalhe                                            |
| ---------------------- | -------------------------------------------------- |
| **Prioridade**         | Baixa                                              |
| **Impacto**            | Baixo — keyword search em inglês é menos eficaz    |
| **Complexidade**       | Baixa                                              |
| **Ficheiros afetados** | `obsidian_rag/retrieval/rag.py` (`_PT_STOP_WORDS`) |

A lista de stop words é apenas em português. Queries em inglês mantêm stop words como "the", "is", "are" nos termos de pesquisa keyword, reduzindo eficácia.

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

### 5.4 ~~Subprocess sem sanitização de paths~~ ✅ PARCIALMENTE RESOLVIDO

| Campo                  | Detalhe                                                         |
| ---------------------- | --------------------------------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Parcialmente resolvido                              |
| **Impacto**            | Baixo — os paths vêm de `rag.toml`, controlado pelo utilizador  |
| **Complexidade**       | Baixa                                                           |
| **Ficheiros afetados** | `obsidian_rag/graph/builder.py`, `obsidian_rag/cli/init_cmd.py` |

**Melhoria (v0.4.0):** `rag init` agora valida paths contra locações perigosas (`/`, `~`, `.ssh`, `.gnupg`, `.cache`, `.local/share/Trash`, directorias de sistema). Paths em `rag.toml` passam por validação antes de serem escritos. Os paths em `builder.py` continuam sem validação runtime (risco baixo pois vêm de `rag.toml`).

### 5.5 ChromaDB telemetria desativada mas sem validação

| Campo                  | Detalhe                                               |
| ---------------------- | ----------------------------------------------------- |
| **Prioridade**         | Baixa                                                 |
| **Impacto**            | Baixo — `anonymized_telemetry=False` está configurado |
| **Complexidade**       | Baixa                                                 |
| **Ficheiros afetados** | `obsidian_rag/store/chroma.py`                        |

A telemetria do ChromaDB é desativada explicitamente (`anonymized_telemetry=False`), o que é correto. Mantém-se como nota de verificação.

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

**Resolução (2026-05-10):** Novo módulo `obsidian_rag/pipeline/backup.py` com função `backup_chroma()`. Cria cópias timestamped do diretório ChromaDB via `shutil.copytree` com rotação automática (mantém últimas 3 cópias). Novo entry point CLI `rag-backup` em `pyproject.toml`.

### 6.3 Ficheiros source/ contêm cópia do vault

| Campo                  | Detalhe                               |
| ---------------------- | ------------------------------------- |
| **Prioridade**         | Baixa                                 |
| **Impacto**            | Baixo — duplicação de dados sensíveis |
| **Complexidade**       | Baixa                                 |
| **Ficheiros afetados** | `source/`                             |

A pasta `source/` contém uma cópia (rsync) das notas Obsidian. Se o repositório for partilhado, dados pessoais podem ser expostos. O `.gitignore` deve excluir `source/` e `data/`.

---

## 7. Performance

### 7.1 ~~Sync síncrono e sequencial~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                   |
| ---------------------- | --------------------------------------------------------- |
| **Prioridade**         | ~~Média~~ — Resolvido                                     |
| **Impacto**            | Médio — sync de muitos repos é lento                      |
| **Complexidade**       | Média                                                     |
| **Ficheiros afetados** | `obsidian_rag/pipeline/sync.py`, `obsidian_rag/config.py` |

**Resolução (2026-05-10):** `sync_repos()` agora usa `concurrent.futures.ThreadPoolExecutor` para processar repos em paralelo. Nova configuração `[pipeline] max_workers = 4` em `rag.toml`. Novo dataclass `PipelineConfig` em `config.py`.

### 7.2 ~~Embedding batch size fixo~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                         |
| ---------------------- | --------------------------------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Resolvido                                           |
| **Impacto**            | Baixo — batch size de 50 pode não ser ótimo para todos os casos |
| **Complexidade**       | Baixa                                                           |
| **Ficheiros afetados** | `obsidian_rag/store/chroma.py` (`BATCH_SIZE = 50`)              |

**Resolução (2026-05-10):** O batch size de embeddings é agora configurável via `[performance] embedding_batch_size` em `rag.toml`. Quando `auto_tune=true` (default), o valor é ajustado automaticamente com base na RAM disponível: 25 (<8GB), 50 (8-16GB), 100 (>16GB). Novo `PerformanceConfig` em `config.py`, com auto-tuning em `tuning.py`.

### 7.3 Router LLM adiciona latência

| Campo                  | Detalhe                                                              |
| ---------------------- | -------------------------------------------------------------------- |
| **Prioridade**         | Baixa                                                                |
| **Impacto**            | Baixo — gemma3:4b é rápido (~77 tok/s) mas adiciona 0.5-2s por query |
| **Complexidade**       | Baixa                                                                |
| **Ficheiros afetados** | `obsidian_rag/retrieval/router.py`                                   |

Cada query passa pelo LLM router antes do retrieval. Com `gemma3:4b` é rápido, mas adiciona latência percetível. O fallback para keyword heuristic em caso de timeout (15s) mitiga o pior caso.

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

### 8.2 ChromaDB como vector store

| Campo                  | Detalhe                                    |
| ---------------------- | ------------------------------------------ |
| **Prioridade**         | Baixa                                      |
| **Impacto**            | Baixo — ChromaDB escala bem até ~1M chunks |
| **Complexidade**       | Alta                                       |
| **Ficheiros afetados** | `obsidian_rag/store/chroma.py`             |

O ChromaDB é adequado para o volume atual. Para vaults com dezenas de milhares de notas, pode ser necessário migrar para Qdrant, Milvus ou similar.

---

## 9. Organização do código

### 9.1 Estrutura modular (positivo)

O código está bem organizado em módulos temáticos (`cli/`, `chunking/`, `embeddings/`, `retrieval/`, `graph/`, `store/`, `api/`, `pipeline/`, `prompts/`). A separação de responsabilidades é clara.

### 9.2 Config centralizada com lazy loading (positivo)

Toda a configuração está em `rag.toml` com env overrides, frozen dataclasses e path resolution. Desde v0.4.0, `settings` é um `_LazySettings` proxy que só carrega no primeiro acesso, permitindo que `rag init` e `rag doctor` funcionem sem `rag.toml`. Helper `config_exists()` adicionado.

### 9.3 CLI unificado (positivo — v0.4.0)

Desde v0.4.0, existe um único entry point `rag` com subcomandos em vez de 5 comandos separados. O dispatcher em `cli/main.py` usa imports lazy para não carregar `settings` em comandos que não precisam (ex: `rag init`, `rag doctor`).

### 9.4 Falta de `__all__` exports

| Campo                  | Detalhe                                                          |
| ---------------------- | ---------------------------------------------------------------- |
| **Prioridade**         | Baixa                                                            |
| **Impacto**            | Baixo — API pública dos módulos não está definida explicitamente |
| **Complexidade**       | Baixa                                                            |
| **Ficheiros afetados** | Todos os `__init__.py`                                           |

Os ficheiros `__init__.py` não definem `__all__`, tornando o API público de cada módulo implícito.

---

## 10. Melhorias recomendadas

### 10.1 ~~Testes automatizados~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                |
| ---------------------- | -------------------------------------- |
| **Prioridade**         | ~~Alta~~ — Resolvido                   |
| **Impacto**            | Alto — permite refatorar com confiança |
| **Complexidade**       | Média                                  |
| **Ficheiros afetados** | `tests/`, `pyproject.toml`             |

**Resolução (2026-05-10):** 157 testes implementados com pytest (83 unit iniciais + funcionalidades médias + 16 integration + CLI dispatch + init + security + 10 performance + 16 adaptive top_k). Cobertura de chunking (markdown + code), router heuristic, budget allocation, API auth, backup, sync paralelo, logging JSON, tokenizer regex, CLI dispatcher, path validation, bind validation, `PerformanceConfig`, `auto_tune`, `should_throttle`, `_estimate_complexity`, adaptive top_k scaling e integration tests com TestClient + ChromaDB in-memory. Fixtures partilhadas em `conftest.py`. Nenhum teste depende de serviços externos.

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

### 10.8 Chunking multi-linguagem

| Campo                  | Detalhe                             |
| ---------------------- | ----------------------------------- |
| **Prioridade**         | Baixa                               |
| **Impacto**            | Médio — suportaria repos não-Python |
| **Complexidade**       | Alta                                |
| **Ficheiros afetados** | `obsidian_rag/chunking/code.py`     |

O AST chunking só funciona para Python. Para suportar JavaScript, TypeScript, Rust, etc., seria necessário integrar tree-sitter ou equivalente.

### 10.9 Reranker habilitado por defeito (com cache)

| Campo                  | Detalhe                                          |
| ---------------------- | ------------------------------------------------ |
| **Prioridade**         | Baixa                                            |
| **Impacto**            | Médio — melhora qualidade das respostas          |
| **Complexidade**       | Baixa                                            |
| **Ficheiros afetados** | `obsidian_rag/retrieval/reranker.py`, `rag.toml` |

O reranker está implementado mas desativado. Habilitar por defeito com cache de resultados reduziria o impacto na latência.

### 10.10 ~~Sync paralelo~~ ✅ RESOLVIDO

| Campo                  | Detalhe                                                   |
| ---------------------- | --------------------------------------------------------- |
| **Prioridade**         | ~~Baixa~~ — Resolvido                                     |
| **Impacto**            | Médio — sync mais rápido para múltiplos repos             |
| **Complexidade**       | Média                                                     |
| **Ficheiros afetados** | `obsidian_rag/pipeline/sync.py`, `obsidian_rag/config.py` |

**Resolução (2026-05-10):** `sync_repos()` agora usa `concurrent.futures.ThreadPoolExecutor` com `max_workers` configurável (defeito: 4). Novo dataclass `PipelineConfig` em `config.py`. Configuração via `[pipeline] max_workers` em `rag.toml`.

### 10.11 Stop words bilíngues

| Campo                  | Detalhe                                  |
| ---------------------- | ---------------------------------------- |
| **Prioridade**         | Baixa                                    |
| **Impacto**            | Baixo — melhora keyword search em inglês |
| **Complexidade**       | Baixa                                    |
| **Ficheiros afetados** | `obsidian_rag/retrieval/rag.py`          |

Adicionar stop words em inglês à lista `_PT_STOP_WORDS` ou criar lista separada `_EN_STOP_WORDS`.

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

| #   | Tarefa                                                    | Complexidade | Estado       |
| --- | --------------------------------------------------------- | ------------ | ------------ |
| 6   | ~~Integration tests com TestClient + ChromaDB in-memory~~ | Média        | ✅ Concluído |
| 7   | ~~Configurar ruff/mypy no pyproject.toml~~                | Baixa        | ✅ Concluído |
| 8   | ~~CI/CD básico (GitHub Actions: lint + test)~~            | Média        | ✅ Concluído |
| 9   | ~~Rate limiting com slowapi~~                             | Baixa        | ✅ Concluído |
| 10  | ~~Tokenizer real para budget~~                            | Média        | ✅ Concluído |
| C3  | ~~Sync paralelo de repos (ThreadPoolExecutor)~~           | Média        | ✅ Concluído |
| D1  | ~~Logging estruturado JSON~~                              | Baixa        | ✅ Concluído |
| D2  | ~~Backup ChromaDB com rotação~~                           | Baixa        | ✅ Concluído |
| D3  | ~~Containerização Docker~~                                | Baixa        | ✅ Concluído |

> **Fase 2 concluída em 2026-05-10.** Todas as tarefas de média prioridade foram implementadas. 157 testes passam sem deps externas.

### Fase 3 — Evolução (Baixa prioridade)

| #   | Tarefa                                   | Complexidade | Estado                                          |
| --- | ---------------------------------------- | ------------ | ----------------------------------------------- |
| 11  | ~~Dockerfile + docker-compose~~          | Baixa        | ✅ Concluído                                    |
| 12  | ~~Logging estruturado (JSON)~~           | Baixa        | ✅ Concluído                                    |
| 13  | Habilitar reranker com cache             | Baixa        |                                                 |
| 14  | ~~Sync paralelo para múltiplos repos~~   | Média        | ✅ Concluído                                    |
| 15  | Chunking multi-linguagem (tree-sitter)   | Alta         |                                                 |
| 16  | Versão centralizada (importlib.metadata) | Baixa        |                                                 |
| 17  | ~~Health check do Ollama no startup~~    | Baixa        | ✅ Concluído (v0.4.0 — `rag up` + `rag doctor`) |
| 18  | Stop words bilíngues (PT + EN)           | Baixa        |                                                 |

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
| 28  | ~~Testes CLI + init + security + performance + adaptive top_k (157 total)~~ | Média        | ✅ Concluído |

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
| 37  | ~~26 novos testes (performance + adaptive top_k) — 157 total~~   | Média        | ✅ Concluído |

> **Fase 5 concluída em 2026-05-10.** Auto-tuning de recursos, adaptive top_k, proteção de recursos no sync, verificação de disco, nova dependência `psutil`.

---

## Regra de manutenção da documentação

> **Sempre que qualquer alteração for feita ao projeto** — código, configuração, modelos, prompts, arquitetura, dependências, novo agente, nova funcionalidade — **este documento e `docs/PROJECT_OVERVIEW.md` devem ser atualizados obrigatoriamente.**
>
> Uma tarefa só é considerada concluída quando a documentação relevante tiver sido revista e atualizada.
