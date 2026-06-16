"""Reference normalization.

Live models reference files/primitives with inconsistent conventions — bare names
(``Card``), repo-relative (``src/components/Card.tsx``), or project-relative
(``target_repo/src/components/Card.tsx``). This module canonicalizes any such
reference to a single project-relative path so both the evals and the downstream
Developer agent consume clean, resolvable paths.

Strategy: reduce a reference to its *stem* (basename without extension), then look it
up in an index of real repo files. Unknown references that look like new files under
``src/`` are prefixed to ``target_repo/...``; anything else is returned unchanged.
"""
from __future__ import annotations

from functools import lru_cache

from agent_pipeline import config


def _stem(ref: str) -> str:
    return ref.split("/")[-1].rsplit(".", 1)[0]


@lru_cache(maxsize=1)
def _repo_index() -> dict[str, str]:
    """stem -> project-relative path for every file in the target repo + context.md."""
    index: dict[str, str] = {}
    for p in config.TARGET_REPO_DIR.rglob("*"):
        if p.is_file():
            rel = str(p.relative_to(config.PROJECT_ROOT))
            index[_stem(rel)] = rel
    ctx = config.CONTEXT_FILE
    index[_stem(str(ctx.relative_to(config.PROJECT_ROOT)))] = str(ctx.relative_to(config.PROJECT_ROOT))
    return index


@lru_cache(maxsize=1)
def _canonical_primitive_index() -> dict[str, str]:
    return {_stem(p): p for p in config.CANONICAL_PRIMITIVES}


def canonical_path(ref: str) -> str:
    """Resolve a file reference to a project-relative path.

    Existing repo file (by stem) -> its real path. New file under ``src/`` ->
    ``target_repo/<ref>``. Already project-relative or unknown -> unchanged.
    """
    if not ref:
        return ref
    stem = _stem(ref)
    repo = _repo_index()
    if stem in repo:
        return repo[stem]
    if ref.startswith("target_repo/"):
        return ref
    if ref.startswith("src/"):
        return f"target_repo/{ref}"
    return ref


def canonical_primitive(ref: str) -> str:
    """Resolve a primitive reference (any convention) to its canonical path."""
    return _canonical_primitive_index().get(_stem(ref), canonical_path(ref))


def normalize_plan(plan: dict) -> dict:
    """Return a copy of a plan with file/primitive references canonicalized."""
    out = dict(plan)
    out["files_touched"] = [canonical_path(f) for f in plan.get("files_touched", [])]
    out["primitives_reused"] = [canonical_primitive(p) for p in plan.get("primitives_reused", [])]
    return out


def normalize_plans(plans: list[dict]) -> list[dict]:
    return [normalize_plan(p) for p in plans]


def normalize_design(design: dict) -> dict:
    """Canonicalize the primitive/service references inside a design artifact dict."""
    out = dict(design)
    if "primitives_reused" in out:
        out["primitives_reused"] = [canonical_primitive(p) for p in out["primitives_reused"]]
    if "services_used" in out:
        out["services_used"] = [canonical_path(s) for s in out["services_used"]]
    return out
