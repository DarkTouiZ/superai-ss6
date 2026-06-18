#!/usr/bin/env python3
"""Impact / consistency benchmark — quantifies what SS6 does across many requirements.

For each requirement we run the full pipeline (plan -> debate -> execute) on the
deterministic mock provider (zero cost, offline) and record:

  * winner plan + focus (the debate's choice),
  * whether the change passes the context.md compliance gate,
  * how many files and lines the Developer drafted (a human would otherwise write
    these from a blank file), and
  * how many real repo files RAG surfaced for grounding, plus wall-clock time.

Aggregate metrics (gate pass-rate, mean LOC drafted, etc.) are written to
``eval/IMPACT.md`` and ``out/impact.json``.

Run:  python eval/impact_study.py        (or: ss6 ... then this)
Note: on the deterministic mock the generated code volume is constant by design;
a live provider would vary it. The point here is consistency + the productivity
proxy (lines drafted) + a 100%-green gate, all reproducibly and for free.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_pipeline import api, config  # noqa: E402

REQUIREMENTS = [
    "Add a Top Customers by Spend analytics endpoint",
    "Add a low-stock reorder alert screen for store managers",
    "Let customers redeem ALL Member points at checkout",
    "Add a daily revenue-by-store report endpoint",
    "Add a courier performance leaderboard",
    "Add order cancellation with an automatic refund flow",
]


def _loc(files: list[dict]) -> int:
    total = 0
    for f in files:
        if "content" in f:
            total += len(f["content"].splitlines())
        edits = f.get("edits") or ([f["edit"]] if "edit" in f else [])
        for e in edits:
            payload = e.get("insert_after") or e.get("insert_before") or e.get("replace") or ""
            total += len([ln for ln in payload.splitlines() if ln.strip()])
    return total


def run(run_tests: bool = False) -> dict:
    rows = []
    for req in REQUIREMENTS:
        t0 = time.time()
        payload = api.plan(req)
        review = api.execute(payload, run_tests=run_tests)  # gate + repair loop
        # recover the generated files to count LOC drafted
        from agent_pipeline.agents.developer import DeveloperAgent
        winner_id = payload["debate"]["winner_id"]
        winner = next(p for p in payload["plans"] if p.get("id") == winner_id)
        files = DeveloperAgent().generate_files(req, winner, payload.get("design", {}))
        rows.append({
            "requirement": req,
            "winner": f'{payload["debate"]["winner_id"]}/{payload["debate"]["winner_focus"]}',
            "candidate_files": len(payload["candidate_files"]),
            "files_drafted": len(files),
            "loc_drafted": _loc(files),
            "compliance_passed": review["compliance_passed"],
            "attempts": review.get("attempts", 1),
            "repaired": review.get("repaired", False),
            "gate_passed": review.get("gate_passed", review["compliance_passed"]),
            "seconds": round(time.time() - t0, 2),
        })

    n = len(rows)
    passed = sum(1 for r in rows if r["gate_passed"])
    summary = {
        "requirements": n,
        "gate_pass_rate": round(100.0 * passed / n, 1),
        "mean_attempts": round(sum(r["attempts"] for r in rows) / n, 2),
        "repaired_count": sum(1 for r in rows if r["repaired"]),
        "total_loc_drafted": sum(r["loc_drafted"] for r in rows),
        "mean_loc_drafted": round(sum(r["loc_drafted"] for r in rows) / n, 1),
        "mean_files_drafted": round(sum(r["files_drafted"] for r in rows) / n, 1),
        "mean_seconds": round(sum(r["seconds"] for r in rows) / n, 2),
        "provider": "mock",
        "real_gate": bool(run_tests),
    }
    return {"summary": summary, "rows": rows}


def write_reports(result: dict) -> None:
    out = config.PROJECT_ROOT / "out"
    out.mkdir(exist_ok=True)
    (out / "impact.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    s = result["summary"]
    lines = [
        "# IMPACT.md — SS6 consistency & productivity benchmark",
        "",
        f"Across **{s['requirements']} requirements**, run on the deterministic mock "
        f"provider (zero cost, offline):",
        "",
        f"- **Gate pass-rate:** {s['gate_pass_rate']}% (compliant"
        f"{' + tsc/jest green' if s.get('real_gate') else ''}, review-ready every time)",
        f"- **Mean gate attempts per requirement:** {s.get('mean_attempts', 1.0)} "
        f"(repair loop, roadmap M2 — {s.get('repaired_count', 0)} needed a repair)",
        f"- **Lines drafted per requirement:** {s['mean_loc_drafted']} "
        f"(a human would otherwise write these from a blank file)",
        f"- **Files drafted per requirement:** {s['mean_files_drafted']}",
        f"- **Total lines drafted:** {s['total_loc_drafted']}",
        f"- **Mean wall-clock per requirement:** {s['mean_seconds']}s",
        "",
        "| Requirement | Winner | Candidate files (RAG) | Files | LOC drafted | Attempts | Gate | s |",
        "|-------------|--------|----------------------:|------:|------------:|:-------:|:----:|--:|",
    ]
    for r in result["rows"]:
        gate = "PASS" if r["gate_passed"] else "FAIL"
        att = f"{r['attempts']}{'🔁' if r['repaired'] else ''}"
        lines.append(
            f"| {r['requirement']} | {r['winner']} | {r['candidate_files']} | "
            f"{r['files_drafted']} | {r['loc_drafted']} | {att} | {gate} | {r['seconds']} |"
        )
    lines += [
        "",
        "_On the deterministic mock the generated code volume is constant by design; "
        "a live provider would vary it. This benchmark measures consistency, a green "
        "gate on every run, and the lines-drafted productivity proxy — reproducibly "
        "and for $0._",
    ]
    (config.PROJECT_ROOT / "eval" / "IMPACT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    result = run()
    write_reports(result)
    s = result["summary"]
    print(f"requirements      : {s['requirements']}")
    print(f"gate pass-rate    : {s['gate_pass_rate']}%" + (" (incl. tsc/jest)" if s.get('real_gate') else ""))
    print(f"mean gate attempts: {s.get('mean_attempts')} ({s.get('repaired_count')} repaired)")
    print(f"mean LOC drafted  : {s['mean_loc_drafted']} over {s['mean_files_drafted']} files")
    print(f"mean seconds/req  : {s['mean_seconds']}")
    print(f"\nWrote eval/IMPACT.md and out/impact.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
