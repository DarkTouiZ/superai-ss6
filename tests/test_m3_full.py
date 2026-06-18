"""Roadmap M3 (full): unified-diff application via git apply --3way.  Run: pytest -q"""
import difflib
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from agent_pipeline import vcs
from agent_pipeline.agents.developer import DeveloperAgent


def _git_available() -> bool:
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _git_available(), reason="git not installed")

TARGET = "backend/src/routes/index.ts"


def _make_diff(original: str, modified: str, path: str) -> str:
    return "".join(difflib.unified_diff(
        original.splitlines(keepends=True),
        modified.splitlines(keepends=True),
        fromfile=f"a/{path}", tofile=f"b/{path}",
    ))


def _fresh_copy():
    wc = vcs.make_working_copy("m3full-test")
    vcs.create_branch(wc, "ss6/m3full-test")
    return wc


def test_unified_diff_applies_and_is_idempotent():
    wc = _fresh_copy()
    target = wc.path / TARGET
    original = target.read_text(encoding="utf-8")
    modified = original.replace(
        "export const router = Router();",
        "export const router = Router();\n// SS6 patched marker",
    )
    diff = _make_diff(original, modified, TARGET)

    ok, msg = vcs.apply_patch(wc, diff)
    assert ok, msg
    assert "SS6 patched marker" in target.read_text(encoding="utf-8")

    # idempotent: re-applying the same patch is a clean no-op, not an error/dup
    ok2, msg2 = vcs.apply_patch(wc, diff)
    assert ok2, msg2
    assert target.read_text(encoding="utf-8").count("SS6 patched marker") == 1


def test_non_applying_patch_reports_conflict():
    wc = _fresh_copy()
    bogus = (
        f"--- a/{TARGET}\n+++ b/{TARGET}\n@@ -1,1 +1,1 @@\n"
        "-this line does not exist in the file at all\n"
        "+replacement\n"
    )
    ok, msg = vcs.apply_patch(wc, bogus)
    assert not ok
    assert msg  # a human-readable failure reason


def test_developer_write_files_accepts_diff_entries():
    wc = _fresh_copy()
    target = wc.path / TARGET
    original = target.read_text(encoding="utf-8")
    modified = original.replace(
        "export const router = Router();",
        "export const router = Router();\n// via diff entry",
    )
    diff = _make_diff(original, modified, TARGET)
    effective, conflicts = DeveloperAgent._write_files(wc, [{"path": TARGET, "diff": diff}])
    assert not conflicts, conflicts
    assert effective[0]["patched"] is True
    assert "via diff entry" in effective[0]["content"]
