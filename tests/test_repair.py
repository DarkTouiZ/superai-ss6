"""Roadmap M2 (repair loop) + M7 (security scan) tests.  Run: pytest -q"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import agent_pipeline.config as cfg
from agent_pipeline.agents.developer import DeveloperAgent
from agent_pipeline.review import review_files, gate_feedback, GateOutcome, check_file

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


def _compliance_gate(files, workdir):
    rev = review_files(files)
    return GateOutcome(rev.passed, gate_feedback(rev), rev, [])


def test_clean_run_passes_on_first_attempt():
    """With no injected fault, the gate passes on attempt 1 (no repair needed)."""
    res = DeveloperAgent().execute(
        "Add a top customers screen", WINNER, DESIGN, gate=_compliance_gate, max_attempts=3
    )
    assert res.attempts == 1
    assert res.repaired is False
    assert review_files(res.files).passed


def test_repair_loop_recovers_from_injected_violation(monkeypatch):
    """With a fixable violation injected on the first attempt, the loop feeds the
    violation back and converges to a compliant change on the second attempt."""
    monkeypatch.setattr(cfg, "DEMO_REPAIR", True)
    res = DeveloperAgent().execute(
        "Add a top customers screen", WINNER, DESIGN, gate=_compliance_gate, max_attempts=3
    )
    assert res.attempts == 2, res.attempt_log
    assert res.repaired is True
    assert res.attempt_log[0]["passed"] is False
    assert any("fetch()" in v for v in res.attempt_log[0]["violations"])
    assert res.attempt_log[-1]["passed"] is True
    # the committed code is clean
    assert review_files(res.files).passed


def test_security_scan_flags_secret_and_eval():
    secret = check_file("svc.ts", "export const c = 1;\nconst apiKey = 'AKIAABCDEFGHIJKLMNOP';")
    assert not secret.passed
    assert any("credential" in v or "secret" in v for v in secret.violations)
    danger = check_file("svc.ts", "export function r(): void { eval('1+1'); }")
    assert not danger.passed
    assert any("dynamic code execution" in v for v in danger.violations)
    # the compliant generated slice is unaffected by the security scan
    clean = check_file("svc.ts", "export function ok(): number { return 1; }")
    assert clean.passed


def test_asset_files_are_not_required_to_export():
    """Live-run dogfooding finding: .html/.scss assets legitimately ship no export,
    so the 'must export' / return-type rules must not fire on them."""
    assert check_file("x.component.html", "<h1>{{ title }}</h1>").passed
    assert check_file("x.component.scss", ".row { color: var(--color-text); }").passed
    # a .ts file with no export is still a violation
    assert not check_file("x.ts", "const x = 1;").passed
