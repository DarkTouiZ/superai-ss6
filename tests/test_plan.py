"""Week 2 tests: Architect plan generation + plan-phase eval gates. Run: pytest -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_pipeline.agents.architect import ArchitectAgent, write_outputs
from eval.plan_quality import evaluate


def _make_plans(tmp_path):
    agent = ArchitectAgent()
    ps = agent.generate("Add a top customers by revenue screen")
    json_path, md_path = write_outputs(ps, tmp_path)
    return ps, json_path, md_path


def test_architect_emits_three_archetype_plans(tmp_path):
    ps, json_path, md_path = _make_plans(tmp_path)
    assert len(ps.plans) == 3
    assert {p["priority_focus"] for p in ps.plans} == {"performance", "reuse", "speed"}
    assert json_path.exists() and md_path.exists()
    assert "Plan A" in md_path.read_text()


def test_plan_eval_passes_all_gates(tmp_path):
    _, json_path, _ = _make_plans(tmp_path)
    report = evaluate(json_path)
    assert report["schema_valid"], report["schema_errors"]
    assert report["archetype_cover"]
    assert report["distinct_ok"], report["mean_pairwise_similarity"]
    assert report["grounding_ok"], report["grounding_errors"]
    assert report["pass"]


def test_reuse_plan_grounds_in_canonical_primitives(tmp_path):
    ps, _, _ = _make_plans(tmp_path)
    reuse_plan = next(p for p in ps.plans if p["priority_focus"] == "reuse")
    assert reuse_plan["primitives_reused"], "reuse plan should cite primitives"
