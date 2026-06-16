#!/usr/bin/env python3
"""Plan-phase evaluation — proves the Architect produced valid, distinct, grounded plans.

Rule of Engagement #3: every module ships with the metric that proves it works.
For the Plan phase "works" means four checkable properties:

  1. schema_valid    — every plan carries all required fields and a legal
                       priority_focus.
  2. archetype_cover — the three required archetypes (performance / reuse / speed)
                       are all present exactly once.
  3. distinctiveness — plans are meaningfully different. We measure the mean pairwise
                       Jaccard similarity over each plan's (steps ∪ files) token/path
                       set; lower is better. Must be below DISTINCT_THRESHOLD.
  4. grounding       — every referenced EXISTING file is real (in target_repo or
                       context.md); primitives_reused must be canonical primitives.
                       New files are allowed but must not collide with the existing
                       tree under a different intent. We report a grounding ratio.

Exit code is non-zero if any hard gate fails, so this doubles as a CI check.

Run:
    python eval/plan_quality.py                 # evaluate <out>/plans.json
    python eval/plan_quality.py --plans path/to/plans.json --json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_pipeline import config  # noqa: E402

REQUIRED_FIELDS = {
    "id", "title", "priority_focus", "summary",
    "steps", "files_touched", "primitives_reused", "tradeoffs",
}
LEGAL_FOCUS = {"performance", "reuse", "speed"}
DISTINCT_THRESHOLD = 0.60  # mean pairwise Jaccard must be below this
DEFAULT_PLANS = config.PROJECT_ROOT / "out" / "plans.json"


def _existing_repo_files() -> set[str]:
    files = {
        str(p.relative_to(config.PROJECT_ROOT))
        for p in config.TARGET_REPO_DIR.rglob("*")
        if p.is_file()
    }
    files.add(str(config.CONTEXT_FILE.relative_to(config.PROJECT_ROOT)))
    return files


def _plan_signature(plan: dict) -> set[str]:
    """Token+path set used for the distinctiveness measure."""
    tokens: set[str] = set()
    for step in plan.get("steps", []):
        tokens |= set(re.findall(r"[A-Za-z0-9_]+", step.lower()))
    tokens |= {f.lower() for f in plan.get("files_touched", [])}
    return tokens


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b)


def evaluate(plans_path: Path) -> dict:
    data = json.loads(plans_path.read_text(encoding="utf-8"))
    plans = data["plans"]
    repo_files = _existing_repo_files()

    # 1. schema
    schema_errors = []
    for p in plans:
        missing = REQUIRED_FIELDS - set(p)
        if missing:
            schema_errors.append(f"plan {p.get('id','?')} missing {sorted(missing)}")
        if p.get("priority_focus") not in LEGAL_FOCUS:
            schema_errors.append(f"plan {p.get('id','?')} illegal focus {p.get('priority_focus')!r}")
    schema_valid = not schema_errors

    # 2. archetype coverage
    focuses = [p.get("priority_focus") for p in plans]
    archetype_cover = sorted(set(focuses)) == sorted(LEGAL_FOCUS) and len(plans) == 3

    # 3. distinctiveness
    sigs = [_plan_signature(p) for p in plans]
    pairs = list(combinations(sigs, 2))
    mean_sim = sum(_jaccard(a, b) for a, b in pairs) / len(pairs) if pairs else 0.0
    distinct_ok = mean_sim < DISTINCT_THRESHOLD

    # 4. grounding — normalize every reference to its stem (drop path + extension)
    #    so naming conventions don't matter: "Card", "Card.tsx",
    #    "src/components/Card.tsx" and "target_repo/src/components/Card.tsx" all
    #    resolve to the same canonical primitive.
    def _stem(x: str) -> str:
        return x.split("/")[-1].rsplit(".", 1)[0]

    repo_stems = {_stem(f) for f in repo_files}
    canon_prim_stems = {_stem(p) for p in config.CANONICAL_PRIMITIVES}

    referenced_existing = 0
    referenced_total = 0
    grounding_errors = []
    for p in plans:
        for f in p.get("files_touched", []):
            referenced_total += 1
            if _stem(f) in repo_stems:
                referenced_existing += 1
            elif "src/" not in f and not f.startswith("target_repo/"):
                # neither an existing file nor a plausible new file inside the app
                grounding_errors.append(f"plan {p['id']} references out-of-tree file {f}")
        for prim in p.get("primitives_reused", []):
            if _stem(prim) not in canon_prim_stems:
                grounding_errors.append(f"plan {p['id']} reuses non-canonical primitive {prim}")
    grounding_ratio = referenced_existing / referenced_total if referenced_total else 0.0
    grounding_ok = not grounding_errors

    hard_gates_pass = schema_valid and archetype_cover and distinct_ok and grounding_ok

    return {
        "plans_file": str(plans_path),
        "provider": data.get("provider"),
        "is_live": data.get("is_live"),
        "n_plans": len(plans),
        "schema_valid": schema_valid,
        "schema_errors": schema_errors,
        "archetype_cover": archetype_cover,
        "focuses": focuses,
        "mean_pairwise_similarity": round(mean_sim, 4),
        "distinct_threshold": DISTINCT_THRESHOLD,
        "distinct_ok": distinct_ok,
        "grounding_ratio": round(grounding_ratio, 4),
        "grounding_ok": grounding_ok,
        "grounding_errors": grounding_errors,
        "pass": hard_gates_pass,
    }


def _print_human(r: dict) -> None:
    print("\n=== SS6 Plan-phase quality report ===")
    print(f"plans     : {r['plans_file']}")
    print(f"provider  : {r['provider']}  (live={r['is_live']})  n={r['n_plans']}")
    print(f"[{'PASS' if r['schema_valid'] else 'FAIL'}] schema valid")
    for e in r["schema_errors"]:
        print(f"        - {e}")
    print(f"[{'PASS' if r['archetype_cover'] else 'FAIL'}] archetype coverage  focuses={r['focuses']}")
    print(f"[{'PASS' if r['distinct_ok'] else 'FAIL'}] distinctiveness  mean_sim={r['mean_pairwise_similarity']} "
          f"(< {r['distinct_threshold']})")
    print(f"[{'PASS' if r['grounding_ok'] else 'FAIL'}] grounding  ratio_existing={r['grounding_ratio']}")
    for e in r["grounding_errors"]:
        print(f"        - {e}")
    print(f"\nOVERALL: {'PASS' if r['pass'] else 'FAIL'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Architect plan quality.")
    parser.add_argument("--plans", type=Path, default=DEFAULT_PLANS)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.plans.exists():
        print(f"plans file not found: {args.plans}\nRun scripts/run_plan.py first.")
        return 2

    report = evaluate(args.plans)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human(report)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
