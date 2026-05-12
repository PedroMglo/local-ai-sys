# Qdrant Server Mode — Guia de Migração

## Quando Migrar

O modo **embedded** (predefinido) é adequado para a maioria dos casos de uso local:

- Até ~50 000 chunks (notas + código)
- Um único utilizador/processo a aceder ao store
- Startup rápido sem dependências externas

Considera migrar para **server mode** quando:

- O store ultrapassa ~50 000 chunks (coleções `obsidian_vault` + `code_repos`)
- Precisas de acesso concorrente (e.g. API + sync em paralelo)
- Queres isolar o ciclo de vida do Qdrant (restart independente, backups separados)
- Planeias usar a dashboard Web do Qdrant (`http://localhost:6333/dashboard`)

---

## 1. Lançar o Servidor Qdrant

O projecto já inclui um serviço Qdrant no `docker-compose.yml`, sob o profile `qdrant`:

```bash
# Arrancar apenas o Qdrant (sem o container da API)
docker compose --profile qdrant up -d

# Verificar que está a correr
curl -s http://localhost:6333/healthz
# Resposta esperada: {"title":"qdrant - vectorass engine","version":"1.13.2"}
```

O serviço expõe:

- **REST API**: `http://localhost:6333` (bind a 127.0.0.1)
- **gRPC**: `localhost:6334`
- **Dashboard**: `http://localhost:6333/dashboard`

Os dados ficam persistidos em `./data/qdrant_server/`.

---

## 2. Configurar `rag.user.toml`

Altera a secção `[store]`:

```toml
[store]
backend = "qdrant"
qdrant_url = "http://localhost:6333"   # ← activar server mode
qdrant_api_key = ""                     # vazio para local (sem autenticação)
```

Ou via variáveis de ambiente (útil para Docker/CI):

```bash
export RAG_STORE_QDRANT_URL="http://localhost:6333"
```

> **Nota**: Quando `qdrant_url` está definido, o campo `data_dir` é ignorado.
> O Qdrant client liga-se directamente ao servidor.

---

## 3. Migrar Dados do Modo Embedded

Se já tens chunks indexados em modo embedded (`data/qdrant/`), é necessário
re-indexar — o formato interno do Qdrant embedded não é directamente
compatível com o servidor.

### Opção A — Re-sync completo (recomendado)

```bash
# 1. Garantir que o servidor Qdrant está a correr
docker compose --profile qdrant up -d

# 2. Configurar qdrant_url no rag.user.toml (passo 2 acima)

# 3. Re-indexar tudo
rag sync --all
```

Isto re-processa notas e código, gera embeddings, e armazena no servidor.
Demora o mesmo tempo que o primeiro sync inicial.

### Opção B — Exportar/importar via snapshots (avançado)

O Qdrant suporta [snapshots](https://qdrant.tech/documentation/concepts/snapshots/)
para backup e migração entre instâncias:

```bash
# No servidor: criar snapshot de uma coleção
curl -X POST http://localhost:6333/collections/obsidian_vault/snapshots

# Restaurar noutro servidor
curl -X PUT http://target:6333/collections/obsidian_vault/snapshots/recover \
  -H "Content-Type: application/json" \
  -d '{"location": "http://source:6333/collections/obsidian_vault/snapshots/<snapshot>"}'
```

---

## 4. Verificar a Migração

```bash
# Verificar contagens via API
rag doctor

# Ou directamente via REST
curl -s http://localhost:6333/collections/obsidian_vault | python3 -m json.tool
curl -s http://localhost:6333/collections/code_repos | python3 -m json.tool

# Testar uma query
rag query "test query"
```

---

## 5. Voltar ao Modo Embedded

Para reverter, basta limpar o `qdrant_url`:

```toml
[store]
backend = "qdrant"
qdrant_url = ""          # ← volta ao embedded
qdrant_api_key = ""
```

Os dados do servidor permanecem em `./data/qdrant_server/`.
Os dados embedded permanecem em `./data/qdrant/qdrant/`.

---

## Referência: Embedded vs Server

| Aspecto           | Embedded                       | Server                               |
| ----------------- | ------------------------------ | ------------------------------------ |
| Dependências      | Apenas `qdrant-client`         | Docker + imagem `qdrant/qdrant`      |
| Startup           | ~0.5s (in-process)             | ~2-3s (container)                    |
| Concorrência      | Processo único                 | Multi-processo / multi-cliente       |
| Memória           | Partilhada com a app           | Isolada no container                 |
| Dashboard         | Não disponível                 | `http://localhost:6333/dashboard`    |
| Snapshots/Backups | Cópia manual de `data/qdrant/` | API de snapshots nativa              |
| Escala            | Até ~50k chunks                | ~1M+ chunks                          |
| Configuração      | Zero config                    | `docker compose --profile qdrant up` |

---

## Docker Compose — Referência Completa

O serviço Qdrant no `docker-compose.yml`:

```yaml
qdrant:
  image: qdrant/qdrant:v1.13.2
  ports:
    - "127.0.0.1:6333:6333" # REST API (bind local)
    - "127.0.0.1:6334:6334" # gRPC
  volumes:
    - ./data/qdrant_server:/qdrant/storage
  environment:
    - QDRANT__SERVICE__GRPC_PORT=6334
  restart: unless-stopped
  profiles:
    - qdrant
```

Para expor na LAN (requer precaução):

```yaml
ports:
  - "0.0.0.0:6333:6333" # ⚠ acessível na rede local
```

> **Segurança**: O Qdrant não tem autenticação por defeito.
> Se expor na LAN, configura `QDRANT__SERVICE__API_KEY` e usa
> `qdrant_api_key` no `rag.user.toml`.
