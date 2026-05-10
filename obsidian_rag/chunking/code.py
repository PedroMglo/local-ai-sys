"""Chunking de código Python para RAG — usa ast.parse() (stdlib, sem dependências).

Estratégia:
  - Um chunk por função/método (decorators + docstring + corpo)
  - Um chunk por classe (docstring + assinaturas dos métodos)
  - Um chunk por módulo (imports + constants + module docstring)

Ficheiros não-Python no repo (.md, .yaml, .toml, .sh) são enviados para o
chunker Markdown existente com source_type="repo_doc".

Metadata compatível com o Chunk dataclass existente — todos os campos standard
estão presentes para que o retrieval e a API funcionem sem alterações.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

from obsidian_rag.chunking.markdown import Chunk, chunk_note

# Extensões tratadas como "repo doc" (via chunker Markdown)
_REPO_DOC_EXTENSIONS = {".md", ".mdx", ".txt", ".rst", ".yaml", ".yml", ".toml", ".sh", ".env"}
# Extensões de código Python
_PYTHON_EXTENSION = ".py"


def _compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _source_lines(source: str, node: ast.AST) -> str:
    """Extrai linhas de código para um nó AST."""
    lines = source.splitlines()
    start = getattr(node, "lineno", 1) - 1
    end = getattr(node, "end_lineno", getattr(node, "lineno", 1))
    return "\n".join(lines[start:end])


def _get_decorator_start(source: str, node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) -> int:
    """Linha de início real (incluindo decorators)."""
    if node.decorator_list:
        return node.decorator_list[0].lineno - 1
    return node.lineno - 1


def _build_chunk(
    text: str,
    rel_path: str,
    repo_name: str,
    note_title: str,
    section_header: str,
    symbol_type: str,
    chunk_index: int,
    contextual_prefix: bool,
) -> Chunk | None:
    display = text.strip()
    if not display:
        return None

    if contextual_prefix:
        prefix = f"Repo: {repo_name} | Ficheiro: {rel_path} | {symbol_type.capitalize()}: {section_header}"
        embedding_text = f"{prefix}\n{display}"
    else:
        embedding_text = display

    chunk_id = _compute_hash(f"{rel_path}:{section_header}:{chunk_index}:{display}")
    metadata = {
        "source_path": rel_path,
        "source_type": "code",
        "repo_name": repo_name,
        "note_title": note_title,          # compat com retrieval existente
        "section_header": section_header,
        "symbol_type": symbol_type,
        "chunk_index": chunk_index,
        "display_text": display,
    }
    return Chunk(id=chunk_id, text=embedding_text, metadata=metadata)


def _chunk_python_source(
    source: str,
    rel_path: str,
    repo_name: str,
    cfg,
) -> list[Chunk]:
    """Parse um ficheiro Python e produz chunks semânticos por função/classe/módulo."""
    note_title = Path(rel_path).name
    chunks: list[Chunk] = []
    chunk_index = 0

    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError:
        # Fallback: tratar como texto plano se o parse falhar
        return _chunk_text_fallback(source, rel_path, repo_name, note_title, cfg)

    lines = source.splitlines()

    # Recolher top-level nodes que interessam (funções, classes, e resto para módulo-level)
    top_level_nodes = list(ast.iter_child_nodes(tree))

    # 1. Chunk de módulo — docstring + imports + constants (tudo excepto funções/classes)
    module_lines: list[str] = []
    for node in top_level_nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        start = getattr(node, "lineno", 1) - 1
        end = getattr(node, "end_lineno", getattr(node, "lineno", 1))
        module_lines.extend(lines[start:end])

    module_text = "\n".join(module_lines).strip()
    if module_text and len(module_text) >= cfg.min_chars:
        c = _build_chunk(
            text=module_text,
            rel_path=rel_path,
            repo_name=repo_name,
            note_title=note_title,
            section_header=f"{note_title} (module-level)",
            symbol_type="module",
            chunk_index=chunk_index,
            contextual_prefix=cfg.contextual_prefix,
        )
        if c:
            chunks.append(c)
            chunk_index += 1

    # 2. Chunks por função e classe top-level
    for node in top_level_nodes:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_start = _get_decorator_start(source, node)
            func_end = getattr(node, "end_lineno", node.lineno)
            text = "\n".join(lines[func_start:func_end])
            header = node.name

            # Split se muito grande
            sub_chunks = _split_if_long(text, cfg.max_chars, cfg.overlap_chars)
            for i, sub in enumerate(sub_chunks):
                if len(sub.strip()) < cfg.min_chars:
                    continue
                label = header if len(sub_chunks) == 1 else f"{header} (parte {i+1})"
                c = _build_chunk(
                    text=sub,
                    rel_path=rel_path,
                    repo_name=repo_name,
                    note_title=note_title,
                    section_header=label,
                    symbol_type="function",
                    chunk_index=chunk_index,
                    contextual_prefix=cfg.contextual_prefix,
                )
                if c:
                    chunks.append(c)
                    chunk_index += 1

        elif isinstance(node, ast.ClassDef):
            class_start = _get_decorator_start(source, node)
            class_end = getattr(node, "end_lineno", node.lineno)
            class_text_lines = lines[class_start:class_end]

            # Chunk da classe: cabeçalho + docstring + assinaturas de métodos
            class_summary_parts = []
            # Linhas da class def até ao fim da docstring
            in_body = False
            for child in ast.iter_child_nodes(node):
                if isinstance(child, ast.Expr) and isinstance(child.value, ast.Constant):
                    # docstring da classe
                    start = child.lineno - 1 - class_start
                    end = getattr(child, "end_lineno", child.lineno) - class_start
                    class_summary_parts.extend(class_text_lines[:end + 1])
                    in_body = True
                    break
            if not in_body:
                class_summary_parts.extend(class_text_lines[:3])  # só cabeçalho

            # Adicionar assinaturas dos métodos
            for method in ast.iter_child_nodes(node):
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    sig_start = _get_decorator_start(source, method)
                    # Só a linha de def (sem corpo)
                    sig_line = lines[sig_start : method.lineno]
                    class_summary_parts.extend(sig_line)
                    class_summary_parts.append("    ...")

            class_summary = "\n".join(class_summary_parts).strip()
            if len(class_summary) >= cfg.min_chars:
                c = _build_chunk(
                    text=class_summary,
                    rel_path=rel_path,
                    repo_name=repo_name,
                    note_title=note_title,
                    section_header=f"class {node.name}",
                    symbol_type="class",
                    chunk_index=chunk_index,
                    contextual_prefix=cfg.contextual_prefix,
                )
                if c:
                    chunks.append(c)
                    chunk_index += 1

            # Chunks individuais por método
            for method in ast.iter_child_nodes(node):
                if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    m_start = _get_decorator_start(source, method)
                    m_end = getattr(method, "end_lineno", method.lineno)
                    method_text = "\n".join(lines[m_start:m_end])
                    sub_chunks = _split_if_long(method_text, cfg.max_chars, cfg.overlap_chars)
                    for i, sub in enumerate(sub_chunks):
                        if len(sub.strip()) < cfg.min_chars:
                            continue
                        label = f"{node.name}.{method.name}"
                        if len(sub_chunks) > 1:
                            label += f" (parte {i+1})"
                        c = _build_chunk(
                            text=sub,
                            rel_path=rel_path,
                            repo_name=repo_name,
                            note_title=note_title,
                            section_header=label,
                            symbol_type="method",
                            chunk_index=chunk_index,
                            contextual_prefix=cfg.contextual_prefix,
                        )
                        if c:
                            chunks.append(c)
                            chunk_index += 1

    return chunks


def _split_if_long(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    """Divide texto longo preservando linhas inteiras."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    lines = text.splitlines(keepends=True)
    current: list[str] = []
    current_len = 0
    for line in lines:
        if current_len + len(line) > max_chars and current:
            chunks.append("".join(current).strip())
            # overlap: manter últimas linhas
            overlap_chars_left = overlap_chars
            overlap_lines: list[str] = []
            for ln in reversed(current):
                if overlap_chars_left <= 0:
                    break
                overlap_lines.insert(0, ln)
                overlap_chars_left -= len(ln)
            current = overlap_lines
            current_len = sum(len(ln) for ln in current)
        current.append(line)
        current_len += len(line)
    if current:
        chunks.append("".join(current).strip())
    return [c for c in chunks if c]


