"""Regression tests for the code-review fixes (findings #2-#10 + cleanup)."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from agent_pipeline import checks, config, hitl, impact, normalize
from agent_pipeline.hitl import HumanApproval


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


# --- #R1 shared repo_rel ---------------------------------------------------- #
def test_repo_rel_strips_only_exact_prefix():
    assert normalize.repo_rel("target_repo/backend/x.ts") == "backend/x.ts"
    assert normalize.repo_rel("target_repo-evil/x.ts") == "target_repo-evil/x.ts"  # not spoofable
    assert normalize.repo_rel("backend\\x.ts") == "backend/x.ts"                   # posix-normalized


# --- #4 single source of truth for protected areas -------------------------- #
def test_protected_areas_single_source():
    assert impact._PROTECTED is config.PROTECTED_AREAS
    assert hitl.plan_protected_touches({"files_touched": ["backend/db/migrations/1.sql"]}) == ["backend/db/migrations"]
    assert normalize.protected_touches(["target_repo/backend/src/aws/sns.ts"]) == ["backend/src/aws"]


# --- #2 post-execution risk re-check from ACTUAL changed files --------------- #
def test_post_execution_escalation_from_actual_files(tmp_path):
    imp = {"proposed_risk_level": "medium", "risk_reasons": []}
    plan = {"id": "B", "files_touched": ["backend/src/services/x.ts"]}  # declared medium
    hitl.record_approval(tmp_path, HumanApproval(
        stage="plan", decision="approved", approved_by="S",
        packet_version=1, plan_id="B", environment_version=1, risk_level="medium"))
    # declared risk is medium and the medium approval covers it
    declared = hitl.check_execution_allowed(tmp_path, impact=imp, chosen_plan=plan,
                                            packet_version=1, environment_version=1)
    assert declared.approved and declared.risk_level == "medium"
    # but the ACTUAL diff also wrote a migration → executed risk is high → medium approval insufficient
    executed = hitl.check_execution_allowed(
        tmp_path, impact=imp, chosen_plan=plan, packet_version=1, environment_version=1,
        changed_files=["backend/src/services/x.ts", "backend/db/migrations/007.sql"])
    assert executed.risk_level == "high"
    assert executed.blocked


# --- #3 infra change under --run-tests is UNVERIFIED, not a silent pass ------ #
def test_infra_change_under_run_tests_is_unverified(tmp_path):
    res = checks.run_selected_checks(str(tmp_path), ["docker-compose.yml"])
    assert any(r.name == "infra" and r.status == checks.UNVERIFIED for r in res), res
    assert checks.checks_passed(res) is False


# --- #5 null plan id cannot be wildcard-authorized -------------------------- #
def test_find_matching_approval_rejects_null_plan_id():
    apps = [HumanApproval(stage="plan", decision="approved", approved_by="S",
                          packet_version=1, plan_id="B", environment_version=1, risk_level="high")]
    assert hitl.find_matching_approval(apps, packet_version=1, plan_id=None,
                                       environment_version=1, risk_level="high") is None


# --- #6 diff-header regex no longer false-matches removed '-- ' comment lines - #
def test_diff_removing_sql_comment_is_not_falsely_rejected():
    from agent_pipeline.agents.developer import _diff_target_paths
    diff = ("--- a/backend/db/migrations/001.sql\n"
            "+++ b/backend/db/migrations/001.sql\n"
            "@@ -1,1 +1,1 @@\n"
            "--- add index on customers\n"        # a REMOVED SQL comment line
            "+-- add composite index on customers\n")
    targets = _diff_target_paths(diff)
    assert targets == ["backend/db/migrations/001.sql"]
    assert "add index on customers" not in targets


# --- #7 common words no longer force high risk ------------------------------ #
def test_common_words_do_not_force_high_risk():
    from agent_pipeline.grounding import GroundingChunk
    ch = [GroundingChunk("x", "frontend/src/app/features/profile.ts", 1, 2, "code", 0.5, "code")]
    ia = impact.analyze_impact("Show each user's role and their design token on the profile", ch)
    assert ia.proposed_risk_level != "high"      # 'role'/'token' used to escalate
    assert not ia.security_or_privacy_impact


# --- #8 missing-tool UNVERIFIED does not drive the repair loop --------------- #
def test_gate_unverified_only_flag_is_set(monkeypatch, tmp_path):
    # a compliant change whose required check can't run -> unverified_only, so no repair
    from agent_pipeline import review
    r = review.review_files([{"path": "backend/src/services/ok.ts",
                              "content": "export const ok = (): number => 1;"}])
    tests = [checks.CheckResult("tsc", checks.UNVERIFIED, "tsc not available")]
    unverified_only = (r.passed and checks.gate_status(tests) == checks.UNVERIFIED)
    assert unverified_only is True


# --- #9 allowlist permits common root tooling files ------------------------- #
@pytest.mark.skipif(not _git_available(), reason="git not installed")
def test_allowlist_permits_common_root_files():
    from agent_pipeline import vcs
    from agent_pipeline.agents.developer import DeveloperAgent
    wc = vcs.make_working_copy("allow-root")
    vcs.create_branch(wc, "ss6/allow-root")
    eff, conflicts = DeveloperAgent._write_files(wc, [{"path": "package.json", "content": "{}"}])
    assert not conflicts, conflicts
    assert (wc.path / "package.json").exists()
