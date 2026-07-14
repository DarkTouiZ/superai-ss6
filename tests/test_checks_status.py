"""Honest gate status + path-based check selection (spec §22.3, §22.4).  Run: pytest -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_pipeline import checks
from agent_pipeline.checks import CheckResult, PASS, FAIL, UNVERIFIED, NOT_REQUIRED


# --- §22.3 UNVERIFIED must never launder into a pass ------------------------- #

def test_unverified_required_check_is_not_a_pass():
    res = [CheckResult("deps", UNVERIFIED, "node_modules cache miss")]
    assert checks.gate_status(res) == UNVERIFIED
    assert checks.checks_passed(res) is False


def test_all_tools_missing_does_not_silently_pass():
    # The original bug: all checks skipped -> all([]) -> True. Now it is UNVERIFIED.
    res = [CheckResult("tsc", UNVERIFIED, "tsc not available"),
           CheckResult("jest", UNVERIFIED, "jest not available")]
    assert checks.checks_passed(res) is False


def test_ran_and_passed_is_pass():
    res = [CheckResult("tsc", PASS, ""), CheckResult("jest", PASS, "")]
    assert checks.gate_status(res) == PASS
    assert checks.checks_passed(res) is True


def test_any_failure_blocks():
    res = [CheckResult("tsc", PASS, ""), CheckResult("jest", FAIL, "boom")]
    assert checks.gate_status(res) == FAIL
    assert checks.checks_passed(res) is False


def test_pass_plus_unverified_is_blocked():
    # A partial result set where one required check couldn't run is still not a pass.
    res = [CheckResult("tsc", PASS, ""), CheckResult("jest", UNVERIFIED, "jest not available")]
    assert checks.gate_status(res) == UNVERIFIED
    assert checks.checks_passed(res) is False


def test_not_required_is_not_blocking():
    res = [CheckResult("scope", NOT_REQUIRED, "docs only")]
    assert checks.gate_status(res) == NOT_REQUIRED
    assert checks.checks_passed(res) is True


# --- §22.4 checks are selected from the actual changed paths ---------------- #

def test_docs_only_change_requires_nothing(tmp_path):
    res = checks.run_selected_checks(str(tmp_path), ["README.md"])
    assert [r.name for r in res] == ["scope"]
    assert res[0].status == NOT_REQUIRED


def test_backend_change_selects_backend_suite(tmp_path):
    # No backend/ dir in this bare tmp copy, but routing must pick the backend suite.
    res = checks.run_selected_checks(str(tmp_path), ["backend/src/x.ts"])
    assert any(r.name in ("backend", "deps", "tsc", "jest") for r in res), res


def test_frontend_change_selects_frontend_suite(tmp_path):
    res = checks.run_selected_checks(str(tmp_path), ["frontend/src/x.ts"])
    assert any(r.name in ("frontend", "frontend-tsc") for r in res), res
