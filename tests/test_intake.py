"""ProblemPacket intake: schema, readiness, questions, JSON+MD loading (spec §5-8,§13)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from agent_pipeline import config, intake
from agent_pipeline.intake import (
    ProblemPacket, load_intake, validate_packet, compute_readiness,
    questions_for_packet, requirement_text,
)

EX = config.PROJECT_ROOT / "examples"


def test_load_json_intake_has_required_and_readiness():
    p = load_intake(EX / "top_customers_intake.json")
    assert isinstance(p, ProblemPacket)
    assert p.feature_title and len(p.acceptance_criteria) >= 1
    assert validate_packet(p) == []
    assert p.readiness.can_plan is True
    assert p.readiness.can_evaluate is True          # example provides evaluation methods


def test_load_markdown_intake_matches_json_essentials():
    pj = load_intake(EX / "top_customers_intake.json")
    pm = load_intake(EX / "top_customers_intake.md")
    assert pm.feature_title == pj.feature_title
    assert pm.acceptance_criteria[0].startswith("GET /api/v1/dashboard/top-customers")
    assert pm.readiness.can_plan is True
    assert len(pm.evaluation_method) >= 1
    assert pm.existing_system_context.is_known()


def test_missing_required_field_is_caught_and_blocks_plan():
    p = ProblemPacket(feature_title="", user_requirement="x", user_goal_or_pain="y",
                      desired_outcome="z", acceptance_criteria=[])
    problems = validate_packet(p)
    assert any("feature_title" in x for x in problems)
    assert any("acceptance_criteria" in x for x in problems)
    assert compute_readiness(p).can_plan is False


def test_questions_generated_when_eval_or_context_missing():
    p = ProblemPacket("t", "r", "g", "o", ["c1"])   # no eval method, no system context
    ids = {q.id for q in questions_for_packet(p)}
    assert "eval-method" in ids
    assert "system-context" in ids


def test_requirement_text_carries_acceptance_criteria():
    p = load_intake(EX / "top_customers_intake.json")
    txt = requirement_text(p)
    assert "FEATURE TITLE" in txt and "ACCEPTANCE CRITERIA" in txt
    assert "top-customers" in txt


def test_unknown_constraints_not_treated_as_absent():
    p = ProblemPacket("t", "r", "g", "o", ["c1"])
    assert p.constraints.deadline == "unknown"        # not "" / None
    assert "deadline: unknown" in requirement_text(p)


def test_living_packet_fields_default_sanely():
    p = ProblemPacket("t", "r", "g", "o", ["c1"])
    assert p.version == 1
    assert p.change_log == [] and p.obsolete_items == [] and p.reusable_items == []


def test_api_plan_accepts_packet_and_records_it(tmp_path):
    from agent_pipeline import api
    p = load_intake(EX / "top_customers_intake.json")
    payload = api.plan(p, out_dir=tmp_path)
    assert payload["problem_packet"]["feature_title"] == p.feature_title
    assert payload["readiness"]["can_plan"] is True
    # backward-compatible 'requirement' becomes the packet-derived text (spec §13)
    assert payload["requirement"].startswith("FEATURE TITLE")
    d = json.load(open(tmp_path / "plans.json"))
    assert d["problem_packet"]["feature_title"] == p.feature_title
    assert {"assumptions", "open_questions", "readiness"} <= d.keys()


def test_raw_string_still_works_and_has_null_packet(tmp_path):
    from agent_pipeline import api
    payload = api.plan("Add a courier performance leaderboard", out_dir=tmp_path)
    assert payload["problem_packet"] is None          # backward compatible
    assert payload["requirement"] == "Add a courier performance leaderboard"


def test_cli_rejects_both_requirement_and_intake():
    from agent_pipeline import cli
    args = cli.build_parser().parse_args(
        ["plan", "raw req", "--intake", str(EX / "top_customers_intake.json")])
    with pytest.raises(SystemExit):
        cli._resolve_requirement_arg(args)


def test_cli_loads_intake_when_only_intake_given():
    from agent_pipeline import cli
    args = cli.build_parser().parse_args(["plan", "--intake", str(EX / "top_customers_intake.json")])
    resolved = cli._resolve_requirement_arg(args)
    assert isinstance(resolved, ProblemPacket)
    assert resolved.feature_title
