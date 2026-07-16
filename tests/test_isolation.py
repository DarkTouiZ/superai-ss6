"""Safety baseline (spec §22.1 path containment, §22.2 repair isolation).  Run: pytest -q"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from agent_pipeline import vcs
from agent_pipeline.agents.developer import DeveloperAgent
from agent_pipeline.review import review_files, gate_feedback, GateOutcome

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


def _fresh(slug: str):
    wc = vcs.make_working_copy(slug)
    vcs.create_branch(wc, f"ss6/{slug}")
    return wc


def _compliance_gate(files, workdir):
    rev = review_files(files)
    return GateOutcome(rev.passed, gate_feedback(rev), rev, [])


# --- §22.1 path containment ------------------------------------------------- #

def test_parent_traversal_is_rejected():
    wc = _fresh("iso-traversal")
    escape = (wc.path / "../../ss6_escape_probe.txt").resolve()
    effective, conflicts = DeveloperAgent._write_files(wc, [{"path": "../../ss6_escape_probe.txt", "content": "x"}])
    assert any("unsafe path" in c for c in conflicts), conflicts
    assert not effective
    assert not escape.exists(), "a traversal path escaped the isolated repo"


def test_absolute_path_is_rejected(tmp_path):
    wc = _fresh("iso-abs")
    target = tmp_path / "ss6_abs_probe.txt"
    effective, conflicts = DeveloperAgent._write_files(wc, [{"path": str(target), "content": "x"}])
    assert any("unsafe path" in c for c in conflicts), conflicts
    assert not target.exists()


def test_prefix_confusion_is_rejected():
    """Only the exact 'target_repo/' prefix is stripped — 'target_repo-evil/...'
    must not be smuggled through as if it were the repo prefix."""
    wc = _fresh("iso-prefix")
    effective, conflicts = DeveloperAgent._write_files(
        wc, [{"path": "target_repo-evil/x.ts", "content": "export const x = 1;"}]
    )
    assert any("unsafe path" in c for c in conflicts), conflicts
    assert not effective


def test_valid_backend_path_writes():
    wc = _fresh("iso-valid")
    effective, conflicts = DeveloperAgent._write_files(
        wc, [{"path": "backend/src/ss6_probe.ts", "content": "export const x = 1;"}]
    )
    assert not conflicts, conflicts
    assert (wc.path / "backend/src/ss6_probe.ts").exists()


def test_path_naming_existing_directory_is_rejected():
    """D4 regression: a generated path that resolves to an existing directory must be a
    clean conflict, not an uncaught IsADirectoryError."""
    wc = _fresh("iso-dir")
    effective, conflicts = DeveloperAgent._write_files(wc, [{"path": "backend/src", "content": "x"}])
    assert any("existing directory" in c for c in conflicts), conflicts
    assert not effective


def test_diff_touching_outside_repo_is_rejected():
    """A diff whose wrapper path is safe but whose body targets an outside file must
    be rejected — every path a diff references is validated (spec §22.1)."""
    wc = _fresh("iso-diff")
    evil = "--- a/../../evil.ts\n+++ b/../../evil.ts\n@@ -0,0 +1 @@\n+bad\n"
    effective, conflicts = DeveloperAgent._write_files(
        wc, [{"path": "backend/src/ok.ts", "diff": evil}]
    )
    assert any("diff targets rejected" in c for c in conflicts), conflicts


# --- §22.2 repair isolation ------------------------------------------------- #

def test_repair_discards_stale_file_from_earlier_attempt(monkeypatch):
    """Regression: attempt 1 writes a bad file and fails; attempt 2 returns only a
    good file. The stale bad file must NOT survive into the gated/committed diff."""
    def fake_generate(self, requirement, winner, design, feedback=None, repair_round=0):
        good = {"path": "backend/src/services/good_probe.ts",
                "content": "export const ok = (): number => 1;"}
        if repair_round == 0:
            bad = {"path": "backend/src/services/bad_probe.ts",
                   "content": "export const bad = () => { fetch('/x'); };"}
            return [good, bad]
        return [good]

    monkeypatch.setattr(DeveloperAgent, "generate_files", fake_generate)
    res = DeveloperAgent().execute("stale file repro", WINNER, DESIGN,
                                   gate=_compliance_gate, max_attempts=3)
    assert res.attempts == 2, res.attempt_log
    assert res.repaired is True
    changed = " ".join(res.changed_files)
    assert "bad_probe.ts" not in changed, res.changed_files   # stale file is gone
    assert "good_probe.ts" in changed
    assert "fetch(" not in res.diff                            # no violation survives
    assert review_files(res.files).passed
