"""Tests for obsidian_rag.chunking.treesitter — tree-sitter multi-language chunking."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

# Skip entire module if tree-sitter is not installed
ts = pytest.importorskip("tree_sitter", reason="tree-sitter not installed")

from obsidian_rag.chunking.treesitter import (
    chunk_treesitter,
    is_available,
    supported_extensions,
    _extract_name,
    _get_parser,
    _node_text,
)


@dataclass
class _FakeCfg:
    """Minimal config for chunking tests."""
    max_chars: int = 2000
    overlap_chars: int = 200
    min_chars: int = 50
    contextual_prefix: bool = True


# ---------------------------------------------------------------------------
# Availability & registry
# ---------------------------------------------------------------------------


class TestAvailability:
    def test_is_available(self):
        assert is_available() is True

    def test_supported_extensions(self):
        exts = supported_extensions()
        assert ".js" in exts
        assert ".ts" in exts
        assert ".go" in exts
        assert ".rs" in exts
        assert ".java" in exts
        assert ".py" not in exts  # Python uses ast, not tree-sitter


# ---------------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------------


class TestJavaScript:
    def test_function_chunk(self):
        src = (
            "function greet(name) {\n"
            "    console.log('Hello ' + name);\n"
            "    return name;\n"
            "}\n"
        )
        chunks = chunk_treesitter(src, "app.js", "repo", "javascript", _FakeCfg())
        assert len(chunks) >= 1
        fn = [c for c in chunks if c.metadata["symbol_type"] == "function"]
        assert len(fn) == 1
        assert fn[0].metadata["section_header"] == "greet"

    def test_class_and_methods(self):
        src = (
            "class Calculator {\n"
            "    constructor(value) {\n"
            "        this.value = value;\n"
            "    }\n"
            "    add(x) {\n"
            "        this.value += x;\n"
            "        return this;\n"
            "    }\n"
            "    subtract(x) {\n"
            "        this.value -= x;\n"
            "        return this;\n"
            "    }\n"
            "}\n"
        )
        chunks = chunk_treesitter(src, "calc.js", "repo", "javascript", _FakeCfg())
        types = {c.metadata["symbol_type"] for c in chunks}
        assert "class" in types
        assert "method" in types
        # Should have class summary + individual methods
        methods = [c for c in chunks if c.metadata["symbol_type"] == "method"]
        assert len(methods) >= 2

    def test_metadata_fields(self):
        src = (
            "function process(data) {\n"
            "    const result = data.map(x => x * 2);\n"
            "    return result;\n"
            "}\n"
        )
        chunks = chunk_treesitter(src, "utils.js", "my-repo", "javascript", _FakeCfg())
        assert len(chunks) >= 1
        c = chunks[0]
        assert c.metadata["source_path"] == "utils.js"
        assert c.metadata["repo_name"] == "my-repo"
        assert c.metadata["source_type"] == "code"
        assert c.metadata["note_title"] == "utils.js"
        assert c.id  # has a hash ID

    def test_contextual_prefix(self):
        src = (
            "function hello(name) {\n"
            "    return 'Hello ' + name;\n"
            "}\n"
        )
        cfg = _FakeCfg(contextual_prefix=True)
        chunks = chunk_treesitter(src, "app.js", "repo", "javascript", cfg)
        assert len(chunks) >= 1
        assert "Repo: repo" in chunks[0].text
        assert "Ficheiro: app.js" in chunks[0].text

    def test_no_contextual_prefix(self):
        src = (
            "function hello(name) {\n"
            "    return 'Hello ' + name;\n"
            "}\n"
        )
        cfg = _FakeCfg(contextual_prefix=False)
        chunks = chunk_treesitter(src, "app.js", "repo", "javascript", cfg)
        assert len(chunks) >= 1
        assert "Repo:" not in chunks[0].text


# ---------------------------------------------------------------------------
# TypeScript
# ---------------------------------------------------------------------------


class TestTypeScript:
    def test_interface(self):
        src = (
            "interface User {\n"
            "    name: string;\n"
            "    age: number;\n"
            "    email: string;\n"
            "}\n"
        )
        chunks = chunk_treesitter(src, "types.ts", "repo", "typescript", _FakeCfg())
        assert len(chunks) >= 1
        iface = [c for c in chunks if c.metadata["symbol_type"] == "interface"]
        assert len(iface) == 1
        assert iface[0].metadata["section_header"] == "User"

    def test_function_and_export(self):
        src = (
            "function createUser(name: string, age: number): User {\n"
            "    return { name, age, email: '' };\n"
            "}\n"
            "\n"
            "export class UserService {\n"
            "    private users: User[] = [];\n"
            "    add(user: User): void {\n"
            "        this.users.push(user);\n"
            "    }\n"
            "}\n"
        )
        chunks = chunk_treesitter(src, "user.ts", "repo", "typescript", _FakeCfg())
        assert len(chunks) >= 2
        types = {c.metadata["symbol_type"] for c in chunks}
        assert "function" in types


# ---------------------------------------------------------------------------
# Java
# ---------------------------------------------------------------------------


class TestJava:
    def test_class_and_methods(self):
        src = (
            "public class Calculator {\n"
            "    private int value;\n"
            "\n"
            "    public Calculator(int initial) {\n"
            "        this.value = initial;\n"
            "    }\n"
            "\n"
            "    public int add(int x) {\n"
            "        this.value += x;\n"
            "        return this.value;\n"
            "    }\n"
            "\n"
            "    public int subtract(int x) {\n"
            "        this.value -= x;\n"
            "        return this.value;\n"
            "    }\n"
            "}\n"
        )
        chunks = chunk_treesitter(src, "Calculator.java", "repo", "java", _FakeCfg())
        types = {c.metadata["symbol_type"] for c in chunks}
        assert "class" in types
        methods = [c for c in chunks if c.metadata["symbol_type"] in ("method", "constructor")]
        assert len(methods) >= 2


# ---------------------------------------------------------------------------
# Go
# ---------------------------------------------------------------------------


class TestGo:
    def test_function_and_type(self):
        src = (
            'package main\n'
            '\n'
            'import "fmt"\n'
            '\n'
            'func hello(name string) string {\n'
            '    return fmt.Sprintf("Hello %s", name)\n'
            '}\n'
            '\n'
            'type Server struct {\n'
            '    Port int\n'
            '    Host string\n'
            '}\n'
        )
        chunks = chunk_treesitter(src, "main.go", "repo", "go", _FakeCfg())
        types = {c.metadata["symbol_type"] for c in chunks}
        assert "function" in types


# ---------------------------------------------------------------------------
# Rust
# ---------------------------------------------------------------------------


class TestRust:
    def test_impl_and_methods(self):
        src = (
            "pub struct Point {\n"
            "    pub x: f64,\n"
            "    pub y: f64,\n"
            "}\n"
            "\n"
            "impl Point {\n"
            "    pub fn new(x: f64, y: f64) -> Self {\n"
            "        Point { x, y }\n"
            "    }\n"
            "\n"
            "    pub fn distance(&self, other: &Point) -> f64 {\n"
            "        let dx = self.x - other.x;\n"
            "        let dy = self.y - other.y;\n"
            "        (dx * dx + dy * dy).sqrt()\n"
            "    }\n"
            "}\n"
        )
        chunks = chunk_treesitter(src, "point.rs", "repo", "rust", _FakeCfg())
        assert len(chunks) >= 1
        # impl should exist
        impl_chunks = [c for c in chunks if c.metadata["symbol_type"] == "impl"]
        assert len(impl_chunks) >= 1
        assert impl_chunks[0].metadata["section_header"] == "Point"


# ---------------------------------------------------------------------------
# C
# ---------------------------------------------------------------------------


class TestC:
    def test_function(self):
        src = (
            '#include <stdio.h>\n'
            '\n'
            'int factorial(int n) {\n'
            '    if (n <= 1) return 1;\n'
            '    return n * factorial(n - 1);\n'
            '}\n'
            '\n'
            'int main() {\n'
            '    printf("%d\\n", factorial(5));\n'
            '    return 0;\n'
            '}\n'
        )
        chunks = chunk_treesitter(src, "math.c", "repo", "c", _FakeCfg())
        fn_chunks = [c for c in chunks if c.metadata["symbol_type"] == "function"]
        assert len(fn_chunks) >= 1


# ---------------------------------------------------------------------------
# Integration with code.py dispatch
# ---------------------------------------------------------------------------


class TestCodeDispatch:
    """Test that code.py correctly dispatches to tree-sitter for non-Python files."""

    def test_js_file_dispatched(self, tmp_path: Path):
        from obsidian_rag.chunking.code import chunk_file

        repo = tmp_path / "repo"
        repo.mkdir()
        js = repo / "app.js"
        js.write_text(
            "function greet(name) {\n"
            "    console.log('Hello ' + name);\n"
            "    return name;\n"
            "}\n"
        )
        cfg = _FakeCfg()
        chunks = chunk_file(js, repo, cfg)
        assert len(chunks) >= 1
        assert chunks[0].metadata["symbol_type"] == "function"
        assert chunks[0].metadata["section_header"] == "greet"

    def test_ts_file_dispatched(self, tmp_path: Path):
        from obsidian_rag.chunking.code import chunk_file

        repo = tmp_path / "repo"
        repo.mkdir()
        ts = repo / "types.ts"
        ts.write_text(
            "interface Config {\n"
            "    host: string;\n"
            "    port: number;\n"
            "    debug: boolean;\n"
            "}\n"
        )
        cfg = _FakeCfg()
        chunks = chunk_file(ts, repo, cfg)
        assert len(chunks) >= 1
        assert chunks[0].metadata["symbol_type"] == "interface"

    def test_go_file_dispatched(self, tmp_path: Path):
        from obsidian_rag.chunking.code import chunk_file

        repo = tmp_path / "repo"
        repo.mkdir()
        go = repo / "main.go"
        go.write_text(
            'package main\n'
            '\n'
            'import "fmt"\n'
            '\n'
            'func greet(name string) string {\n'
            '    return fmt.Sprintf("Hello %s", name)\n'
            '}\n'
        )
        cfg = _FakeCfg()
        chunks = chunk_file(go, repo, cfg)
        assert len(chunks) >= 1
        assert chunks[0].metadata["symbol_type"] == "function"

    def test_iter_repo_files_includes_ts_js(self, tmp_path: Path):
        from obsidian_rag.chunking.code import iter_repo_files

        repo = tmp_path / "repo"
        repo.mkdir()
        (repo / "app.js").write_text("var x = 1;")
        (repo / "types.ts").write_text("type X = string;")
        (repo / "main.go").write_text("package main")
        (repo / "readme.md").write_text("# Hello")
        (repo / "binary.png").write_bytes(b"\x89PNG")

        files = list(iter_repo_files(repo))
        names = {f.name for f in files}
        assert "app.js" in names
        assert "types.ts" in names
        assert "main.go" in names
        assert "readme.md" in names
        assert "binary.png" not in names


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_file(self):
        chunks = chunk_treesitter("", "empty.js", "repo", "javascript", _FakeCfg())
        assert chunks == []

    def test_syntax_error_fallback(self):
        """Files with syntax errors should still produce chunks via text fallback."""
        src = "function { broken syntax (" * 10  # deliberately bad
        chunks = chunk_treesitter(src, "bad.js", "repo", "javascript", _FakeCfg())
        # tree-sitter is error-tolerant, so it may still produce partial chunks
        # or fall back to text — either way, no exception
        assert isinstance(chunks, list)

    def test_min_chars_filter(self):
        """Chunks below min_chars should be filtered."""
        src = "function f() { return 1; }\n"  # very short
        cfg = _FakeCfg(min_chars=100)
        chunks = chunk_treesitter(src, "tiny.js", "repo", "javascript", cfg)
        assert len(chunks) == 0

    def test_long_function_split(self):
        """Long functions should be split into multiple chunks."""
        lines = ["function big() {"]
        for i in range(100):
            lines.append(f"    console.log('line {i}: ' + 'x'.repeat(30));")
        lines.append("}")
        src = "\n".join(lines)
        cfg = _FakeCfg(max_chars=500)
        chunks = chunk_treesitter(src, "big.js", "repo", "javascript", cfg)
        assert len(chunks) > 1
        # Should have (part N) in section_header
        multi = [c for c in chunks if "part" in c.metadata["section_header"]]
        assert len(multi) > 0

    def test_module_level_code(self):
        """Top-level statements that aren't definitions should be collected."""
        src = (
            'import express from "express";\n'
            'import cors from "cors";\n'
            'import helmet from "helmet";\n'
            '\n'
            'const app = express();\n'
            'app.use(cors());\n'
            'app.use(helmet());\n'
        )
        cfg = _FakeCfg(min_chars=30)
        chunks = chunk_treesitter(src, "server.js", "repo", "javascript", cfg)
        # Should have at least a module-level chunk or variable chunks
        assert len(chunks) >= 1
