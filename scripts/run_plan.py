#!/usr/bin/env python3
"""Week 2 entrypoint: Phase 1 retrieval → Design artifacts → Architect plans.

Usage:
    python scripts/run_plan.py
    python scripts/run_plan.py --requirement "Add a top-customers-by-revenue screen"
    SS6_LLM_PROVIDER=ollama python scripts/run_plan.py   # use a free local model
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_pipeline import config  # noqa: E402
from agent_pipeline import normalize  # noqa: E402
from agent_pipeline.agents.architect import ArchitectAgent, write_outputs  # noqa: E402
from agent_pipeline.agents.design import DesignAgent, write_design_md  # noqa: E402
from agent_pipeline.agents.evaluator import EvaluatorAgent, result_to_dict, write_debate_md  # noqa: E402
from agent_pipeline.rag.retriever import Retriever  # noqa: E402

DEFAULT_REQUIREMENT = (
    "Add a 'Top Customers by Spend' screen to the eleven-7 ops console that lists "
    "each customer with their total spend and loyalty tier, reusing the canonical "
    "Angular primitives and fetching through ApiService, respecting the design "
    "tokens and integer-satang money rules."
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Design + Plan phases.")
    parser.add_argument("--requirement", default=DEFAULT_REQUIREMENT)
    parser.add_argument("--out", type=Path, default=config.PROJECT_ROOT / "out")
    args = parser.parse_args()

    # One shared retriever/index for both agents (avoids rebuilding twice).
    retriever = Retriever(rebuild=True)

    print("Phase 1 → retrieval. Phase 2 → design + plans. Phase 3 → debate ...\n")
    design = DesignAgent(retriever=retriever).generate(args.requirement)
    plan_set = ArchitectAgent(retriever=retriever).generate(args.requirement)

    # Normalize all references to clean repo-relative paths before scoring/saving.
    plan_set.plans = normalize.normalize_plans(plan_set.plans)
    design.artifacts = normalize.normalize_design(design.artifacts)

    # Phase 3 — Debate: score the plans and pick the winner.
    debate = EvaluatorAgent().evaluate(plan_set.plans)

    design_path = write_design_md(design, args.out)
    json_path, md_path = write_outputs(plan_set, args.out, design=design.artifacts)
    debate_path = write_debate_md(debate, args.out)
    # fold the debate result into plans.json
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    payload["debate"] = result_to_dict(debate)
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print(f"Requirement : {plan_set.requirement}")
    print(f"Provider    : {plan_set.provider} (live={plan_set.is_live})")
    print(f"Design      : UML + {len(design.artifacts.get('api_spec', []))} API entries + "
          f"{len(design.artifacts.get('test_cases', []))} test cases")
    print(f"Plans       : {[p.get('id') for p in plan_set.plans]}")
    print(f"Debate      : winner = Plan {debate.winner_id} ({debate.winner_focus}), "
          f"margin {debate.margin}")
    print(f"\nWrote:\n  {design_path}\n  {md_path}\n  {debate_path}\n  {json_path}")
    print("\nNext:")
    print(f"  python eval/design_quality.py --design {json_path}")
    print(f"  python eval/plan_quality.py   --plans  {json_path}")
    print(f"  python eval/debate_quality.py --plans  {json_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
