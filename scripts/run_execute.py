#!/usr/bin/env python3
"""Phase 3b + 4 entrypoint: implement the winning plan, then test & halt for HITL.

Reads out/plans.json (winner from the Debate + design), generates code on an
isolated git branch, runs the compliance suite, writes REVIEW.md, and STOPS for
human approval. Nothing is merged automatically.

Usage:
    python scripts/run_execute.py
    python scripts/run_execute.py --plans out/plans.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_pipeline import config  # noqa: E402
from agent_pipeline.agents.developer import DeveloperAgent  # noqa: E402
from agent_pipeline.review import review_files, write_review_md  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Execute + Review phases.")
    parser.add_argument("--plans", type=Path, default=config.PROJECT_ROOT / "out" / "plans.json")
    parser.add_argument("--out", type=Path, default=config.PROJECT_ROOT / "out")
    args = parser.parse_args()

    if not args.plans.exists():
        print(f"plans file not found: {args.plans}\nRun scripts/run_plan.py first.")
        return 2

    data = json.loads(args.plans.read_text(encoding="utf-8"))
    plans = data["plans"]
    design = data.get("design", {})
    requirement = data.get("requirement", "")
    winner_id = data.get("debate", {}).get("winner_id")
    if not winner_id:
        print("No debate winner in plans.json — run scripts/run_plan.py (Phase 3) first.")
        return 2
    winner = next(p for p in plans if p.get("id") == winner_id)

    print(f"Executing winning Plan {winner_id} ({winner.get('priority_focus')}) ...\n")
    exec_result = DeveloperAgent().execute(requirement, winner, design)
    review = review_files(exec_result.files)
    review_path = write_review_md(exec_result, review, args.out)

    print(f"Provider     : {exec_result.provider} (live={exec_result.is_live})")
    print(f"Branch       : {exec_result.branch}")
    print(f"Changed files: {', '.join(exec_result.changed_files) or '—'}")
    print(f"Compliance   : {'PASS' if review.passed else 'FAIL'} "
          f"({review.n_violations} violation(s))")
    for fr in review.files:
        for v in fr.violations:
            print(f"   ❌ {fr.path}: {v}")
    print(f"\nWrote {review_path}")
    if review.passed:
        print("\n⏸  HALTED for human review. Nothing merged. See REVIEW.md for the diff "
              "and your approve/reject options.")
    else:
        print("\n⛔ Compliance failed — not advancing to human review. Adjust the plan and re-run.")
    return 0 if review.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
