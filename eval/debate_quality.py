#!/usr/bin/env python3
"""Debate-phase evaluation — proves the Evaluator chose the *right* plan.

The hard question from the project brief: "how do we prove the AI Debate node chose
the right plan?" We answer it with a **weight-sensitivity** test. Each plan archetype
should win exactly when its dimension dominates the priorities:

    weight profile          expected winning focus
    ----------------------  ----------------------
    default (context.md §7)  reuse        (reuse 0.40 + blueprint 0.30 dominate)
    performance-heavy        performance
    speed-heavy              speed
    reuse-heavy              reuse

If the Evaluator's winner matches the expectation across all profiles, the scoring
is both correct on the default priorities and provably weight-sensitive (not hard-
coded to one answer). Exit code is non-zero on any mismatch → CI-usable.

Run:
    python eval/debate_quality.py                  # uses the plans in out/plans.json
    python eval/debate_quality.py --plans p.json --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_pipeline import config  # noqa: E402
from agent_pipeline.agents.evaluator import EvaluatorAgent  # noqa: E402

DEFAULT_PLANS = config.PROJECT_ROOT / "out" / "plans.json"

PROFILES = {
    "default": (config.PRIORITY_WEIGHTS, "reuse"),
    "performance_heavy": ({"reuse": 0.1, "blueprint": 0.1, "performance": 0.7, "speed": 0.1}, "performance"),
    "speed_heavy": ({"reuse": 0.1, "blueprint": 0.1, "performance": 0.1, "speed": 0.7}, "speed"),
    "reuse_heavy": ({"reuse": 0.7, "blueprint": 0.1, "performance": 0.1, "speed": 0.1}, "reuse"),
}


def evaluate(plans: list[dict]) -> dict:
    profiles = {}
    all_pass = True
    for name, (weights, expected_focus) in PROFILES.items():
        res = EvaluatorAgent(weights).evaluate(plans)
        ok = res.winner_focus == expected_focus
        all_pass = all_pass and ok
        profiles[name] = {
            "expected_focus": expected_focus,
            "winner_id": res.winner_id,
            "winner_focus": res.winner_focus,
            "margin": res.margin,
            "ok": ok,
        }
    return {"n_plans": len(plans), "profiles": profiles, "pass": all_pass}


def _print_human(r: dict) -> None:
    print("\n=== SS6 Debate-phase quality report ===")
    print(f"plans: {r['n_plans']}")
    print(f"{'profile':<18} {'expected':<12} {'winner':<8} {'margin':>7}  result")
    for name, p in r["profiles"].items():
        mark = "PASS" if p["ok"] else "FAIL"
        print(f"{name:<18} {p['expected_focus']:<12} "
              f"{p['winner_id']}/{p['winner_focus'][:5]:<6} {p['margin']:>7}  [{mark}]")
    print(f"\nOVERALL: {'PASS' if r['pass'] else 'FAIL'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the Debate node's plan choice.")
    parser.add_argument("--plans", type=Path, default=DEFAULT_PLANS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.plans.exists():
        print(f"plans file not found: {args.plans}\nRun scripts/run_plan.py first.")
        return 2

    plans = json.loads(args.plans.read_text(encoding="utf-8"))["plans"]
    report = evaluate(plans)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human(report)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
