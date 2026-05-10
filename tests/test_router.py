"""Tests for obsidian_rag.retrieval.router — keyword heuristic only."""

from __future__ import annotations

from obsidian_rag.retrieval.router import ContextMode, _heuristic_route


class TestHeuristicRoute:
    # --- Local signals ---

    def test_local_reference_returns_rag_only(self):
        decision = _heuristic_route("Quais são as minhas notas sobre Python?")
        assert decision.mode == ContextMode.RAG_ONLY
        assert decision.method == "heuristic"

    def test_explicit_vault_reference(self):
        decision = _heuristic_route("Pesquisa no meu vault por machine learning")
        assert decision.mode == ContextMode.RAG_ONLY

    def test_code_reference(self):
        decision = _heuristic_route("Mostra o código do ficheiro config.py")
        assert decision.mode == ContextMode.RAG_ONLY

    # --- Graph signals ---

    def test_graph_with_local_context(self):
        decision = _heuristic_route("Quais módulos do meu projeto dependem do config?")
        assert decision.mode == ContextMode.RAG_AND_GRAPH

    def test_graph_with_project_hint(self):
        decision = _heuristic_route("Qual é a arquitectura do meu repositório?")
        assert decision.mode == ContextMode.RAG_AND_GRAPH

    def test_pure_graph_without_local(self):
        decision = _heuristic_route("O que é um grafo de dependências?")
        assert decision.mode == ContextMode.NO_CONTEXT

    # --- No signals ---

    def test_general_question(self):
        decision = _heuristic_route("What is the capital of France?")
        assert decision.mode == ContextMode.NO_CONTEXT

    def test_generic_coding_question(self):
        decision = _heuristic_route("How do I sort a list in Python?")
        assert decision.mode == ContextMode.NO_CONTEXT

    # --- Confidence ---

    def test_local_confidence(self):
        decision = _heuristic_route("Mostra as minhas notas")
        assert decision.confidence >= 0.6

    def test_no_context_confidence(self):
        decision = _heuristic_route("Explain quantum computing")
        assert decision.confidence >= 0.5

    # --- Edge cases ---

    def test_empty_query(self):
        decision = _heuristic_route("")
        assert decision.mode == ContextMode.NO_CONTEXT

    def test_graph_pattern_match(self):
        decision = _heuristic_route("como funciona o meu pipeline de sync?")
        assert decision.mode == ContextMode.RAG_AND_GRAPH

    def test_english_local_signals(self):
        decision = _heuristic_route("Search my notes for RAG")
        assert decision.mode == ContextMode.RAG_ONLY

    def test_call_chain_pattern(self):
        decision = _heuristic_route("what calls the build_rag_context in my project?")
        assert decision.mode == ContextMode.RAG_AND_GRAPH
