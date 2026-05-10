---
type: shell-knowledge
area: linux
system: zsh
source: ~/.zsh_custom.d/45-data-engineering.zsh
created_by: github-copilot-cli
tags:
  - linux
  - zsh
  - shell
  - data-engineering
  - duckdb
  - parquet
  - csv
  - docker
---

# 🦆 Shell — Data Engineering

## Sobre

Módulo `45-data-engineering.zsh` — helpers para trabalho com DuckDB, Parquet, CSV e Docker no contexto de data engineering local.

---

## Aliases

| Alias | Comando | Descrição |
|-------|---------|-----------|
| `duck` | `duckdb` | Abrir DuckDB (modo ficheiro ou `:memory:`) |
| `duckm` | `duckdb :memory:` | Abrir DuckDB em memória |

---

## Funções — DuckDB / Parquet

### `duckpq`
**Objetivo:** Preview de ficheiro Parquet (primeiras N linhas)

```zsh
duckpq <ficheiro.parquet> [limite]
duckpq data.parquet
duckpq data.parquet 50
```

Default: 100 linhas.

---

### `pqschema`
**Objetivo:** Mostrar schema (tipos de colunas) de um ficheiro Parquet

```zsh
pqschema <ficheiro.parquet>
pqschema data.parquet
```

Usa `DESCRIBE SELECT * FROM read_parquet(...)`.

---

### `pqcount`
**Objetivo:** Contar linhas de um ficheiro Parquet

```zsh
pqcount <ficheiro.parquet>
pqcount data.parquet
```

---

### `pqsql`
**Objetivo:** Query SQL ad-hoc num ficheiro Parquet

```zsh
pqsql <ficheiro.parquet> <query_sql>
pqsql data.parquet "SELECT count(*) FROM data WHERE status = 'active'"
pqsql data.parquet "SELECT * FROM data ORDER BY created_at DESC LIMIT 10"
```

> A query referencia o ficheiro como tabela `data` (view criada automaticamente).

---

### `csv2pq`
**Objetivo:** Converter CSV para Parquet

```zsh
csv2pq <ficheiro.csv> [output.parquet]
csv2pq data.csv
csv2pq data.csv resultado.parquet
```

Se não for especificado output, usa o mesmo nome com extensão `.parquet`.

---

### `pq2csv`
**Objetivo:** Converter Parquet para CSV

```zsh
pq2csv <ficheiro.parquet> [output.csv]
pq2csv data.parquet
pq2csv data.parquet resultado.csv
```

---

## Funções — Docker

### `docker_clean`
**Objetivo:** Limpar Docker (containers parados, imagens dangling, volumes órfãos)

```zsh
docker_clean
```

Pede confirmação antes de executar `docker system prune -af --volumes`.

---

## Cheat Sheet

| Comando | Descrição |
|---------|-----------|
| `duck` | Abrir DuckDB |
| `duckm` | DuckDB em memória |
| `duckpq data.parquet` | Preview de Parquet (100 linhas) |
| `duckpq data.parquet 50` | Preview com limite personalizado |
| `pqschema data.parquet` | Schema / tipos de colunas |
| `pqcount data.parquet` | Contar linhas |
| `pqsql data.parquet "SELECT ..."` | Query SQL ad-hoc |
| `csv2pq data.csv` | CSV → Parquet |
| `pq2csv data.parquet` | Parquet → CSV |
| `docker_clean` | Limpar Docker (com confirmação) |

---

## Dependências

| Ferramenta | Função | Obrigatória |
|------------|--------|-------------|
| `duckdb` | Todas as funções pq* e csv/parquet | Sim |
| `docker` | `docker_clean` | Não |

---

## Notas

- Todas as funções verificam a existência do ficheiro antes de executar
- `duckdb` pode ser instalado via `mise` ou download direto
- Para ficheiros grandes, usar `pqsql` com `LIMIT` para não sobrecarregar memória
