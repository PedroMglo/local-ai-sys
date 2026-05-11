"""Wrapper para execução do graphify CLI.

Invoca `graphify extract` via subprocess para cada repo configurado.
O graphify processa:
  - Código Python via AST (tree-sitter) — local, sem LLM
  - Markdown/docs via Ollama — local, sem API key externa

Os grafos ficam persistidos em:
  {settings.graphify.output_dir}/{repo_name}/graphify-out/graph.json

Incremental mode:
  Before spawning a subprocess, the builder checks graphify's own
  manifest.json (file hashes) against current files.  If nothing
  changed the subprocess is skipped entirely.  When only code files
  changed (no .md/.txt), ``graphify update`` (AST-only, no LLM) is
  used instead of the full ``graphify extract``.
"""

from __future__ import annotations

import gc
import hashlib
import json
import logging
import os
import subprocess
from pathlib import Path

from obsidian_rag.config import settings

log = logging.getLogger(__name__)

# File extensions that require LLM semantic extraction (vs AST-only)
_DOC_EXTENSIONS = frozenset({".md", ".txt", ".rst", ".adoc"})


def _graphify_output_dir(repo_path: Path) -> Path:
    """Directório de output do graphify para um repo.

    graphify extract --out DIR escreve em DIR/graphify-out/,
    portanto apontamos --out para {output_dir}/{repo_name}.
    """
    return Path(settings.graphify.output_dir) / repo_path.name / "graphify-out"


def _graphify_out_parent(repo_path: Path) -> Path:
    """O valor a passar a --out (o pai de graphify-out/)."""
    return Path(settings.graphify.output_dir) / repo_path.name


def _graph_json_path(repo_path: Path) -> Path:
    return _graphify_output_dir(repo_path) / "graph.json"


def _report_path(repo_path: Path) -> Path:
    return _graphify_output_dir(repo_path) / "GRAPH_REPORT.md"


# ---------------------------------------------------------------------------
# Incremental change detection
# ---------------------------------------------------------------------------

def _file_md5(path: Path) -> str:
    """Compute MD5 hex digest of a file (matches graphify's manifest hash)."""
    h = hashlib.md5(usedforsecurity=False)
    try:
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
    except OSError:
        return ""
    return h.hexdigest()


def _detect_changes(repo_path: Path, manifest_path: Path) -> tuple[bool, bool]:
    """Compare graphify manifest.json against current repo files.

    Returns:
        (has_changes, has_doc_changes) — *has_doc_changes* is True when
        at least one changed/new file has a doc extension (.md, .txt, …).
    """
    if not manifest_path.exists():
        return True, True  # no manifest → full build needed

    try:
        manifest: dict = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return True, True

    has_changes = False
    has_doc_changes = False

    # Check existing manifest entries for changed/deleted files
    for file_path_str, info in manifest.items():
        fp = Path(file_path_str)
        if not fp.exists():
            has_changes = True
            if fp.suffix.lower() in _DOC_EXTENSIONS:
                has_doc_changes = True
            continue
        stored_hash = info.get("hash", "")
        if stored_hash and _file_md5(fp) != stored_hash:
            has_changes = True
            if fp.suffix.lower() in _DOC_EXTENSIONS:
                has_doc_changes = True

    # Early exit if we already know docs changed
    if has_doc_changes:
        return True, True

    # Check for new files not in the manifest (walk repo)
    manifest_paths = set(manifest.keys())
    try:
        for child in repo_path.rglob("*"):
            if not child.is_file():
                continue
            # Skip hidden dirs and common non-source paths
            parts = child.relative_to(repo_path).parts
            if any(p.startswith(".") or p in ("node_modules", "__pycache__", ".git", "venv", ".venv") for p in parts):
                continue
            if str(child) not in manifest_paths:
                has_changes = True
                if child.suffix.lower() in _DOC_EXTENSIONS:
                    has_doc_changes = True
                    return True, True
    except OSError:
        pass

    return has_changes, has_doc_changes


