#!/usr/bin/env python3
"""Phase 3 entrypoint: score the plans in out/plans.json and pick the winner.

Usage:
    python scripts/run_debate.py
    python scripts/run_debate.py --plans out/plans.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_pipeline import config  # noqa: E402
from agent_pipeline.agents.evaluator import EvaluatorAgent, result_to_dict, write_debate_md  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Debate phase.")
    parser.add_argument("--plans", type=Path, default=config.PROJECT_ROOT / "out" / "plans.json")
    parser.add_argument("--out", type=Path, default=config.PROJECT_ROOT / "out")
    args = parser.parse_args()

    if not args.plans.exists():
        print(f"plans file not found: {args.plans}\nRun scripts/run_plan.py first.")
        return 2

    plans = json.loads(args.plans.read_text(encoding="utf-8"))["plans"]
    res = EvaluatorAgent().evaluate(plans)
    md_path = write_debate_md(res, args.out)

    print(res.rationale)
    print("\nRanking:")
    for s in res.ranking:
        print(f"  Plan {s.plan_id} ({s.focus:<11}) weighted={s.weighted_total:.3f}  "
              f"reuse={s.subscores['reuse']:.2f} bp={s.subscores['blueprint']:.2f} "
              f"perf={s.subscores['performance']:.2f} speed={s.subscores['speed']:.2f}")
    print(f"\nWrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
