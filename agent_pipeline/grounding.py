"""Bounded, cited code grounding for the planning agents (spec §20.1–§20.2).

The retriever already returns ``Hit`` objects with the actual source text, score, path
and line metadata — but Design/Architect historically consumed only ``retrieve_paths()``,
so the model saw filenames, not code. That is the difference between "a plan that names
files" and "a plan grounded in what the files actually implement".

This module turns retriever hits into a **single, deduplicated, budget-bounded** snapshot
of ``GroundingChunk`` records (with ``path:start-end`` citations) that Design and Architect
share, so their view of the repository is identical. A compact, secret-free snapshot
(path/lines/score/kind, no full text) is recorded in ``plans.json`` for auditability.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from agent_pipeline import config

# Keep the whole grounding block bounded so we never dump the repo into the prompt.
DEFAULT_CHAR_BUDGET = 6000
PER_CHUNK_CHAR_CAP = 1600


@dataclass
class GroundingChunk:
    chunk_id: str
    rel_path: str
    start_line: int
    end_line: int
    text: str
    score: float
    kind: str

    def cite(self) -> str:
        return f"{self.rel_path}:{self.start_line}-{self.end_line}"

    def snapshot(self) -> dict:
        """Compact, serializable, secret-free record for plans.json (no full text)."""
        return {
            "chunk_id": self.chunk_id,
            "rel_path": self.rel_path,
            "start_line": self.start_line,
            "end_line": self.end_line,
            "score": round(float(self.score), 4),
            "kind": self.kind,
        }


def build_grounding(retriever, requirement: str, top_k: int = 8,
                    char_budget: int = DEFAULT_CHAR_BUDGET) -> List[GroundingChunk]:
    """Query once and return a deduped, budget-bounded list of GroundingChunks.

    Overlapping/identical (path, line-range) hits are collapsed; the running character
    budget stops us from sending the whole codebase to the LLM while still guaranteeing
    at least the single strongest chunk.
    """
    hits = retriever.query(requirement, top_k=top_k)
    chunks: List[GroundingChunk] = []
    seen: set = set()
    used = 0
    for h in hits:
        meta = h.metadata or {}
        start = _int(meta.get("start_line"))
        end = _int(meta.get("end_line"))
        key = (h.rel_path, start, end)
        if key in seen:
            continue
        text = (h.text or "")[:PER_CHUNK_CHAR_CAP]
        if chunks and used + len(text) > char_budget:
            break  # budget exhausted (but we always keep at least one chunk)
        seen.add(key)
        used += len(text)
        chunks.append(GroundingChunk(
            chunk_id=getattr(h, "chunk_id", ""),
            rel_path=h.rel_path,
            start_line=start,
            end_line=end,
            text=text,
            score=float(getattr(h, "score", 0.0)),
            kind=meta.get("kind", "code"),
        ))
    return chunks


def candidate_files(chunks: List[GroundingChunk]) -> List[str]:
    """Ranked, de-duplicated file paths derived from the grounding — kept so existing
    callers/evals that expect ``candidate_files`` keep working (spec §20.2)."""
    seen: List[str] = []
    for c in chunks:
        if c.rel_path not in seen:
            seen.append(c.rel_path)
    return seen


def snapshot(chunks: List[GroundingChunk]) -> List[dict]:
    return [c.snapshot() for c in chunks]


def to_prompt_block(chunks: List[GroundingChunk], char_budget: int = DEFAULT_CHAR_BUDGET) -> str:
    """Render the grounding as cited, fenced code blocks for the agent prompt.

    Only ``code`` chunks are shown as source (the blueprint reaches agents via
    context.md already); each block is labelled with its ``path:start-end`` citation so
    the model — and a human reviewer — can trace a plan back to real evidence.
    """
    code = [c for c in chunks if c.kind == "code"] or chunks
    lines: List[str] = ["RETRIEVED CODE (actual implementation evidence — cite these):"]
    used = 0
    for c in code:
        body = c.text.strip()
        if used + len(body) > char_budget and used > 0:
            lines.append(f"\n# … grounding truncated at {char_budget} chars …")
            break
        used += len(body)
        lang = _lang_for(c.rel_path)
        lines.append(f"\n// {c.cite()}  (score {round(c.score, 3)})\n```{lang}\n{body}\n```")
    return "\n".join(lines)


def _int(val, default: int = 0) -> int:
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def _lang_for(path: str) -> str:
    if path.endswith((".ts", ".tsx")):
        return "typescript"
    if path.endswith((".js", ".jsx")):
        return "javascript"
    if path.endswith(".scss") or path.endswith(".css"):
        return "scss"
    if path.endswith(".html"):
        return "html"
    if path.endswith(".sql"):
        return "sql"
    if path.endswith(".md"):
        return "markdown"
    return ""
