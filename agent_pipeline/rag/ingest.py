"""Ingestion: walk a local codebase + context.md and split into retrievable chunks.

Chunking strategy is a simple overlapping line window. It's language-agnostic and
proven (the same approach LangChain's ``RecursiveCharacterTextSplitter`` falls back
to). We deliberately do NOT invent a custom AST indexer for the MVP — line windows
give good Recall@k on a small repo and keep the eval honest.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from agent_pipeline import config


@dataclass
class Chunk:
    """One retrievable unit of text with provenance."""

    id: str
    text: str
    rel_path: str          # path relative to project root (the eval label space)
    start_line: int
    end_line: int
    kind: str              # "code" | "blueprint"
    metadata: dict = field(default_factory=dict)


def _iter_files(roots: Iterable[Path]) -> Iterator[Path]:
    for root in roots:
        if root.is_file():
            yield root
            continue
        for path in sorted(root.rglob("*")):
            if path.is_dir():
                continue
            if any(part in config.IGNORE_DIRS for part in path.parts):
                continue
            if path.suffix.lower() in config.INDEXED_SUFFIXES:
                yield path


def _window_chunks(lines: list[str], size: int, overlap: int) -> Iterator[tuple[int, int, str]]:
    """Yield (start_line, end_line, text) windows (1-indexed, inclusive)."""
    if not lines:
        return
    step = max(1, size - overlap)
    i = 0
    n = len(lines)
    while i < n:
        window = lines[i : i + size]
        start = i + 1
        end = min(i + size, n)
        text = "".join(window).strip()
        if text:
            yield start, end, text
        if i + size >= n:
            break
        i += step


def load_chunks(
    project_root: Path | None = None,
    *,
    size: int | None = None,
    overlap: int | None = None,
) -> list[Chunk]:
    """Build the chunk list for the target repo plus the context.md blueprint."""
    project_root = project_root or config.PROJECT_ROOT
    size = size or config.CHUNK_LINES
    overlap = overlap if overlap is not None else config.CHUNK_OVERLAP

    roots = [config.TARGET_REPO_DIR, config.CONTEXT_FILE]
    chunks: list[Chunk] = []
    for path in _iter_files(roots):
        try:
            raw = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        rel_path = str(path.relative_to(project_root))
        kind = "blueprint" if path == config.CONTEXT_FILE else "code"
        lines = raw.splitlines(keepends=True)
        for start, end, text in _window_chunks(lines, size, overlap):
            chunk_id = f"{rel_path}:{start}-{end}"
            chunks.append(
                Chunk(
                    id=chunk_id,
                    text=text,
                    rel_path=rel_path,
                    start_line=start,
                    end_line=end,
                    kind=kind,
                    metadata={"rel_path": rel_path, "kind": kind,
                              "start_line": start, "end_line": end},
                )
            )
    return chunks


if __name__ == "__main__":
    cs = load_chunks()
    print(f"Loaded {len(cs)} chunks from {len({c.rel_path for c in cs})} files")
    for c in cs[:3]:
        print(f"  {c.id} ({c.kind})")
