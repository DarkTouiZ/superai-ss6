"""Risk-based HITL approval enforcement (spec §21).  Run: pytest -q"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from agent_pipeline import hitl
from agent_pipeline.hitl import HumanApproval


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


# --- unit: risk + approval store -------------------------------------------- #

def test_effective_risk_escalates_when_plan_touches_protected():
    impact = {"proposed_risk_level": "low", "risk_reasons": []}
    plan = {"id": "A", "files_touched": ["backend/db/migrations/005.sql"]}
    risk, reasons = hitl.effective_risk(impact, plan)
    assert risk == "high"
    assert any("protected" in r for r in reasons)


def test_requires_approval_by_level():
    assert hitl.requires_pre_execution_approval("low") is False
    assert hitl.requires_pre_execution_approval("medium") is True
    assert hitl.requires_pre_execution_approval("high") is True


def test_record_and_load_roundtrip(tmp_path):
    hitl.record_approval(tmp_path, HumanApproval(
        stage="plan", decision="approved", approved_by="Safe",
        packet_version=1, plan_id="B", environment_version=1, risk_level="high"))
    loaded = hitl.load_approvals(tmp_path)
    assert len(loaded) == 1 and loaded[0].approved_by == "Safe"


def test_matching_requires_same_packet_plan_env_and_risk(tmp_path):
    hitl.record_approval(tmp_path, HumanApproval(
        stage="plan", decision="approved", approved_by="Safe",
        packet_version=1, plan_id="B", environment_version=1, risk_level="high"))
    apps = hitl.load_approvals(tmp_path)
    # exact match works
    assert hitl.find_matching_approval(apps, packet_version=1, plan_id="B",
                                       environment_version=1, risk_level="high")
    # stale packet version is NOT authorized (spec §21.2)
    assert hitl.find_matching_approval(apps, packet_version=2, plan_id="B",
                                       environment_version=1, risk_level="high") is None
    # a high-risk change is not covered by... wait, this approval IS high; lower risk is covered
    assert hitl.find_matching_approval(apps, packet_version=1, plan_id="B",
                                       environment_version=1, risk_level="medium")


def test_check_execution_allowed_blocks_then_allows(tmp_path):
    impact = {"proposed_risk_level": "high", "risk_reasons": ["schema"]}
    plan = {"id": "B", "files_touched": ["backend/src/services/x.ts"]}
    blocked = hitl.check_execution_allowed(tmp_path, impact=impact, chosen_plan=plan,
                                           packet_version=1, environment_version=1)
    assert blocked.required and blocked.blocked
    hitl.record_approval(tmp_path, HumanApproval(
        stage="plan", decision="approved", approved_by="Safe",
        packet_version=1, plan_id="B", environment_version=1, risk_level="high"))
    allowed = hitl.check_execution_allowed(tmp_path, impact=impact, chosen_plan=plan,
                                           packet_version=1, environment_version=1)
    assert allowed.approved and not allowed.blocked


def test_low_risk_not_required(tmp_path):
    impact = {"proposed_risk_level": "low", "risk_reasons": []}
    plan = {"id": "A", "files_touched": ["docs/readme.md"]}
    chk = hitl.check_execution_allowed(tmp_path, impact=impact, chosen_plan=plan,
                                       packet_version=1, environment_version=1)
    assert not chk.required and chk.approved and not chk.blocked


# --- integration: api.execute gate ------------------------------------------ #
pytestmark = pytest.mark.skipif(not _git_available(), reason="git not installed")

_HIGH_PAYLOAD = {
    "requirement": "add analytics endpoint",
    "plans": [{"id": "B", "priority_focus": "reuse", "summary": "s", "steps": ["a"],
               "files_touched": ["backend/src/services/analytics.ts"],
               "primitives_reused": [], "tradeoffs": {"pros": ["p"], "cons": ["c"]}}],
    "debate": {"winner_id": "B"},
    "impact": {"proposed_risk_level": "high", "risk_reasons": ["schema-sensitive"]},
    "problem_packet": {"version": 1},
    "environment": {"environment_version": 1},
}


def test_execute_blocks_high_risk_without_approval(tmp_path):
    from agent_pipeline import api
    res = api.execute(dict(_HIGH_PAYLOAD), out_dir=tmp_path, require_approval=True)
    assert res.get("approval_blocked") is True
    assert "branch" not in res                 # the Developer never ran
    assert res["risk_level"] == "high"


def test_execute_proceeds_after_recorded_approval(tmp_path):
    from agent_pipeline import api
    api.approve(dict(_HIGH_PAYLOAD), plan_id="B", approved_by="Safe", out_dir=tmp_path)
    res = api.execute(dict(_HIGH_PAYLOAD), out_dir=tmp_path, require_approval=True)
    assert not res.get("approval_blocked")
    assert res["branch"].startswith("ss6/")
    assert res["approval"]["pre_execution_approval_recorded"] is True


def test_execute_inline_approved_by_proceeds(tmp_path):
    from agent_pipeline import api
    res = api.execute(dict(_HIGH_PAYLOAD), out_dir=tmp_path, require_approval=True,
                      approved_by="Safe")
    assert not res.get("approval_blocked")
    assert res["branch"].startswith("ss6/")


def test_execute_backward_compatible_without_enforcement(tmp_path):
    from agent_pipeline import api
    res = api.execute(dict(_HIGH_PAYLOAD), out_dir=tmp_path)   # require_approval defaults False
    assert not res.get("approval_blocked")
    assert res["branch"].startswith("ss6/")


def test_stale_packet_version_invalidates_approval(tmp_path):
    from agent_pipeline import api
    api.approve(dict(_HIGH_PAYLOAD), plan_id="B", approved_by="Safe", out_dir=tmp_path)
    bumped = dict(_HIGH_PAYLOAD, problem_packet={"version": 2})   # materially changed packet
    res = api.execute(bumped, out_dir=tmp_path, require_approval=True)
    assert res.get("approval_blocked") is True    # old approval no longer authorizes
