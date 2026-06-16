"""High-level, callable API for the SS6 autonomous software-engineering pipeline.

This is the stable surface you import as a library:

    from agent_pipeline import retrieve, plan, debate, execute, run

    paths   = retrieve("how is a delivery fee computed?")     # Phase 1
    result  = plan("Add a top-customers-by-spend screen")     # Phases 1-3 (design+plans+debate)
    review  = execute(result)                                 # Phases 3b-4 (code + compliance, halts)
    full    = run("Add ALL Member points redemption")         # the whole loop in one call

Every function works offline (deterministic mock + lexical RAG fallback) and with a
live provider via SS6_LLM_PROVIDER. Functions return plain dicts/lists so they are
easy to use as agent tools; passing ``out_dir`` also writes the human artifacts
(DESIGN.md / PLANS.md / DEBATE.md / REVIEW.md).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Union

from agent_pipeline import config, normalize
from agent_pipeline.rag.retriever import Retriever
from agent_pipeline.agents.design import DesignAgent, write_design_md
from agent_pipeline.agents.architect import ArchitectAgent, write_outputs
from agent_pipeline.agents.evaluator import (
    EvaluatorAgent,
    result_to_dict,
    write_debate_md,
)
from agent_pipeline.agents.developer import DeveloperAgent
from agent_pipeline.review import review_files, write_review_md

PlansLike = Union[dict, str, Path]


def retrieve(requirement: str, top_k: int = config.DEFAULT_TOP_K) -> list[str]:
    """Phase 1 — return the repo files most relevant to a requirement (RAG)."""
    return Retriever(rebuild=True).retrieve_paths(requirement, top_k=top_k)


def plan(requirement: str, out_dir: Optional[Path] = None) -> dict:
    """Phases 1-3 — design the requirement, produce three grounded plans, and run
    the deterministic debate. Returns the full ``plans.json`` payload (incl. the
    winner). If ``out_dir`` is given, also writes DESIGN.md / PLANS.md / DEBATE.md.
    """
    retriever = Retriever(rebuild=True)
    design = DesignAgent(retriever=retriever).generate(requirement)
    plan_set = ArchitectAgent(retriever=retriever).generate(requirement)

    plan_set.plans = normalize.normalize_plans(plan_set.plans)
    design.artifacts = normalize.normalize_design(design.artifacts)
    debate = EvaluatorAgent().evaluate(plan_set.plans)

    payload = {
        "requirement": plan_set.requirement,
        "provider": plan_set.provider,
        "is_live": plan_set.is_live,
        "candidate_files": plan_set.candidate_files,
        "plans": plan_set.plans,
        "design": design.artifacts,
        "debate": result_to_dict(debate),
    }
    if out_dir is not None:
        out_dir = Path(out_dir)
        write_design_md(design, out_dir)
        json_path, _ = write_outputs(plan_set, out_dir, design=design.artifacts)
        write_debate_md(debate, out_dir)
        # fold the debate result into plans.json on disk
        data = json.loads(json_path.read_text(encoding="utf-8"))
        data["debate"] = payload["debate"]
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return payload


def debate(plans: PlansLike, weights: Optional[dict] = None) -> dict:
    """Phase 3 — (re)score a set of plans with the weighted evaluator. Accepts a
    plans payload dict, a list of plans, or a path to plans.json. ``weights`` lets
    you explore sensitivity (e.g. {'performance': 0.5, ...})."""
    plan_list = _coerce_plans(plans)
    return result_to_dict(EvaluatorAgent(weights=weights).evaluate(plan_list))


def execute(plans: PlansLike, out_dir: Optional[Path] = None) -> dict:
    """Phases 3b-4 — implement the debate-winning plan on an isolated git branch,
    run the context.md compliance suite, and HALT for human review (never merges).
    Returns a summary; writes REVIEW.md when ``out_dir`` is given."""
    payload = _coerce_payload(plans)
    plan_list = payload["plans"]
    design = payload.get("design", {})
    requirement = payload.get("requirement", "")
    winner_id = payload.get("debate", {}).get("winner_id")
    if not winner_id:
        winner_id = result_to_dict(EvaluatorAgent().evaluate(plan_list))["winner_id"]
    winner = next(p for p in plan_list if p.get("id") == winner_id)

    exec_result = DeveloperAgent().execute(requirement, winner, design)
    review = review_files(exec_result.files)
    if out_dir is not None:
        write_review_md(exec_result, review, Path(out_dir))
    return {
        "branch": exec_result.branch,
        "workdir": exec_result.workdir,
        "changed_files": exec_result.changed_files,
        "provider": exec_result.provider,
        "is_live": exec_result.is_live,
        "compliance_passed": review.passed,
        "violations": [v for f in review.files for v in f.violations],
        "awaiting_human_review": True,
    }


def run(requirement: str, out_dir: Optional[Path] = None) -> dict:
    """Convenience: the entire loop (plan -> execute) for one requirement."""
    out = Path(out_dir) if out_dir is not None else config.PROJECT_ROOT / "out"
    payload = plan(requirement, out_dir=out)
    review = execute(payload, out_dir=out)
    return {"plan": payload, "review": review}


# Re-export the evaluator scorer for programmatic use as a "tool".
from agent_pipeline.agents.evaluator import score_plan  # noqa: E402


def _coerce_payload(plans: PlansLike) -> dict:
    if isinstance(plans, (str, Path)):
        return json.loads(Path(plans).read_text(encoding="utf-8"))
    if isinstance(plans, dict) and "plans" in plans:
        return plans
    if isinstance(plans, list):
        return {"plans": plans}
    raise TypeError("plans must be a payload dict, a list of plans, or a path to plans.json")


def _coerce_plans(plans: PlansLike) -> list:
    payload = _coerce_payload(plans)
    return payload["plans"]
