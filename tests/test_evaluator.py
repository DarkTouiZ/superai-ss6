"""Week 3 tests: normalization, Evaluator scoring, and the Debate weight-sensitivity.
Run: pytest -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_pipeline import normalize
from agent_pipeline.agents.evaluator import EvaluatorAgent, score_plan
from eval.debate_quality import evaluate as debate_eval

# Three archetype plans mirroring the Architect's A/B/C, using messy reference
# conventions on purpose (bare names) to also exercise normalization.
PLANS = [
    {"id": "A", "title": "Perf", "priority_focus": "performance",
     "summary": "memoized selector and cached aggregate endpoint with precompute and index",
     "steps": ["add cached aggregate selector", "paginate the query", "precompute totals"],
     "files_touched": ["frontend/src/app/features/top.component.ts", "backend/src/services/pricing.ts"],
     "primitives_reused": ["card.component.ts", "metric-tile.component.ts"],
     "tradeoffs": {"pros": ["fast", "scales"], "cons": ["complex", "more code"]}},
    {"id": "B", "title": "Reuse", "priority_focus": "reuse",
     "summary": "compose existing primitives, fetch via ApiService, use design tokens",
     "steps": ["compose Card + MetricTile + Badge", "fetch through ApiService",
               "reference tokens only", "add a service unit test"],
     "files_touched": ["frontend/src/app/features/top.component.ts"],
     "primitives_reused": ["card.component.ts", "avatar.component.ts", "badge.component.ts",
                           "metric-tile.component.ts", "button.component.ts"],
     "tradeoffs": {"pros": ["max reuse", "blueprint adherence"], "cons": ["not tuned for huge lists"]}},
    {"id": "C", "title": "Fast", "priority_focus": "speed",
     "summary": "minimal component over the existing orders endpoint",
     "steps": ["aggregate client-side", "reuse Card"],
     "files_touched": ["frontend/src/app/features/top.component.ts"],
     "primitives_reused": ["card.component.ts"],
     "tradeoffs": {"pros": ["quick", "few parts"], "cons": ["inline logic"]}},
]


def test_normalization_resolves_primitive_references():
    p = normalize.normalize_plan(PLANS[1])
    assert (
        "target_repo/frontend/src/app/shared/components/card/card.component.ts"
        in p["primitives_reused"]
    )
    # files_touched references are preserved through normalization
    assert "top.component.ts" in p["files_touched"][0]


def test_subscores_align_with_archetypes():
    a, b, c = (score_plan(p) for p in PLANS)
    assert a["performance"] >= max(b["performance"], c["performance"])
    assert b["reuse"] >= max(a["reuse"], c["reuse"])
    assert c["speed"] >= max(a["speed"], b["speed"])


def test_default_weights_pick_reuse_plan():
    res = EvaluatorAgent().evaluate(PLANS)
    assert res.winner_id == "B"
    assert res.winner_focus == "reuse"
    assert res.margin >= 0


def test_debate_eval_weight_sensitivity_passes():
    report = debate_eval(PLANS)
    assert report["pass"], report["profiles"]
    assert report["profiles"]["performance_heavy"]["winner_focus"] == "performance"
    assert report["profiles"]["speed_heavy"]["winner_focus"] == "speed"