def _chunk_text_fallback(
    text: str,
    rel_path: str,
    repo_name: str,
    note_title: str,
    cfg,
) -> list[Chunk]:
    """Fallback: chunking por tamanho quando ast.parse() falha."""
    chunks = []
    parts = _split_if_long(text, cfg.max_chars, cfg.overlap_chars)
    for i, part in enumerate(parts):
        if len(part.strip()) < cfg.min_chars:
            continue
        c = _build_chunk(
            text=part,
            rel_path=rel_path,
            repo_name=repo_name,
            note_title=note_title,
            section_header=note_title,
            symbol_type="text",
            chunk_index=i,
            contextual_prefix=cfg.contextual_prefix,
        )
        if c:
            chunks.append(c)
    return chunks


def chunk_file(path: Path, repo_dir: Path, cfg) -> list[Chunk]:
    """Processa um único ficheiro do repo → lista de Chunks.

    - .py  → chunking AST (funções, classes, módulo)
    - resto → chunk_note() do chunker Markdown com source_type="repo_doc"
    """
    repo_name = repo_dir.name
    suffix = path.suffix.lower()

    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    if not source.strip():
        return []

    if suffix == _PYTHON_EXTENSION:
        rel_path = str(path.relative_to(repo_dir))
        return _chunk_python_source(source, rel_path, repo_name, cfg)

    if suffix in _REPO_DOC_EXTENSIONS:
        # Reutiliza o chunker Markdown com metadata enriquecida
        md_chunks = chunk_note(path, source_dir=repo_dir)
        # Enriquecer metadata com info do repo
        enriched = []
        for c in md_chunks:
            c.metadata["source_type"] = "repo_doc"
            c.metadata["repo_name"] = repo_name
            enriched.append(c)
        return enriched

    return []


