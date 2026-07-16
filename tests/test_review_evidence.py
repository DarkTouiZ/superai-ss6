"""Evidence-complete REVIEW.md (spec §23)."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from agent_pipeline.review import _evidence_sections


def test_evidence_sections_render_all_blocks():
    ctx = {
        "problem_packet": {"feature_title": "T", "version": 2, "user_goal_or_pain": "pain",
                           "desired_outcome": "out", "acceptance_criteria": ["c1"]},
        "winner": {"id": "B", "title": "reuse", "priority_focus": "reuse",
                   "rollback_strategy": "revert the branch",
                   "acceptance_criteria_covered": [{"criterion": "c1", "covered": True, "evidence": ["spend"]}],
                   "packet_fit": {"user_fit_pass": True, "system_fit_pass": True,
                                  "acceptance_coverage": 1.0, "system_fit_reasons": []}},
        "impact": {"security_or_privacy_impact": ["sensitive"], "data_or_schema_impact": [],
                   "public_contracts_at_risk": ["api contract"], "protected_areas_touched": []},
        "grounding": [{"rel_path": "backend/x.ts", "start_line": 1, "end_line": 9, "score": 0.5}],
        "assumptions": [], "open_questions": [{"question": "which auth?"}],
    }
    text = "\n".join(_evidence_sections(ctx))
    assert "Feature & intent" in text and "packet v2" in text
    assert "Selected plan" in text and "revert the branch" in text
    assert "☑ c1" in text and "spend" in text            # criteria checklist w/ evidence
    assert "security/privacy" in text and "public contracts" in text
    assert "backend/x.ts:1-9" in text                     # grounding citation
    assert "which auth?" in text                          # open question
    assert "context.md rules in force" in text


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _git_available(), reason="git not installed")
def test_review_md_is_evidence_complete_end_to_end(tmp_path):
    from agent_pipeline import api, config, intake
    p = intake.load_intake(config.PROJECT_ROOT / "examples" / "top_customers_intake.json")
    payload = api.plan(p, out_dir=tmp_path)
    api.execute(payload, out_dir=tmp_path, require_approval=True, approved_by="Tester")
    text = (tmp_path / "REVIEW.md").read_text(encoding="utf-8")
    for section in ["Feature & intent", "Selected plan", "Acceptance criteria",
                    "Risk & human approval", "Grounding used during planning",
                    "context.md rules in force", "your decision"]:
        assert section in text, f"missing REVIEW.md section: {section}"
    # gate_passed clarifier + explicit human-decision verbs (spec §21.3, §23)
    assert "means the automated technical gate passed" in text
    for verb in ("APPROVE", "REQUEST FIX", "RE-PLAN", "REJECT"):
        assert verb in text
    # approval was recorded and disclosed
    assert "approved by `Tester`" in text
