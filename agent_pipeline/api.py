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

from dataclasses import asdict

from agent_pipeline import config, normalize
from agent_pipeline import environment as environment_mod
from agent_pipeline import grounding as grounding_mod
from agent_pipeline import impact as impact_mod
from agent_pipeline import intake as intake_mod
from agent_pipeline.intake import ProblemPacket
from agent_pipeline.rag.retriever import Retriever
from agent_pipeline.agents.design import DesignAgent, write_design_md
from agent_pipeline.agents.architect import ArchitectAgent, write_outputs
from agent_pipeline.agents.evaluator import (
    EvaluatorAgent,
    result_to_dict,
    write_debate_md,
)
from agent_pipeline.agents.developer import DeveloperAgent
from agent_pipeline.review import review_files, write_review_md, evidence_from_files

PlansLike = Union[dict, str, Path]
RequirementLike = Union[str, ProblemPacket]


def _resolve_requirement(requirement: RequirementLike):
    """Accept a raw requirement string or a ProblemPacket. Returns
    ``(requirement_text, packet_or_None)``; for a packet the requirement text is the
    rich prompt-compatible form so existing agents run unchanged (spec §7, §13)."""
    if isinstance(requirement, ProblemPacket):
        packet = intake_mod.finalize(requirement)
        return intake_mod.requirement_text(packet), packet
    return requirement, None


def _packet_payload(packet: Optional[ProblemPacket]) -> dict:
    """The packet-derived slice of plans.json (empty-ish when no packet was used)."""
    if packet is None:
        return {"problem_packet": None, "assumptions": [], "open_questions": [], "readiness": None}
    return {
        "problem_packet": packet.to_dict(),
        "assumptions": [asdict(a) for a in packet.assumptions],
        "open_questions": [asdict(q) for q in packet.open_questions],
        "readiness": asdict(packet.readiness) if packet.readiness else None,
    }


def retrieve(requirement: str, top_k: int = config.DEFAULT_TOP_K) -> list[str]:
    """Phase 1 — return the repo files most relevant to a requirement (RAG)."""
    return Retriever(rebuild=True).retrieve_paths(requirement, top_k=top_k)


def plan(requirement: RequirementLike, out_dir: Optional[Path] = None) -> dict:
    """Phases 1-3 — design the requirement, produce three grounded plans, and run
    the deterministic debate. Returns the full ``plans.json`` payload (incl. the
    winner). If ``out_dir`` is given, also writes DESIGN.md / PLANS.md / DEBATE.md.

    ``requirement`` may be a raw string (unchanged behavior) or a structured
    ``ProblemPacket``; when a packet is given, its packet-derived requirement text
    grounds the agents and the packet + readiness are recorded in plans.json (spec §13).
    """
    requirement, packet = _resolve_requirement(requirement)
    retriever = Retriever(rebuild=True)
    # One grounding snapshot per run, shared by Design and Architect so their view of
    # the repository is identical, and carrying the actual retrieved code (spec §20.2).
    chunks = grounding_mod.build_grounding(retriever, requirement)

    # Load the operational environment contract (spec §19.4) and produce the pre-planning
    # change-impact analysis (spec §20.3) the Architect must respond to.
    env = environment_mod.load_environment()
    impact = impact_mod.analyze_impact(requirement, chunks, environment=env)
    impact_block = impact_mod.impact_prompt_block(impact)

    design = DesignAgent(retriever=retriever).generate(requirement, grounding=chunks)
    plan_set = ArchitectAgent(retriever=retriever).generate(
        requirement, grounding=chunks, impact_block=impact_block
    )

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
        "environment": env.summary(),
        "grounding": grounding_mod.snapshot(chunks),
        "impact": impact.to_dict(),
        **_packet_payload(packet),
    }
    if out_dir is not None:
        out_dir = Path(out_dir)
        write_design_md(design, out_dir)
        json_path, _ = write_outputs(plan_set, out_dir, design=design.artifacts)
        write_debate_md(debate, out_dir)
        impact_mod.write_impact_md(impact, out_dir, requirement=requirement)
        # fold the debate result + environment + grounding + impact + packet into plans.json
        data = json.loads(json_path.read_text(encoding="utf-8"))
        for key in ("debate", "environment", "grounding", "impact",
                    "problem_packet", "assumptions", "open_questions", "readiness"):
            data[key] = payload[key]
        json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return payload


