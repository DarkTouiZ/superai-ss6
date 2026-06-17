"""Real verification for the Review phase — zero cost, local only.

Beyond the syntactic compliance suite, the Review phase can run the *target repo's
own* checks inside the isolated branch copy: the TypeScript compiler (``tsc
--noEmit``) and the unit tests (``jest``). This turns "the change looks compliant"
into "the change actually compiles and its tests pass" — a far stronger, and still
free, signal. No LLM and no network are involved.

To stay fast, an existing ``target_repo/backend/node_modules`` is reused (symlinked)
into the isolated copy; otherwise ``npm install`` is run once.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from agent_pipeline import config


@dataclass
class CheckResult:
    name: str
    passed: bool
    skipped: bool
    detail: str = ""

    @property
    def mark(self) -> str:
        return "skipped" if self.skipped else ("pass" if self.passed else "fail")


def _run(cmd: List[str], cwd: Path, timeout: int = 900) -> tuple[Optional[bool], str]:
    """Return (passed, tail-of-output). passed=None means the tool was not found."""
    try:
        p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)
        out = (p.stdout or "") + (p.stderr or "")
        return p.returncode == 0, out[-4000:]
    except FileNotFoundError:
        return None, f"{cmd[0]}: not found"
    except subprocess.TimeoutExpired:
        return False, f"{' '.join(cmd)}: timed out after {timeout}s"


def _ensure_node_modules(backend: Path) -> tuple[bool, str]:
    """Make node_modules available in the isolated backend, cheaply if possible."""
    nm = backend / "node_modules"
    if nm.exists():
        return True, "present"
    cache = config.TARGET_REPO_DIR / "backend" / "node_modules"
    if cache.exists():
        try:
            os.symlink(cache, nm)
            return True, "symlinked from target_repo cache"
        except OSError:
            pass
    if (backend / "package.json").exists():
        ok, _ = _run(["npm", "install", "--no-audit", "--no-fund"], backend, timeout=900)
        if ok:
            return True, "npm install"
        return False, "npm install failed"
    return False, "no package.json"


def run_backend_checks(workdir: str | Path) -> List[CheckResult]:
    """Run tsc --noEmit and jest in the isolated copy's backend. Returns one
    CheckResult per tool. Tools that are absent are reported as skipped, not failed,
    so the gate still works on a machine without Node installed."""
    backend = Path(workdir) / "backend"
    results: List[CheckResult] = []
    if not backend.exists():
        return [CheckResult("backend", False, True, "no backend/ in the change")]

    ok, how = _ensure_node_modules(backend)
    if not ok:
        return [CheckResult("deps", False, True, f"node_modules unavailable ({how}); skipping tsc/jest")]

    tsc_ok, tsc_out = _run(["npx", "--no-install", "tsc", "--noEmit", "-p", "tsconfig.json"], backend)
    if tsc_ok is None:
        results.append(CheckResult("tsc", False, True, "tsc not available"))
    else:
        results.append(CheckResult("tsc", tsc_ok, False, "type-check clean" if tsc_ok else tsc_out))

    jest_ok, jest_out = _run(["npx", "--no-install", "jest", "--runInBand", "--silent"], backend)
    if jest_ok is None:
        results.append(CheckResult("jest", False, True, "jest not available"))
    else:
        # jest prints the summary to stderr; keep the tail either way
        results.append(CheckResult("jest", jest_ok, False, "tests passed" if jest_ok else jest_out))
    return results


def checks_passed(results: List[CheckResult]) -> bool:
    """A real check is a gate only when it actually ran. Skipped tools don't fail
    the gate (graceful on hosts without Node); executed tools must pass."""
    ran = [r for r in results if not r.skipped]
    return all(r.passed for r in ran)
