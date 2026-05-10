# --- Build stage ---
FROM python:3.11-slim AS builder

RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml requirements.txt ./
COPY obsidian_rag/ obsidian_rag/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir '.[qdrant]'

# --- Runtime stage ---
FROM python:3.11-slim

# Patch OS-level vulnerabilities and create non-root user
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 rag \
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

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

USER rag

CMD ["rag", "serve"]
