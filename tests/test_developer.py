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
    assert len(res.files) >= 2, "expected a multi-file vertical slice"
    # the generated diff exists in the isolated copy
    assert "rankCustomersBySpend" in res.diff


def test_review_passes_generated_code():
    res = DeveloperAgent().execute("Add a top customers screen", WINNER, DESIGN)
    review = review_files(res.files)
    assert review.passed, [v for f in review.files for v in f.violations]


def test_compliance_gate_catches_violations():
    # fetch() is forbidden everywhere (front end and back end)
    bad_fetch = check_file("svc.ts", "export const X = () => { fetch('/x'); };")
    assert not bad_fetch.passed
    assert any("fetch()" in v for v in bad_fetch.violations)
    # inline hex is a component-scoped rule (UI must use design tokens)
    comp = "import {Component} from '@angular/core'; @Component({styles:[`.x{color:#fff}`]}) export class C {}"
    bad_hex = check_file("c.component.ts", comp)
    assert not bad_hex.passed
    assert any("hex" in v for v in bad_hex.violations)
    # test files are validated by jest, not by the syntactic gate
    assert check_file("a.test.ts", "describe('x',()=>{})").passed


def test_execution_eval_discriminates():
    report = exec_eval()
    assert report["good_file_passes"]
    assert report["pass"], report["bad_fixtures"]
