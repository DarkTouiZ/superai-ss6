"""Week 4 tests: Developer agent on an isolated branch + Review compliance gate.
Run: pytest -q"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from agent_pipeline.agents.developer import DeveloperAgent
from agent_pipeline.review import review_files, check_file
from eval.execution_quality import evaluate as exec_eval

WINNER = {"id": "B", "priority_focus": "reuse", "summary": "compose primitives",
          "steps": ["compose"], "files_touched": [], "primitives_reused": []}
DESIGN = {"services_used": ["target_repo/backend/src/services/pricing.ts"]}


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _git_available(), reason="git not installed")


def test_developer_creates_branch_and_compliant_code():
    res = DeveloperAgent().execute("Add a top customers screen", WINNER, DESIGN)
    assert res.branch.startswith("ss6/")
    assert res.changed_files, "expected at least one changed file"
    assert res.files[0]["content"], "generated file has content"
    # the generated diff exists in the isolated copy
    assert "TopCustomersComponent" in res.diff


def test_review_passes_generated_code():
    res = DeveloperAgent().execute("Add a top customers screen", WINNER, DESIGN)
    review = review_files(res.files)
    assert review.passed, [v for f in review.files for v in f.violations]


def test_compliance_gate_catches_violations():
    bad = check_file("Bad.tsx", "export const X = () => <div style={{color:'#fff'}}/>; fetch('/x');")
    assert not bad.passed
    joined = " ".join(bad.violations)
    assert "hex" in joined and "fetch()" in joined


def test_execution_eval_discriminates():
    report = exec_eval()
    assert report["good_file_passes"]
    assert report["pass"], report["bad_fixtures"]