def debate(plans: PlansLike, weights: Optional[dict] = None) -> dict:
    """Phase 3 — (re)score a set of plans with the weighted evaluator. Accepts a
    plans payload dict, a list of plans, or a path to plans.json. ``weights`` lets
    you explore sensitivity (e.g. {'performance': 0.5, ...})."""
    plan_list = _coerce_plans(plans)
    return result_to_dict(EvaluatorAgent(weights=weights).evaluate(plan_list))


def execute(
    plans: PlansLike,
    out_dir: Optional[Path] = None,
    run_tests: bool = False,
    max_repair_attempts: Optional[int] = None,
) -> dict:
    """Phases 3b-4 — implement the debate-winning plan on an isolated git branch,
    run the context.md compliance suite, and HALT for human review (never merges).
    Returns a summary; writes REVIEW.md when ``out_dir`` is given.

    ``run_tests=True`` additionally runs the target repo's real ``tsc`` and ``jest``
    inside the isolated copy (zero cost, local only) and folds the result into the
    gate — so the change must both be compliant and actually compile + pass tests.

    Repair loop (roadmap M2): if the gate fails, the Developer is re-asked with the
    violations fed back, up to ``max_repair_attempts`` times (default
    ``config.MAX_REPAIR_ATTEMPTS``), before halting.
    """
    from agent_pipeline.review import GateOutcome, gate_feedback
    from agent_pipeline import checks

    payload = _coerce_payload(plans)
    plan_list = payload["plans"]
    design = payload.get("design", {})
    requirement = payload.get("requirement", "")
    winner_id = payload.get("debate", {}).get("winner_id")
    if not winner_id:
        winner_id = result_to_dict(EvaluatorAgent().evaluate(plan_list))["winner_id"]
    winner = next(p for p in plan_list if p.get("id") == winner_id)

    max_attempts = max_repair_attempts or config.MAX_REPAIR_ATTEMPTS

    def gate(files, workdir) -> "GateOutcome":
        review = review_files(files)
        # Select checks from the ACTUAL changed paths (spec §22.4): backend change →
        # backend suite, frontend change → frontend suite.
        changed = [f["path"] for f in files]
        tests = checks.run_selected_checks(workdir, changed) if run_tests else []
        tests_ok = checks.checks_passed(tests) if run_tests else True
        passed = review.passed and tests_ok
        return GateOutcome(
            passed=passed,
            feedback=gate_feedback(review, tests),
            review=review,
            tests=tests,
        )

    exec_result = DeveloperAgent().execute(
        requirement, winner, design, gate=gate, max_attempts=max_attempts
    )

    review = exec_result.gate_review or review_files(exec_result.files)
    test_results = exec_result.gate_tests or []
    tests_passed = checks.checks_passed(test_results) if run_tests else True
    # Honest overall status of the real checks (PASS/FAIL/UNVERIFIED/NOT_REQUIRED).
    checks_status = checks.gate_status(test_results) if run_tests else "NOT_REQUIRED"

    # Roadmap M6: validate the debate winner against POST-EXECUTION evidence, not its
    # self-declared label — a 'reuse' winner is only validated if the code actually
    # reused canonical primitives or followed the repository+service layering.
    evidence = evidence_from_files(exec_result.files)
    paths_joined = " ".join(evidence["files_touched"])
    reuse_evidence = bool(evidence["reused_components"]) or (
        "repositories/" in paths_joined and "services/" in paths_joined
    )
    winner_focus = winner.get("priority_focus")
    winner_validated = (winner_focus != "reuse") or reuse_evidence
    evidence["winner_focus"] = winner_focus
    evidence["winner_validated"] = winner_validated

    # Environment freshness travels with the plan; fall back to a fresh load if this
    # payload predates the environment contract (spec §19.4).
    env_summary = payload.get("environment") or environment_mod.load_environment().summary()

    if out_dir is not None:
        write_review_md(exec_result, review, Path(out_dir), checks=test_results,
                        environment=env_summary)
    return {
        "branch": exec_result.branch,
        "workdir": exec_result.workdir,
        "environment": env_summary,
        "changed_files": exec_result.changed_files,
        "provider": exec_result.provider,
        "is_live": exec_result.is_live,
        "compliance_passed": review.passed,
        "violations": [v for f in review.files for v in f.violations],
        "tests_run": bool(run_tests),
        "tests": [{"name": r.name, "result": r.status, "detail": r.detail[:400]} for r in test_results],
        "tests_passed": tests_passed,
        "checks_status": checks_status,            # honest: PASS/FAIL/UNVERIFIED/NOT_REQUIRED
        "gate_passed": review.passed and tests_passed,
        "attempts": exec_result.attempts,
        "repaired": exec_result.repaired,
        "attempt_log": exec_result.attempt_log,
        "evidence": evidence,                      # roadmap M6 (incl. winner_validated)
        "winner_validated": winner_validated,      # debate claim vs execution reality
        "awaiting_human_review": True,
    }


