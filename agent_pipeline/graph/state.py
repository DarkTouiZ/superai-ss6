"""Shared pipeline state passed between LangGraph nodes.

This is the typed channel the four phases read/write. Week 1 only the
``understand`` fields are populated (by the Retriever). The rest are declared now
so later weeks slot in without reshaping state.
"""
from __future__ import annotations

from typing import List, Optional, TypedDict


class RetrievedChunk(TypedDict):
    chunk_id: str
    rel_path: str
    text: str
    score: float


class PipelineState(TypedDict, total=False):
    # ---- Phase 1: Understand (Week 1) ----
    requirement: str                      # the user requirement to satisfy
    retrieved: List[RetrievedChunk]       # RAG hits for the requirement
    blueprint_rules: List[str]            # relevant context.md rules

    # ---- Phase 2: Plan (Week 2) ----
    plans: Optional[dict]                 # {"A": ..., "B": ..., "C": ...}

    # ---- Phase 3: Debate & Execute (Week 3) ----
    plan_scores: Optional[dict]           # plan_id -> weighted score
    chosen_plan: Optional[str]
    branch_name: Optional[str]

    # ---- Phase 4: Review (Week 4) ----
    tests_passed: Optional[bool]
    awaiting_human_review: Optional[bool]
