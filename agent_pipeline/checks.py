"""Real verification for the Review phase — $0, local, and honest about coverage.

Beyond the syntactic compliance suite, the Review phase can run the *target repo's
own* checks inside the isolated branch copy: the TypeScript compiler (``tsc
--noEmit``) and the unit tests (``jest``). This turns "the change looks compliant"
into "the change actually compiles and its tests pass" — a stronger, still-free
signal. No LLM is involved.

Every check reports one of four honest statuses (spec §22.3):

    PASS         every required check ran and passed
    FAIL         a required check ran and failed
    UNVERIFIED   a required check could NOT run (tool/deps missing) — NOT a pass
    NOT_REQUIRED the check is irrelevant to the changed area

Critically, when ``--run-tests`` is requested a required-but-skipped check is
``UNVERIFIED`` and must never be laundered into ``gate_passed=True``.

Checks are selected from the *actual changed paths* (spec §22.4): a backend change
runs the backend suite, a frontend change runs the frontend suite. To stay offline
($0), an existing ``node_modules`` is reused via symlink; if the cache is missing we
report ``UNVERIFIED`` rather than silently running ``npm install`` (which would need
the network) unless ``SS6_ALLOW_NPM_INSTALL=1`` is set.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from agent_pipeline import config

# Honest check statuses.
PASS = "PASS"
FAIL = "FAIL"
UNVERIFIED = "UNVERIFIED"
NOT_REQUIRED = "NOT_REQUIRED"
_BLOCKING = {FAIL, UNVERIFIED}


@dataclass
class CheckResult:
    name: str
    status: str          # PASS | FAIL | UNVERIFIED | NOT_REQUIRED
    detail: str = ""

    @property
    def passed(self) -> bool:
        return self.status == PASS

    @property
    def failed(self) -> bool:
        return self.status == FAIL

    @property
    def skipped(self) -> bool:
        """Back-compat: UNVERIFIED and NOT_REQUIRED both mean "did not pass/fail"."""
        return self.status in (UNVERIFIED, NOT_REQUIRED)

    @property
    def mark(self) -> str:
        return self.status.lower()


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


def _tool_status(ok: Optional[bool]) -> str:
    return UNVERIFIED if ok is None else (PASS if ok else FAIL)


def _ensure_node_modules(area: Path) -> tuple[bool, str]:
    """Make node_modules available in the isolated area, cheaply and offline.

    Reuses the committed ``target_repo/<area>/node_modules`` via symlink ($0, no
    network). Only runs ``npm install`` if ``SS6_ALLOW_NPM_INSTALL=1`` — otherwise a
    cache miss is reported so the caller can mark the check UNVERIFIED honestly.
    """
    nm = area / "node_modules"
    if nm.exists():
        return True, "present"
    cache = config.TARGET_REPO_DIR / area.name / "node_modules"
    if cache.exists():
        try:
            os.symlink(cache, nm)
            return True, "symlinked from target_repo cache"
        except OSError:
            pass
    if config.ALLOW_NPM_INSTALL and (area / "package.json").exists():
        ok, _ = _run(["npm", "install", "--no-audit", "--no-fund"], area, timeout=900)
        return (True, "npm install (network)") if ok else (False, "npm install failed")
    return False, "node_modules cache miss; npm install disabled (set SS6_ALLOW_NPM_INSTALL=1)"


def run_backend_checks(workdir: str | Path) -> List[CheckResult]:
    """Run tsc --noEmit and jest in the isolated copy's backend."""
    backend = Path(workdir) / "backend"
    if not backend.exists():
        return [CheckResult("backend", NOT_REQUIRED, "no backend/ in the isolated copy")]

    ok, how = _ensure_node_modules(backend)
    if not ok:
        return [CheckResult("deps", UNVERIFIED, f"backend deps unavailable ({how}); tsc/jest could not run")]

    tsc_ok, tsc_out = _run(["npx", "--no-install", "tsc", "--noEmit", "-p", "tsconfig.json"], backend)
    jest_ok, jest_out = _run(["npx", "--no-install", "jest", "--runInBand", "--silent"], backend)
    return [
        CheckResult("tsc", _tool_status(tsc_ok),
                    "tsc not available" if tsc_ok is None else ("type-check clean" if tsc_ok else tsc_out)),
        CheckResult("jest", _tool_status(jest_ok),
                    "jest not available" if jest_ok is None else ("tests passed" if jest_ok else jest_out)),
    ]


def run_frontend_checks(workdir: str | Path) -> List[CheckResult]:
    """Type-check the Angular frontend (tsc --noEmit) in the isolated copy."""
    frontend = Path(workdir) / "frontend"
    if not frontend.exists():
        return [CheckResult("frontend", NOT_REQUIRED, "no frontend/ in the isolated copy")]

    ok, how = _ensure_node_modules(frontend)
    tsconfig = frontend / "tsconfig.json"
    if not ok or not tsconfig.exists():
        why = how if not ok else "no tsconfig.json"
        return [CheckResult("frontend-tsc", UNVERIFIED, f"frontend typecheck could not run ({why})")]
    fe_ok, fe_out = _run(["npx", "--no-install", "tsc", "--noEmit", "-p", "tsconfig.json"], frontend)
    return [CheckResult("frontend-tsc", _tool_status(fe_ok),
                        "tsc not available" if fe_ok is None else ("type-check clean" if fe_ok else fe_out))]


def run_selected_checks(workdir: str | Path, changed_files: List[str] | None) -> List[CheckResult]:
    """Pick the check suites from the ACTUAL changed paths (spec §22.4).

    Backend code change → backend tsc/jest. Frontend change → frontend typecheck. An
    infra/docker/compose change has no automated check but MUST NOT pass silently — it is
    reported UNVERIFIED (needs human validation), so `--run-tests` on an infra-only change
    cannot yield gate_passed=True. If nothing verifiable was touched → NOT_REQUIRED.
    """
    from agent_pipeline import normalize
    paths = [normalize.repo_rel(p) for p in (changed_files or [])]
    touches_backend = any(p.startswith("backend/") for p in paths)
    touches_frontend = any(p.startswith("frontend/") for p in paths)
    touches_infra = any(p.startswith(("infra/", "localstack/")) or p == "docker-compose.yml"
                        for p in paths)
    results: List[CheckResult] = []
    if touches_backend:
        results += run_backend_checks(workdir)
    if touches_frontend:
        results += run_frontend_checks(workdir)
    if touches_infra:
        results.append(CheckResult("infra", UNVERIFIED,
                                   "infra/compose change has no automated check — needs human validation"))
    if not results:
        results.append(CheckResult("scope", NOT_REQUIRED,
                                   "no backend/ or frontend/ code changed; nothing to build/test"))
    return results


def gate_status(results: List[CheckResult]) -> str:
    """Reduce a set of check results to one honest overall status."""
    statuses = {r.status for r in results}
    if FAIL in statuses:
        return FAIL
    if UNVERIFIED in statuses:
        return UNVERIFIED
    if PASS in statuses:
        return PASS
    return NOT_REQUIRED


def checks_passed(results: List[CheckResult]) -> bool:
    """True only when nothing blocks the gate: every required check passed (or none
    was required). A required check left UNVERIFIED — the ``--run-tests`` bug in
    spec §22.3 — is blocking and must NOT read as a pass."""
    return gate_status(results) not in _BLOCKING
