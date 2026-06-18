"""Roadmap M4/M6/M7 tests: clarification step, evidence scoring, debate wording
invariance, and per-phase tracing.  Run: pytest -q"""
import copy
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from agent_pipeline import api
from agent_pipeline.review import evidence_from_files


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


# ---- M7: clarification step (no git / no execution needed) ----
def test_needs_clarification_flags_vague_requirements():
    assert api.needs_clarification("make it better")        # vague
    assert api.needs_clarification("fix")                   # too short
    assert not api.needs_clarification("Add a daily revenue-by-store report endpoint")


def test_run_allow_clarify_short_circuits_without_executing():
    out = api.run("improve stuff", allow_clarify=True)
    assert "needs_clarification" in out
    assert "review" not in out  # it must NOT have run the pipeline


# ---- M6: evidence is computed from actual code, not plan prose ----
def test_evidence_reports_reused_components():
    files = [{
        "path": "frontend/src/app/features/x/x.component.ts",
        "content": "import { CardComponent } from '../../shared/components/card/card.component';\n"
                   "import { ApiService } from '../../core/services/api.service';\n"
                   "export class X {}",
    }]
    ev = evidence_from_files(files)
    assert "CardComponent" in ev["reused_components"]
    assert "ApiService" in ev["reused_components"]
    assert ev["n_files"] == 1


# ---- M6: the debate winner does not depend on the losers' wording ----
@pytest.mark.skipif(not _git_available(), reason="git not installed")
def test_debate_winner_is_wording_invariant():
    payload = api.plan("Add a Top Customers by Spend analytics endpoint")
    winner = payload["debate"]["winner_id"]
    plans = copy.deepcopy(payload["plans"])
    for p in plans:                      # scramble the *losers'* wording only
        if p["id"] != winner:
            p["summary"] = "zzz " + p.get("summary", "")[::-1]
            p["steps"] = [s[::-1] for s in p.get("steps", [])]
    assert api.debate({"plans": plans})["winner_id"] == winner


# ---- M6: winner is invariant to plan ORDER (no positional bias) ----
@pytest.mark.skipif(not _git_available(), reason="git not installed")
def test_debate_winner_is_order_invariant():
    payload = api.plan("Add a Top Customers by Spend analytics endpoint")
    winner = payload["debate"]["winner_id"]
    reordered = list(reversed(payload["plans"]))
    assert api.debate({"plans": reordered})["winner_id"] == winner


# ---- M6: the executed change validates the winner's claimed focus ----
@pytest.mark.skipif(not _git_available(), reason="git not installed")
def test_winner_validated_against_execution_evidence():
    out = api.run("Add a Top Customers by Spend analytics endpoint")
    rev = out["review"]
    assert "winner_validated" in rev
    assert rev["winner_validated"] is True  # mock slice reuses repo+service layering
    assert "winner_validated" in rev["evidence"]


# ---- M7: per-phase tracing is attached to a full run ----
@pytest.mark.skipif(not _git_available(), reason="git not installed")
def test_run_includes_trace():
    out = api.run("Add a top customers screen")
    assert "trace" in out
    assert out["trace"]["total_seconds"] >= 0
    assert "evidence" in out["review"]