# --- Clarification step (roadmap M7) ----------------------------------------- #
_VAGUE_WORDS = {
    "better", "improve", "improved", "fix", "update", "change", "nice", "good",
    "stuff", "things", "it", "something", "everything", "more",
    "make", "do", "handle", "redo", "tweak", "work", "the", "a", "an",
}


def needs_clarification(requirement: str) -> list[str]:
    """Return clarifying questions when a requirement is too underspecified to act on
    safely (roadmap M7). Empty list means it is concrete enough to proceed."""
    r = (requirement or "").strip()
    words = r.split()
    questions: list[str] = []
    if len(words) < 3:
        questions.append(
            "The requirement is very short — which screen or endpoint, and what data "
            "or behavior should it provide?"
        )
    elif r and all(w.lower() in _VAGUE_WORDS or len(w) <= 2 for w in words):
        questions.append(
            "This reads as non-specific — name the feature/file to change and the "
            "acceptance criterion (what does 'done' look like?)."
        )
    return questions


def run(
    requirement: RequirementLike,
    out_dir: Optional[Path] = None,
    run_tests: bool = False,
    max_repair_attempts: Optional[int] = None,
    allow_clarify: bool = False,
) -> dict:
    """Convenience: the entire loop (plan -> execute) for one requirement or packet.

    With ``allow_clarify=True`` the pipeline first checks readiness: for a raw string it
    runs the vagueness heuristic; for a ProblemPacket it uses the packet's own readiness
    and blocking open questions. Either way it returns ``{"needs_clarification": [...]}``
    instead of guessing (roadmap M7 / spec §8). A per-phase timing ``trace`` is included.
    """
    import time

    if allow_clarify:
        if isinstance(requirement, ProblemPacket):
            packet = intake_mod.finalize(requirement)
            blocking = [q.question for q in packet.open_questions if q.blocks_planning]
            if blocking:
                return {"needs_clarification": blocking, "requirement": intake_mod.requirement_text(packet)}
        else:
            questions = needs_clarification(requirement)
            if questions:
                return {"needs_clarification": questions, "requirement": requirement}

    out = Path(out_dir) if out_dir is not None else config.PROJECT_ROOT / "out"
    t0 = time.time()
    payload = plan(requirement, out_dir=out)
    t1 = time.time()
    review = execute(payload, out_dir=out, run_tests=run_tests, max_repair_attempts=max_repair_attempts)
    t2 = time.time()
    trace = {
        "plan_seconds": round(t1 - t0, 3),
        "execute_seconds": round(t2 - t1, 3),
        "total_seconds": round(t2 - t0, 3),
        "attempts": review.get("attempts", 1),
        "provider": review.get("provider"),
    }
    return {"plan": payload, "review": review, "trace": trace}


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
