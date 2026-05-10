# --- Build stage ---
FROM python:3.11-slim AS builder

WORKDIR /app
COPY pyproject.toml requirements.txt ./
COPY obsidian_rag/ obsidian_rag/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir .

# --- Runtime stage ---
FROM python:3.11-slim

# Utilizador não-root para segurança
RUN groupadd --gid 1000 rag \
    && useradd --uid 1000 --gid rag --create-home rag

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
COPY obsidian_rag/ obsidian_rag/
COPY rag.toml .

# ChromaDB data volume — writable pelo user rag
RUN mkdir -p /app/data && chown -R rag:rag /app
VOLUME ["/app/data"]

EXPOSE 8000

ENV RAG_API_HOST=0.0.0.0
ENV RAG_API_PORT=8000

USER rag

CMD ["rag", "serve"]
