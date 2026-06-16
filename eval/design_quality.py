#!/usr/bin/env python3
"""Design-phase evaluation — proves the DesignAgent produced complete, valid,
grounded artifacts (Rule of Engagement #3: every module ships with its metric).

Hard gates (exit non-zero on failure → CI-usable):

  1. completeness  — all required design fields present and non-empty.
  2. uml_sane      — uml_mermaid starts with a known Mermaid diagram type and has
                     at least one relationship/edge or class line (cheap syntactic
                     check; we don't run a full Mermaid parser in the MVP).
  3. tests_cover   — at least one functional AND one non_functional test case.
  4. grounding     — primitives_reused are canonical primitives; services_used map
                     to real files in target_repo. Reports a grounding ratio.

Run:
    python eval/design_quality.py                      # reads out/plans.json design
    python eval/design_quality.py --design path.json --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_pipeline import config  # noqa: E402

DEFAULT_SRC = config.PROJECT_ROOT / "out" / "plans.json"
REQUIRED_FIELDS = {
    "requirement", "uml_mermaid", "api_spec", "test_cases",
    "ux_notes", "architecture_notes",
}
MERMAID_TYPES = ("classDiagram", "sequenceDiagram", "flowchart", "graph", "erDiagram")


def _existing_repo_files() -> set[str]:
    return {
        str(p.relative_to(config.PROJECT_ROOT))
        for p in config.TARGET_REPO_DIR.rglob("*")
        if p.is_file()
    }


def _load_design(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    # accept either a raw design dict or a plans.json carrying a "design" key
    return data["design"] if "design" in data else data


def _pbase(ref: str) -> str:
    """Normalize a primitive/file reference to a comparable base name.

    Handles eleven-7 Angular components ('card.component.ts' -> 'card') as well as
    plain '.ts'/'.tsx'/'.scss' files. Robust to bare names ('card') too.
    """
    name = ref.split("/")[-1]
    for suffix in (".component.ts", ".component.tsx", ".tsx", ".ts", ".scss"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name


def evaluate(design: dict) -> dict:
    repo_files = _existing_repo_files()
    prim_names = {_pbase(p) for p in config.CANONICAL_PRIMITIVES}

    # 1. completeness
    missing = [f for f in REQUIRED_FIELDS if not design.get(f)]
    completeness = not missing

    # 2. uml sanity
    uml = (design.get("uml_mermaid") or "").strip()
    uml_typed = uml.startswith(MERMAID_TYPES)
    uml_has_body = any(tok in uml for tok in ("-->", "--", "class ", ":", "->>"))
    uml_sane = uml_typed and uml_has_body

    # 3. test coverage
    types = {tc.get("type") for tc in design.get("test_cases", []) if isinstance(tc, dict)}
    tests_cover = "functional" in types and "non_functional" in types

    # 4. grounding
    grounding_errors = []
    prims = design.get("primitives_reused", [])
    for p in prims:
        if _pbase(p) not in prim_names:
            grounding_errors.append(f"non-canonical primitive: {p}")
    services = design.get("services_used", [])
    svc_hits = 0
    for s in services:
        base = _pbase(s)
        if any(base in f for f in repo_files):
            svc_hits += 1
        else:
            grounding_errors.append(f"unknown service: {s}")
    denom = (len(prims) + len(services)) or 1
    grounding_ratio = (len([p for p in prims if _pbase(p) in prim_names]) + svc_hits) / denom
    grounding_ok = not grounding_errors

    hard_pass = completeness and uml_sane and tests_cover and grounding_ok
    return {
        "completeness": completeness,
        "missing_fields": missing,
        "uml_sane": uml_sane,
        "uml_typed": uml_typed,
        "n_api_spec": len(design.get("api_spec", [])),
        "n_test_cases": len(design.get("test_cases", [])),
        "test_types": sorted(t for t in types if t),
        "tests_cover": tests_cover,
        "grounding_ratio": round(grounding_ratio, 4),
        "grounding_ok": grounding_ok,
        "grounding_errors": grounding_errors,
        "pass": hard_pass,
    }


def _print_human(r: dict) -> None:
    print("\n=== SS6 Design-phase quality report ===")
    print(f"[{'PASS' if r['completeness'] else 'FAIL'}] completeness"
          + (f"  missing={r['missing_fields']}" if r["missing_fields"] else ""))
    print(f"[{'PASS' if r['uml_sane'] else 'FAIL'}] UML sane  (typed={r['uml_typed']})")
    print(f"[{'PASS' if r['tests_cover'] else 'FAIL'}] test coverage  "
          f"types={r['test_types']}  count={r['n_test_cases']}  api_spec={r['n_api_spec']}")
    print(f"[{'PASS' if r['grounding_ok'] else 'FAIL'}] grounding  ratio={r['grounding_ratio']}")
    for e in r["grounding_errors"]:
        print(f"        - {e}")
    print(f"\nOVERALL: {'PASS' if r['pass'] else 'FAIL'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate DesignAgent artifact quality.")
    parser.add_argument("--design", type=Path, default=DEFAULT_SRC)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.design.exists():
        print(f"design source not found: {args.design}\nRun scripts/run_plan.py first.")
        return 2

    report = evaluate(_load_design(args.design))
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human(report)
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
