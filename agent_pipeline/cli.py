"""``ss6`` command-line interface for the SuperAI SS6 pipeline.

Installed as a console script (see pyproject.toml):

    ss6 rag "how is a delivery fee computed?"          # Phase 1 retrieval
    ss6 plan "Add a top-customers-by-spend screen"     # Phases 1-3 -> writes out/
    ss6 debate --plans out/plans.json                  # re-score plans
    ss6 execute --plans out/plans.json                 # Phases 3b-4 -> REVIEW.md (halts)
    ss6 run "Add ALL Member points redemption"         # whole loop
    ss6 eval [rag|plan|debate|design|execution]        # run an eval harness
    ss6 version

Provider is selected with SS6_LLM_PROVIDER=auto|anthropic|gemini|ollama|mock.
"""
from __future__ import annotations

import argparse
import json
import runpy
import sys
from pathlib import Path

from agent_pipeline import __version__, api, config


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def _cmd_rag(args: argparse.Namespace) -> int:
    _print({"requirement": args.requirement, "paths": api.retrieve(args.requirement, top_k=args.k)})
    return 0


def _cmd_plan(args: argparse.Namespace) -> int:
    payload = api.plan(args.requirement, out_dir=args.out)
    d = payload["debate"]
    print(f"Provider : {payload['provider']} (live={payload['is_live']})")
    print(f"Plans    : {[p.get('id') for p in payload['plans']]}")
    print(f"Winner   : Plan {d['winner_id']} ({d['winner_focus']}) — margin {d['margin']}")
    print(f"Artifacts: {args.out}/DESIGN.md, PLANS.md, DEBATE.md, plans.json")
    return 0


def _cmd_debate(args: argparse.Namespace) -> int:
    weights = json.loads(args.weights) if args.weights else None
    _print(api.debate(args.plans, weights=weights))
    return 0


def _cmd_execute(args: argparse.Namespace) -> int:
    review = api.execute(args.plans, out_dir=args.out, run_tests=args.run_tests)
    print(f"Branch     : {review['branch']}")
    print(f"Changed    : {', '.join(review['changed_files']) or '—'}")
    print(f"Compliance : {'PASS' if review['compliance_passed'] else 'FAIL'}")
    for v in review["violations"]:
        print(f"   ❌ {v}")
    for t in review.get("tests", []):
        print(f"   {t['result'].upper():8} {t['name']} (real check)")
    if review.get("tests_run"):
        print(f"Gate       : {'PASS' if review['gate_passed'] else 'FAIL'} (compliance + tsc + jest)")
    print(f"\n⏸  Halted for human review. See {args.out}/REVIEW.md — nothing merged.")
    return 0 if review.get("gate_passed", review["compliance_passed"]) else 1


def _cmd_run(args: argparse.Namespace) -> int:
    result = api.run(args.requirement, out_dir=args.out, run_tests=args.run_tests)
    d = result["plan"]["debate"]
    r = result["review"]
    print(f"Winner     : Plan {d['winner_id']} ({d['winner_focus']})")
    print(f"Branch     : {r['branch']}")
    for t in r.get("tests", []):
        print(f"   {t['result'].upper():8} {t['name']} (real check)")
    passed = r.get("gate_passed", r["compliance_passed"])
    print(f"Gate       : {'PASS' if passed else 'FAIL'}")
    print(f"⏸  Halted for human review. Artifacts in {args.out}/")
    return 0 if passed else 1


_EVALS = {
    "rag": "eval/recall_at_k.py",
    "plan": "eval/plan_quality.py",
    "debate": "eval/debate_quality.py",
    "design": "eval/design_quality.py",
    "execution": "eval/execution_quality.py",
}


def _cmd_eval(args: argparse.Namespace) -> int:
    script = config.PROJECT_ROOT / _EVALS[args.harness]
    sys.argv = [str(script)] + args.extra
    runpy.run_path(str(script), run_name="__main__")
    return 0


def _cmd_version(_args: argparse.Namespace) -> int:
    print(f"ss6 {__version__}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ss6", description="SuperAI SS6 autonomous SWE pipeline")
    sub = p.add_subparsers(dest="command", required=True)

    pr = sub.add_parser("rag", help="Phase 1: retrieve relevant repo files")
    pr.add_argument("requirement")
    pr.add_argument("-k", type=int, default=config.DEFAULT_TOP_K)
    pr.set_defaults(func=_cmd_rag)

    pp = sub.add_parser("plan", help="Phases 1-3: design + plans + debate")
    pp.add_argument("requirement")
    pp.add_argument("--out", type=Path, default=config.PROJECT_ROOT / "out")
    pp.set_defaults(func=_cmd_plan)

    pd = sub.add_parser("debate", help="Phase 3: (re)score plans")
    pd.add_argument("--plans", type=Path, default=config.PROJECT_ROOT / "out" / "plans.json")
    pd.add_argument("--weights", help='JSON, e.g. {"performance":0.5,"reuse":0.2,"blueprint":0.2,"speed":0.1}')
    pd.set_defaults(func=_cmd_debate)

    pe = sub.add_parser("execute", help="Phases 3b-4: implement winner + compliance, halt")
    pe.add_argument("--plans", type=Path, default=config.PROJECT_ROOT / "out" / "plans.json")
    pe.add_argument("--out", type=Path, default=config.PROJECT_ROOT / "out")
    pe.add_argument("--run-tests", action="store_true", help="also run the repo's real tsc + jest in the isolated copy")
    pe.set_defaults(func=_cmd_execute)

    pn = sub.add_parser("run", help="whole loop: plan -> execute")
    pn.add_argument("requirement")
    pn.add_argument("--out", type=Path, default=config.PROJECT_ROOT / "out")
    pn.add_argument("--run-tests", action="store_true", help="also run the repo's real tsc + jest in the isolated copy")
    pn.set_defaults(func=_cmd_run)

    pv = sub.add_parser("eval", help="run an eval harness")
    pv.add_argument("harness", choices=list(_EVALS))
    pv.add_argument("extra", nargs=argparse.REMAINDER, help="args passed through to the harness")
    pv.set_defaults(func=_cmd_eval)

    sub.add_parser("version", help="print version").set_defaults(func=_cmd_version)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
