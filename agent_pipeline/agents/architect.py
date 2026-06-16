"""Architect agent — Phase 2 ("Plan").

Given a requirement, it (1) retrieves grounding context via the Phase 1 RAG
retriever, (2) asks the LLM to produce three distinct plans — A (performance),
B (reuse/maintainability), C (pragmatic) — and (3) emits both a machine-readable
``plans.json`` and a human ``PLANS.md``.

The LLM call is provider-agnostic: live Anthropic Claude when configured, else the
deterministic mock. Either way the agent injects a ``<<GROUNDING:...>>`` block of
real candidate files/primitives so plans stay anchored to the actual codebase and
the Plan-phase eval (grounding check) is meaningful.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from agent_pipeline import config
from agent_pipeline.llm import get_llm
from agent_pipeline.rag.retriever import Retriever

SYSTEM_PROMPT = (
    "You are the Architect agent in an autonomous software-engineering pipeline. "
    "You must obey the System Blueprint (context.md). Produce exactly three DISTINCT "
    "implementation plans for the given requirement: Plan A optimized for performance, "
    "Plan B optimized for component reuse and maintainability, Plan C the pragmatic "
    "fastest path. Reuse the canonical primitives where possible. Reference only real "
    "files from the provided candidate set; if you add a file, mark it clearly as new. "
    "Respond with a single JSON object: {\"plans\":[{id,title,priority_focus,summary,"
    "steps[],files_touched[],primitives_reused[],tradeoffs{pros[],cons[]}}]}.\n"
    "BE THOROUGH, NOT TERSE. Each plan must have: AT LEAST 4 concrete, ordered steps "
    "naming the files/components touched; a files_touched list; a primitives_reused "
    "list; and tradeoffs with AT LEAST 2 pros and 2 cons. The three plans must differ "
    "meaningfully in approach, not just wording. priority_focus must be one of: "
    "performance, reuse, speed."
)

REQUIRED_PLAN_FIELDS = {
    "id", "title", "priority_focus", "summary",
    "steps", "files_touched", "primitives_reused", "tradeoffs",
}


@dataclass
class PlanSet:
    requirement: str
    plans: List[dict]
    candidate_files: List[str]
    provider: str
    is_live: bool
    raw: str = field(default="", repr=False)


def _build_user_prompt(requirement: str, candidate_files: List[str]) -> str:
    primitives = sorted(config.CANONICAL_PRIMITIVES & set(candidate_files)) or sorted(
        config.CANONICAL_PRIMITIVES
    )
    services = [f for f in candidate_files if "/services/" in f]
    grounding = {
        "requirement": requirement,
        "candidate_files": candidate_files,
        "primitives": primitives,
        "services": services,
    }
    blueprint = config.CONTEXT_FILE.read_text(encoding="utf-8")
    return (
        f"REQUIREMENT:\n{requirement}\n\n"
        f"SYSTEM BLUEPRINT (context.md):\n{blueprint}\n\n"
        f"CANDIDATE FILES (from RAG retrieval):\n" + "\n".join(candidate_files) + "\n\n"
        # The mock reads this block; a live model simply treats it as grounding facts.
        f"<<GROUNDING:{json.dumps(grounding)}>>\n"
    )


class ArchitectAgent:
    def __init__(self, retriever: Optional[Retriever] = None) -> None:
        self.retriever = retriever or Retriever(rebuild=True)
        self.llm = get_llm()

    def generate(self, requirement: str, top_k: int = 8) -> PlanSet:
        candidate_files = self.retriever.retrieve_paths(requirement, top_k=top_k)
        user = _build_user_prompt(requirement, candidate_files)
        resp = self.llm.complete(SYSTEM_PROMPT, user)
        plans = self._parse(resp.text)
        return PlanSet(
            requirement=requirement,
            plans=plans,
            candidate_files=candidate_files,
            provider=resp.provider,
            is_live=resp.is_live,
            raw=resp.text,
        )

    @staticmethod
    def _parse(text: str) -> List[dict]:
        """Extract the plans array from the model text (tolerant of code fences)."""
        s = text.strip()
        if "```" in s:
            s = s.split("```")[1]
            s = s[4:] if s.lower().startswith("json") else s
        start, end = s.find("{"), s.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("Architect response contained no JSON object.")
        obj = json.loads(s[start : end + 1])
        plans = obj.get("plans", [])
        if not isinstance(plans, list) or not plans:
            raise ValueError("Architect response had no plans.")
        return plans


def write_outputs(plan_set: PlanSet, out_dir: Path, design: Optional[dict] = None) -> tuple[Path, Path]:
    """Write plans.json (machine) and PLANS.md (human).

    If ``design`` (the DesignAgent artifacts dict) is supplied it is folded into
    plans.json under "design" so the design-quality eval can read a single file.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "plans.json"
    md_path = out_dir / "PLANS.md"

    payload = {
        "requirement": plan_set.requirement,
        "provider": plan_set.provider,
        "is_live": plan_set.is_live,
        "candidate_files": plan_set.candidate_files,
        "plans": plan_set.plans,
    }
    if design is not None:
        payload["design"] = design
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    lines = [
        "# PLANS.md — Architect output",
        "",
        f"**Requirement:** {plan_set.requirement}",
        "",
        f"_Generated by `{plan_set.provider}` "
        f"({'live model' if plan_set.is_live else 'deterministic mock'})._",
        "",
    ]
    for p in plan_set.plans:
        lines += [
            f"## Plan {p.get('id', '?')} — {p.get('title', '')}",
            "",
            f"- **Priority focus:** {p.get('priority_focus', '')}",
            f"- **Summary:** {p.get('summary', '')}",
            "",
            "**Steps:**",
            "",
        ]
        lines += [f"{i}. {s}" for i, s in enumerate(p.get("steps", []), 1)]
        lines += [
            "",
            f"**Files touched:** {', '.join(p.get('files_touched', [])) or '—'}",
            "",
            f"**Primitives reused:** {', '.join(p.get('primitives_reused', [])) or '—'}",
            "",
            "**Trade-offs:**",
            "",
            f"- Pros: {', '.join(p.get('tradeoffs', {}).get('pros', []))}",
            f"- Cons: {', '.join(p.get('tradeoffs', {}).get('cons', []))}",
            "",
        ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path
