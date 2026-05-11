# Obsidian RAG — Makefile
# Atalhos para os comandos mais comuns

.PHONY: install init up serve sync graph doctor test backup clean \
        lint typecheck test-cov ci docker-build docker-check qdrant qdrant-down

VENV := .venv/bin

install:
	./install.sh

init:
	$(VENV)/rag init

up:
	$(VENV)/rag up

serve:
	$(VENV)/rag serve

sync:
	$(VENV)/rag sync --all

graph:
	$(VENV)/rag graph build

doctor:
	$(VENV)/rag doctor

test:
	$(VENV)/pytest

backup:
	$(VENV)/rag backup

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

# ── Targets CI (usam Python do PATH — compatíveis com CI e venv activado) ──
lint:
	ruff check obsidian_rag/

typecheck:
	mypy obsidian_rag/

test-cov:
	pytest tests/ -q --cov=obsidian_rag --cov-report=term-missing --cov-fail-under=30

ci: lint typecheck test-cov
	@echo "CI local concluído."

docker-build:
	docker build -t obsidian-rag .

docker-check:
	docker compose config

# ── Qdrant server mode ────────────────────────────────────────────────────
qdrant:
	docker compose --profile qdrant up -d
	@echo "Qdrant server a correr em http://localhost:6333"
	@echo "Healthcheck: curl -s http://localhost:6333/healthz"

qdrant-down:
	docker compose --profile qdrant down
