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
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
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


def _executed_diff_stats(review: dict) -> tuple[int, int]:
    """LOC + files from the EXACT executed candidate (the committed diff in the isolated
    copy), not a second generation call (spec §22.5). Returns (added_loc, n_files)."""
    wd, br = review.get("workdir"), review.get("branch")
    changed = review.get("changed_files") or []
    if not wd or not br:
        return 0, len(changed)
    try:
        out = subprocess.run(["git", "-C", wd, "diff", "--numstat", f"main..{br}"],
                             capture_output=True, text=True, timeout=30)
        added = 0
        for line in out.stdout.splitlines():
            parts = line.split("\t")
            if parts and parts[0].isdigit():
                added += int(parts[0])
        return added, len(changed)
    except Exception:
        return 0, len(changed)


def run(run_tests: bool = False) -> dict:
    rows = []
    run_id = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for req in REQUIREMENTS:
        t0 = time.time()
        payload = api.plan(req)
        review = api.execute(payload, run_tests=run_tests)  # gate + repair loop
        # Count from the EXACT executed candidate (committed diff), not a re-generation.
        loc, n_files = _executed_diff_stats(review)
        rows.append({
            "requirement": req,
            "winner": f'{payload["debate"]["winner_id"]}/{payload["debate"]["winner_focus"]}',
            "provider": review.get("provider"),
            "is_live": review.get("is_live", False),
            "risk_level": review.get("risk_level"),
            "environment_version": (payload.get("environment") or {}).get("environment_version"),
            "candidate_files": len(payload["candidate_files"]),
            "files_drafted": n_files,
            "loc_drafted": loc,
            "compliance_passed": review["compliance_passed"],
            "attempts": review.get("attempts", 1),
            "repaired": review.get("repaired", False),
            "gate_passed": review.get("gate_passed", review["compliance_passed"]),
            "seconds": round(time.time() - t0, 2),
        })

    n = len(rows)
    passed = sum(1 for r in rows if r["gate_passed"])
    providers = sorted({r.get("provider") for r in rows})
    any_live = any(r.get("is_live") for r in rows)
    requested = os.getenv("SS6_LLM_PROVIDER", "auto")
    locs = [r["loc_drafted"] for r in rows]
    summary = {
        "run_id": run_id,
        "requirements": n,
        # NAME MADE EXPLICIT (spec §22.5): this is gate-pass CONSISTENCY, not proof each
        # distinct requirement was correctly implemented — on the mock the Developer emits
        # a constant template regardless of the requirement string.
        "gate_pass_consistency_rate": round(100.0 * passed / n, 1),
        "measures": "consistency + productivity proxy on a deterministic template — "
                    "NOT requirement-satisfaction; use a live provider + oracle for that",
        "provider": providers[0] if len(providers) == 1 else providers,
        "is_live": any_live,
        "live_requested": requested not in ("mock", "auto"),
        "live_requested_but_mock": (requested not in ("mock", "auto")) and not any_live,
        "mock_output_constant": not any_live,
        "mean_attempts": round(sum(r["attempts"] for r in rows) / n, 2),
        "repaired_count": sum(1 for r in rows if r["repaired"]),
        "total_loc_drafted": sum(locs),
        "mean_loc_drafted": round(sum(locs) / n, 1),
        "loc_min_max": [min(locs), max(locs)],
        "mean_files_drafted": round(sum(r["files_drafted"] for r in rows) / n, 1),
        "mean_seconds": round(sum(r["seconds"] for r in rows) / n, 2),
        "real_gate": bool(run_tests),
    }
    return {"summary": summary, "rows": rows}


def write_reports(result: dict) -> None:
    out = config.PROJECT_ROOT / "out"
    out.mkdir(exist_ok=True)
    (out / "impact.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    s = result["summary"]
    live_note = ""
    if s.get("live_requested_but_mock"):
        live_note = ("\n> ⚠️ A live provider was requested but the run fell back to the mock; "
                     "these are NOT live-quality results. Set `SS6_STRICT=1` to fail instead.")
    lines = [
        "# IMPACT.md — SS6 gate-pass **consistency** benchmark (not requirement-satisfaction)",
        "",
        f"Run `{s['run_id']}` · provider `{s['provider']}` (live={s['is_live']}) · "
        f"{s['requirements']} requirements.",
        "",
        "> **What this measures:** on the deterministic mock the Developer emits a *constant*"
        " vertical-slice template regardless of the requirement string, so a green gate on"
        " every row demonstrates **consistency + a productivity proxy (lines drafted)**, NOT"
        " that each distinct requirement was correctly implemented. A requirement-satisfaction"
        f" claim needs a live provider and a per-requirement oracle." + live_note,
        "",
        f"- **Gate-pass consistency:** {s['gate_pass_consistency_rate']}% (compliant"
        f"{' + tsc/jest green' if s.get('real_gate') else ''} on every run)",
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
        f"_LOC/files are counted from the exact executed candidate (committed diff), not a "
        f"re-generation. Per-requirement LOC range: {s.get('loc_min_max')}._",
    ]
    (config.PROJECT_ROOT / "eval" / "IMPACT.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    result = run()
    write_reports(result)
    s = result["summary"]
    print(f"requirements      : {s['requirements']}  (provider={s['provider']}, live={s['is_live']})")
    print(f"gate consistency  : {s['gate_pass_consistency_rate']}%" + (" (incl. tsc/jest)" if s.get('real_gate') else "")
          + "  [consistency, NOT requirement-satisfaction]")
    print(f"mean gate attempts: {s.get('mean_attempts')} ({s.get('repaired_count')} repaired)")
    print(f"mean LOC drafted  : {s['mean_loc_drafted']} over {s['mean_files_drafted']} files")
    print(f"mean seconds/req  : {s['mean_seconds']}")
    print(f"\nWrote eval/IMPACT.md and out/impact.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
