"""Chunking inteligente de notas Markdown para RAG.

Divide notas por headers (H1/H2/H3) com fallback por tamanho.
Preserva metadata: source_path, title, section_header, display_text.
Gera hash SHA256 por chunk para controlo incremental.
Prefixo contextual no texto para embedding (melhora relevância semântica).
"""

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

from obsidian_rag.config import settings


@dataclass
class Chunk:
    id: str
    text: str  # Texto com prefixo contextual (para embedding)
    metadata: dict = field(default_factory=dict)


HEADER_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)
FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)
LINK_ONLY_RE = re.compile(r"^[\s\-\*]*\[\[.*?\]\][\s\-\*]*$")


def _compute_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter (---...---) do início do texto."""
    return FRONTMATTER_RE.sub("", text).strip()


def _is_navigation_content(text: str) -> bool:
    """True if chunk is mostly wikilinks/navigation (low value for RAG)."""
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        return True
    link_lines = sum(1 for ln in lines if LINK_ONLY_RE.match(ln))
    return link_lines / len(lines) > 0.7


def _split_by_headers(text: str) -> list[tuple[str, str]]:
    """Divide texto em secções baseadas em headers Markdown."""
    matches = list(HEADER_RE.finditer(text))
    if not matches:
        return [("", text)]

    sections = []
    if matches[0].start() > 0:
        preamble = text[: matches[0].start()].strip()
        if preamble:
            sections.append(("", preamble))

    for i, match in enumerate(matches):
        header_title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        if body:
            sections.append((header_title, body))

    return sections


def _split_long_text(text: str, max_chars: int, overlap: int) -> list[str]:
    """Divide texto longo em chunks com overlap."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars
        if end < len(text):
            cut = text.rfind("\n\n", start, end)
            if cut == -1 or cut <= start:
                cut = text.rfind(". ", start, end)
            if cut > start:
                end = cut + 1
        chunks.append(text[start:end].strip())
        start = end - overlap if end < len(text) else end

    return [c for c in chunks if c]


def chunk_note(path: Path, source_dir: Path | None = None) -> list[Chunk]:
    """Divide uma nota .md em chunks semânticos com prefixo contextual."""
    if source_dir is None:
        source_dir = settings.paths.source_dir

    cfg = settings.chunking

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    text = text.replace("\r\n", "\n").strip()
    if not text:
        return []

    if cfg.strip_frontmatter:
        text = _strip_frontmatter(text)
        if not text:
            return []

    rel_path = str(path.relative_to(source_dir))
    title_match = re.match(r"^#\s+(.+)$", text, re.MULTILINE)
    note_title = title_match.group(1).strip() if title_match else path.stem

    sections = _split_by_headers(text)
    chunks = []

    for header, section_text in sections:
        if _is_navigation_content(section_text):
            continue

        sub_chunks = _split_long_text(section_text, cfg.max_chars, cfg.overlap_chars)
        for i, chunk_text in enumerate(sub_chunks):
            if len(chunk_text.strip()) < cfg.min_chars:
                continue

            # Build contextual prefix for better embedding
            if cfg.contextual_prefix:
                prefix_parts = [f"Nota: {note_title}"]
                if header:
                    prefix_parts.append(f"Secção: {header}")
                prefix = " | ".join(prefix_parts)
                embedding_text = f"{prefix}\n{chunk_text}"
            else:
                embedding_text = chunk_text

            chunk_id = _compute_hash(f"{rel_path}:{header}:{i}:{chunk_text}")
            metadata = {
                "source_path": rel_path,
                "note_title": note_title,
                "section_header": header,
                "chunk_index": i,
                "display_text": chunk_text,
            }
            chunks.append(Chunk(id=chunk_id, text=embedding_text, metadata=metadata))

    return chunks


# Directories to skip when scanning notes
_EXCLUDED_DIRS = frozenset({
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    ".cache", "dist", "build", ".obsidian",
})


def chunk_all_notes(source_dir: Path | None = None) -> list[Chunk]:
    """Processa todas as notas .md na source_dir."""
    if source_dir is None:
        source_dir = settings.paths.source_dir

    if not source_dir.exists():
        raise SystemExit(f"Pasta source não existe: {source_dir}")

    files = sorted(
        f for f in source_dir.rglob("*.md")
        if not any(part in _EXCLUDED_DIRS for part in f.relative_to(source_dir).parts)
    )
    if not files:
        raise SystemExit("Sem ficheiros .md na pasta source.")

    all_chunks = []
    for path in files:
        all_chunks.extend(chunk_note(path, source_dir))

    return all_chunks
