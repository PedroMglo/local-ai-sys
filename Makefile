# Obsidian RAG — Makefile
# Atalhos para os comandos mais comuns

.PHONY: install init up serve sync graph doctor test backup clean

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
