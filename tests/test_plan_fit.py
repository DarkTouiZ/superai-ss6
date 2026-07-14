"""Packet-aware plan assessment: user-fit + system-fit (spec §10.3, §18.9)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_pipeline import intake
from agent_pipeline.agents import evaluator as ev


def _packet():
    return intake.ProblemPacket(
        feature_title="Top customers", user_requirement="rank customers by spend",
        user_goal_or_pain="manual pivots", desired_outcome="endpoint returns ranked customers",
        acceptance_criteria=[
            "endpoint returns customers ordered by total spend",
            "existing dashboard APIs still pass their tests",
        ],
    )


def test_criterion_coverage_detects_overlap():
    plan = {"summary": "Add a service that ranks customers by total spend",
            "steps": ["query orders", "aggregate spend per customer"],
            "files_touched": ["backend/src/services/analytics.ts"]}
    cov = ev.criterion_coverage("endpoint returns customers ordered by total spend", plan)
    assert cov["covered"] is True
    assert cov["evidence"]


def test_criterion_not_covered_when_unrelated():
    plan = {"summary": "Change button color", "steps": ["edit tokens"], "files_touched": []}
    cov = ev.criterion_coverage("endpoint returns customers ordered by total spend", plan)
    assert cov["covered"] is False


def test_system_fit_flags_controller_without_service():
    ok, reasons = ev.system_fit({"files_touched": ["backend/src/controllers/x.ts"]})
    assert ok is False
    assert any("service" in r for r in reasons)


def test_system_fit_passes_balanced_slice():
    ok, reasons = ev.system_fit({"files_touched": [
        "backend/src/services/a.ts", "backend/src/repositories/a.ts",
        "backend/src/controllers/a.ts"]})
    assert ok is True and reasons == []


def test_enrich_plan_adds_packet_fields():
    plan = {"id": "B", "summary": "rank customers by total spend via a service",
            "steps": ["aggregate spend"], "files_touched": [
                "backend/src/services/analytics.ts", "backend/src/repositories/analyticsRepository.ts"]}
    ev.enrich_plan(plan, _packet(), impact={"proposed_risk_level": "medium"})
    for key in ("acceptance_criteria_covered", "constraints_addressed", "evaluation_strategy",
                "human_decision_points", "assumptions", "rollback_strategy", "packet_fit"):
        assert key in plan
    assert 0.0 <= plan["packet_fit"]["acceptance_coverage"] <= 1.0
    assert isinstance(plan["packet_fit"]["user_fit_pass"], bool)
    assert plan["packet_fit"]["system_fit_pass"] is True


def test_assess_plans_summary_shape():
    plans = [{"id": "A", "summary": "rank customers by spend", "steps": [], "files_touched": []},
             {"id": "B", "summary": "compose primitives", "steps": [], "files_touched": []}]
    summary = ev.assess_plans(plans, _packet())
    assert summary["packet_aware"] is True
    assert {p["id"] for p in summary["plans"]} == {"A", "B"}


def test_score_plan_backward_compatible_with_packet_arg():
    plan = {"id": "B", "priority_focus": "reuse", "summary": "s", "steps": ["a"],
            "primitives_reused": [], "files_touched": []}
    base = ev.score_plan(plan)
    with_packet = ev.score_plan(plan, packet=_packet())
    assert base == with_packet          # packet must not change the deterministic base score


def test_api_plan_with_packet_enriches_and_summarizes(tmp_path):
    from agent_pipeline import api, config
    p = intake.load_intake(config.PROJECT_ROOT / "examples" / "top_customers_intake.json")
    payload = api.plan(p, out_dir=tmp_path)
    assert payload["evaluation"] is not None and payload["evaluation"]["packet_aware"]
    for plan in payload["plans"]:
        assert "packet_fit" in plan and "acceptance_criteria_covered" in plan
        assert "rollback_strategy" in plan


def test_api_plan_raw_string_has_no_evaluation(tmp_path):
    from agent_pipeline import api
    payload = api.plan("Add a courier performance leaderboard", out_dir=tmp_path)
    assert payload["evaluation"] is None      # backward compatible: no packet, no packet-fit