# Ficheiros/pastas a ignorar no repo
_IGNORE_DIRS = {
    ".git", ".venv", "venv", "__pycache__", ".mypy_cache", ".pytest_cache",
    ".ruff_cache", "node_modules", "dist", "build", ".eggs", "*.egg-info",
    "logs", "models", "output", "rag", "input", "graphify-out", "data",
}

_IGNORE_FILES = {
    ".gitignore", ".env", ".env.example", "Makefile", "compose.yaml",
    "docker-compose.yaml", "docker-compose.yml",
}


def _should_skip(path: Path, repo_dir: Path) -> bool:
    """True se o ficheiro deve ser ignorado."""
    rel = path.relative_to(repo_dir)
    parts = rel.parts
    # Ignorar dirs especiais
    for part in parts[:-1]:  # só dirs (não o filename)
        if part in _IGNORE_DIRS or part.endswith(".egg-info"):
            return True
    # Ignorar ficheiros específicos
    if path.name in _IGNORE_FILES:
        return True
    # Ignorar binários, imagens, etc.
    if path.suffix.lower() in {
        ".pyc", ".pyd", ".so", ".dylib", ".dll",
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg",
        ".zip", ".tar", ".gz", ".pkl", ".npy", ".npz",
        ".faiss", ".index", ".sqlite", ".db",
    }:
        return True
    return False


def chunk_repo(repo_dir: Path | str, cfg=None) -> list[Chunk]:
    """Processa todos os ficheiros relevantes de um repo git.

    Retorna lista de Chunks compatível com sync_to_chroma().
    """
    from obsidian_rag.config import settings as _settings
    if cfg is None:
        cfg = _settings.repos.chunking

    repo_dir = Path(repo_dir).expanduser().resolve()
    if not repo_dir.exists():
        raise FileNotFoundError(f"Repo não encontrado: {repo_dir}")

    # Extensões a processar
    valid_extensions = {_PYTHON_EXTENSION} | _REPO_DOC_EXTENSIONS
    all_files = sorted(repo_dir.rglob("*"))

    all_chunks: list[Chunk] = []
    for path in all_files:
        if not path.is_file():
            continue
        if _should_skip(path, repo_dir):
            continue
        if path.suffix.lower() not in valid_extensions:
            continue
        all_chunks.extend(chunk_file(path, repo_dir, cfg))

    return all_chunks
