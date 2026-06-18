"""Isolated git operations for the Developer agent.

SAFETY: the agent must never touch the user's outer repo or production. So we COPY
``target_repo`` into a throwaway working directory under ``out/exec/`` and run all
git there. Branches, commits and diffs live only in that copy; the human reviews
the diff and decides whether to bring it back. This realizes the brief's "create a
git branch to try the plan" without risking anything real.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from agent_pipeline import config


class GitError(RuntimeError):
    pass


def _git(args: List[str], cwd: Path) -> str:
    env_args = [
        "git",
        "-c", f"user.name={config.GIT_AUTHOR_NAME}",
        "-c", f"user.email={config.GIT_AUTHOR_EMAIL}",
        "-c", "commit.gpgsign=false",
        *args,
    ]
    proc = subprocess.run(env_args, cwd=str(cwd), capture_output=True, text=True)
    if proc.returncode != 0:
        raise GitError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout


@dataclass
class WorkingCopy:
    path: Path           # the isolated copy of target_repo
    base_branch: str     # baseline branch name
    feature_branch: Optional[str] = None


def make_working_copy(slug: str, src: Optional[Path] = None) -> WorkingCopy:
    """Fresh isolated copy of target_repo with a git baseline commit."""
    src = src or config.TARGET_REPO_DIR
    dest = config.EXEC_DIR / slug
    shutil.rmtree(dest, ignore_errors=True)  # best-effort; tolerant of locked junk
    repo = dest / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    # exclude OS/tooling junk so the git baseline is clean and reproducible
    shutil.copytree(
        src, repo,
        ignore=shutil.ignore_patterns(".DS_Store", ".git", "node_modules", "__pycache__"),
        dirs_exist_ok=True,
    )

    _git(["init", "-q"], repo)
    # Keep node_modules (symlinked later by the real tsc/jest gate) out of git, so it
    # never pollutes the baseline, the commit, or the reviewed diff. A symlink to a
    # directory can slip past a `node_modules/` .gitignore rule, so exclude it here.
    exclude = repo / ".git" / "info" / "exclude"
    try:
        exclude.write_text(
            (exclude.read_text(encoding="utf-8") if exclude.exists() else "")
            + "\nnode_modules\n**/node_modules\n",
            encoding="utf-8",
        )
    except OSError:
        pass
    # name the baseline branch deterministically across git versions
    _git(["checkout", "-q", "-B", "main"], repo)
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "-m", "baseline: target_repo snapshot"], repo)
    return WorkingCopy(path=repo, base_branch="main")


def create_branch(wc: WorkingCopy, branch: str) -> None:
    _git(["checkout", "-q", "-B", branch], wc.path)
    wc.feature_branch = branch


def commit_all(wc: WorkingCopy, message: str) -> None:
    _git(["add", "-A"], wc.path)
    _git(["commit", "-q", "-m", message], wc.path)


def diff_against_base(wc: WorkingCopy) -> str:
    return _git(["diff", f"{wc.base_branch}..{wc.feature_branch or 'HEAD'}"], wc.path)


def diff_stat(wc: WorkingCopy) -> str:
    return _git(["diff", "--stat", f"{wc.base_branch}..{wc.feature_branch or 'HEAD'}"], wc.path)


def apply_patch(wc: WorkingCopy, diff_text: str, three_way: bool = True) -> Tuple[bool, str]:
    """Apply a unified diff to the working copy (roadmap M3, full). Uses ``git apply
    --3way`` so a patch with slightly stale context can still merge via the blob index,
    and reports a conflict instead of raising. Idempotent: a patch that already applies
    in reverse (i.e. is already present) is treated as a successful no-op, so re-running
    across repair attempts never double-applies or errors."""
    if not diff_text.strip():
        return False, "empty patch"
    text = diff_text if diff_text.endswith("\n") else diff_text + "\n"
    fd, patch_path = tempfile.mkstemp(suffix=".patch", dir=str(wc.path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        # Idempotency guard: if it cleanly reverse-applies, it's already in place.
        try:
            _git(["apply", "--check", "--reverse", patch_path], wc.path)
            return True, "already applied (no-op)"
        except GitError:
            pass
        args = ["apply", "--whitespace=nowarn"]
        if three_way:
            args.append("--3way")
        args.append(patch_path)
        try:
            _git(args, wc.path)
            return True, "applied"
        except GitError as exc:
            return False, str(exc)
    finally:
        try:
            os.remove(patch_path)
        except OSError:
            pass


def changed_files(wc: WorkingCopy) -> List[str]:
    out = _git(["diff", "--name-only", f"{wc.base_branch}..{wc.feature_branch or 'HEAD'}"], wc.path)
    return [line for line in out.splitlines() if line.strip() and "node_modules" not in line]