def build_graph(repo_path: Path | str, *, force: bool = False) -> bool:
    """Executa graphify extract/update para um único repo.

    Incremental logic (when *force* is False):
      1. Read graphify's manifest.json and compare file hashes.
      2. If nothing changed → skip subprocess entirely.
      3. If only code files changed → ``graphify update`` (AST-only, no LLM).
      4. If doc files also changed → ``graphify extract`` (AST + LLM).

    Returns True if successful (or no changes), False on error.
    """
    repo_path = Path(repo_path).expanduser().resolve()
    if not repo_path.exists():
        log.warning("[Graphify] Repo não encontrado: %s — skipping.", repo_path)
        return False

    output_dir = _graphify_output_dir(repo_path)
    graph_json = _graph_json_path(repo_path)
    manifest_json = output_dir / "manifest.json"

    # Criar directório de output se necessário
    output_dir.parent.mkdir(parents=True, exist_ok=True)

    # force=True: apagar manifest para trigger rebuild completo (AST + LLM)
    if force and manifest_json.exists():
        manifest_json.unlink()
        log.info("[Graphify] Manifest removido — rebuild completo forçado.")

    if graph_json.exists() and not force and not settings.graphify.auto_update:
        log.info("[Graphify] Grafo já existe para '%s' e auto_update=false — skipping.", repo_path.name)
        return True

    # --- Incremental change detection ---
    use_update = False  # True → graphify update (AST-only), False → graphify extract
    if not force and manifest_json.exists() and graph_json.exists():
        has_changes, has_doc_changes = _detect_changes(repo_path, manifest_json)
        if not has_changes:
            log.info("[Graphify] Sem alterações em '%s' — skipping.", repo_path.name)
            print(f"  [graphify] {repo_path.name}: sem alterações — skip")
            return True
        if not has_doc_changes:
            use_update = True
            log.info("[Graphify] Apenas código alterado em '%s' — graphify update (sem LLM).", repo_path.name)

    if force:
        mode = "rebuild completo"
    elif use_update:
        mode = "update (AST-only)"
    elif manifest_json.exists():
        mode = "incremental"
    else:
        mode = "build inicial"

    # --- Build command ---
    if use_update:
        cmd = ["graphify", "update", str(repo_path)]
    else:
        cmd = [
            "graphify", "extract", str(repo_path),
            "--backend", settings.graphify.backend,
            "--out", str(_graphify_out_parent(repo_path)),
        ]

    # Modelo específico (por defeito graphify usa qwen2.5-coder:7b com ollama)
    if settings.graphify.model and not use_update:
        cmd += ["--model", settings.graphify.model]

    log.info("[Graphify] %s — %s", repo_path.name, mode)
    log.debug("[Graphify] Comando: %s", " ".join(cmd))

    # Graphify exige OLLAMA_BASE_URL para o backend ollama.
    # Injectar a partir do base_url configurado em rag.toml [ollama].
    env = os.environ.copy()
    if settings.graphify.backend == "ollama":
        ollama_base = settings.ollama.base_url.rstrip("/")
        env.setdefault("OLLAMA_BASE_URL", f"{ollama_base}/v1")
        # Graphify exige OLLAMA_API_KEY mas não o usa como credencial real;
        # é um placeholder obrigatório da lib litellm que o graphify usa.
        env.setdefault("OLLAMA_API_KEY", "ollama")

    try:
        timeout = settings.performance.graph_timeout or None
        result = subprocess.run(
            cmd,
            cwd=str(repo_path),
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.stderr:
            log.debug("[Graphify] stderr: %s", result.stderr.strip())
        log.info("[Graphify] Concluído. Grafo em: %s", graph_json)
        return True
    except subprocess.TimeoutExpired:
        log.error(
            "[Graphify] TIMEOUT (%ds) para '%s' — skipping. "
            "Ajusta graph_timeout em rag.toml se necessário.",
            settings.performance.graph_timeout, repo_path.name,
        )
        return False
    except subprocess.CalledProcessError as e:
        log.error(
            "[Graphify] ERRO (exit code %d): %s\nstdout: %s\nstderr: %s",
            e.returncode, e, (e.stdout or "").strip(), (e.stderr or "").strip(),
        )
        return False
    except FileNotFoundError:
        raise FileNotFoundError(
            "Comando 'graphify' não encontrado. "
            "Instala com: pip install graphifyy"
        )


def build_graphs(*, force: bool = False) -> None:
    """Executa graphify extract para todos os repos configurados em rag.toml.

    Se *force* for True, faz update mesmo que auto_update=false.
    Usa ThreadPoolExecutor quando graph_parallel_jobs > 1 (subprocess.run é
    thread-safe — cada worker espera por um processo isolado).
    """
    if not settings.repos.paths:
        log.info("[Graphify] Sem repos configurados. Skipping.")
        return

    model_info = f" | modelo: {settings.graphify.model}" if settings.graphify.model else ""
    parallel = settings.performance.graph_parallel_jobs
    log.info(
        "[Graphify] Backend: %s%s | force: %s | parallel: %d",
        settings.graphify.backend, model_info, force, parallel,
    )

    from obsidian_rag.tuning import should_throttle

    def _build_one(repo_path: str) -> bool:
        """Build a single repo with throttle check and optional VRAM guard."""
        advice = should_throttle(settings.performance, str(settings.paths.data_dir))
        if advice.low_disk:
            log.error("[Graphify] Disco quase cheio — skipping '%s'. %s", Path(repo_path).name, advice.reason)
            return False
        if advice.pause_sync:
            import time as _time
            log.warning("[Graphify] Pressão antes de '%s': %s", Path(repo_path).name, advice.reason)
            for _attempt in range(1, 4):
                _time.sleep(5)
                advice = should_throttle(settings.performance, str(settings.paths.data_dir))
                if not advice.pause_sync:
                    break
            else:
                log.warning("[Graphify] Pressão mantém-se — a continuar com precaução.")

        # VRAM guard: ensure enough free VRAM before launching LLM-intensive subprocess
        if parallel > 1:
            try:
                from obsidian_rag.pipeline.governor import _read_vram
                _used, total, _pct = _read_vram()
                free_gb = total - _used if total > 0 else 0
                if total > 0 and free_gb < 1.5:
                    import time as _time
                    log.info(
                        "[Graphify] VRAM baixa (%.1fGB livre) — aguardando antes de '%s'...",
                        free_gb, Path(repo_path).name,
                    )
                    _time.sleep(10)
            except Exception:
                pass  # pynvml unavailable — proceed without guard

        return build_graph(repo_path, force=force)

    if parallel > 1:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        log.info("[Graphify] A processar %d repos em paralelo (max %d workers)...",
                 len(settings.repos.paths), parallel)
        successes = 0
        with ThreadPoolExecutor(max_workers=parallel) as executor:
            futures = {
                executor.submit(_build_one, rp): rp
                for rp in settings.repos.paths
            }
            for future in as_completed(futures):
                if future.result():
                    successes += 1
                gc.collect()
    else:
        successes = 0
        for repo_path in settings.repos.paths:
            if _build_one(repo_path):
                successes += 1
            gc.collect()

    log.info("[Graphify] %d/%d repos processados.", successes, len(settings.repos.paths))


def graph_exists(repo_name: str) -> bool:
    """True se o graph.json existe para um repo."""
    for repo_path in settings.repos.paths:
        if Path(repo_path).name == repo_name:
            return _graph_json_path(repo_path).exists()
    return False


def get_graph_json_path(repo_name: str) -> Path | None:
    """Devolve o path para o graph.json de um repo, ou None se não existir."""
    for repo_path in settings.repos.paths:
        p = Path(repo_path)
        if p.name == repo_name:
            gp = _graph_json_path(p)
            return gp if gp.exists() else None
    return None


def get_report_path(repo_name: str) -> Path | None:
    """Devolve o path para o GRAPH_REPORT.md de um repo, ou None se não existir."""
    for repo_path in settings.repos.paths:
        p = Path(repo_path)
        if p.name == repo_name:
            rp = _report_path(p)
            return rp if rp.exists() else None
    return None
