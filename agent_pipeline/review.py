"""Review phase — Phase 4 ("Test & HITL").

Runs an automated **context.md compliance suite** over the Developer's generated
files. In a full setup this is where the repo's jest tests would also run; for the
MVP the meaningful, runnable gate is whether the new code obeys the System Blueprint
(the project's whole reason for existing). If the suite passes the pipeline writes a
PR-review packet (``REVIEW.md``) and HALTS for human approval — it never auto-merges.

Hard checks (a violation fails the gate):
  * no inline hex color literal (context.md §2/§3 — tokens only)
  * no direct ``fetch(`` in a feature/component file (§4 — go through api/client)
  * reuses at least one canonical primitive / feature component (§3)
  * file has an export (it actually ships something)

Soft checks (reported, non-blocking):
  * imports design tokens
  * exported function/component has an explicit return type
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from agent_pipeline import config

_HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
_FETCH = re.compile(r"\bfetch\s*\(")
_HTTPCLIENT = re.compile(r"\bHttpClient\b")
_COMPONENT = re.compile(r"@Component\b")
_EXPORT = re.compile(r"\bexport\b")
_RETURN_TYPE = re.compile(r"\)\s*:\s*[A-Za-z_][\w<>\[\].| ]*\s*(=>|\{)")

# --- Security scan (roadmap M7 slice): cheap, high-signal guards on shipped code. --
# A hardcoded credential assigned to a quoted literal, an AWS access-key id, or a
# dynamic code-execution sink. These are hard violations: never ship them.
_SECRET = re.compile(
    r"(?i)\b(password|passwd|secret|api[_-]?key|access[_-]?key|auth[_-]?token|token)\b"
    r"\s*[:=]\s*['\"][^'\"]{6,}['\"]"
)
_AWS_KEY = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_DANGER = re.compile(r"\beval\s*\(|\bnew\s+Function\s*\(|child_process")

# Canonical primitive class names for eleven-7 (Angular shared components). A path
# like ".../card/card.component.ts" maps to the class "CardComponent".
def _component_class(path: str) -> str:
    stem = path.split("/")[-1]                     # card.component.ts
    base = stem.replace(".component.ts", "").replace(".ts", "")
    return "".join(w.capitalize() for w in base.split("-")) + "Component"

_PRIMITIVE_NAMES = {_component_class(p) for p in config.CANONICAL_PRIMITIVES}
# Other reusable building blocks a feature is allowed to compose instead of forking:
# the single API client, the money pipe, and existing services/repositories.
_FEATURE_NAMES = {"ApiService", "MoneyPipe"}


@dataclass
class FileReview:
    path: str
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.violations


@dataclass
class ReviewResult:
    files: List[FileReview]

    @property
    def passed(self) -> bool:
        return all(f.passed for f in self.files) and bool(self.files)

    @property
    def n_violations(self) -> int:
        return sum(len(f.violations) for f in self.files)


@dataclass
class GateOutcome:
    """Result of one gate evaluation in the repair loop (roadmap M2): the static
    compliance review plus any real tsc/jest results, reduced to pass/fail and a
    flat list of human-readable feedback strings the Developer can act on."""
    passed: bool
    feedback: List[str]
    review: "ReviewResult"
    tests: list = field(default_factory=list)


def gate_feedback(review: "ReviewResult", tests: list | None = None) -> List[str]:
    """Flatten a review (+ optional real-check results) into actionable feedback
    lines for the Developer's next repair attempt."""
    lines = [f"{fr.path}: {v}" for fr in review.files for v in fr.violations]
    for r in tests or []:
        if not getattr(r, "skipped", False) and not getattr(r, "passed", True):
            first = (r.detail.splitlines()[-1][:160] if getattr(r, "detail", "") else "")
            lines.append(f"{r.name} failed: {first}")
    return lines


def _strip_comments(src: str) -> str:
    """Remove block and line comments so checks don't trip on commentary."""
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.DOTALL)
    src = re.sub(r"//.*", "", src)
    return src


def _is_test(path: str) -> bool:
    return "__tests__" in path or ".test." in path or ".spec." in path


def check_file(path: str, content: str) -> FileReview:
    fr = FileReview(path=path)
    code = _strip_comments(content)  # ignore comments for literal checks

    # Test files are validated by the real jest run, not by syntactic rules.
    if _is_test(path):
        return fr

    is_component = bool(_COMPONENT.search(code))
    # Template/style assets (.html/.scss/.css) legitimately ship no `export` and have
    # no functions — the "must export" / return-type rules apply only to CODE files.
    suffix = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    is_code = suffix in {"ts", "tsx", "js", "jsx"}

    # Rules that apply to code files (front end and back end):
    if is_code:
        if _FETCH.search(code):
            fr.violations.append("direct fetch() call (route via ApiService/api client — context.md §4)")
        if not _EXPORT.search(code):
            fr.violations.append("no export found (file ships nothing)")

    # Security scan (roadmap M7): hard-fail on hardcoded secrets or dynamic eval.
    if _SECRET.search(code) or _AWS_KEY.search(code):
        fr.violations.append("hardcoded credential/secret literal (use env/config — security)")
    if _DANGER.search(code):
        fr.violations.append("dynamic code execution (eval/new Function/child_process — security)")

    # Front-end-component-specific rules (design tokens, primitive reuse, HttpClient):
    if is_component:
        if _HEX.search(code):
            fr.violations.append("inline hex color literal (use design tokens — context.md §3)")
        if _HTTPCLIENT.search(code):
            fr.violations.append("component uses HttpClient directly (route via ApiService — context.md §4)")
        import_text = " ".join(l for l in code.splitlines() if l.strip().startswith("import"))
        reuses = any(name in import_text for name in (_PRIMITIVE_NAMES | _FEATURE_NAMES))
        if not reuses:
            fr.violations.append("screen does not reuse any canonical primitive (context.md §3)")
        if "tokens" not in code and "var(--" not in code:
            fr.warnings.append("does not reference design tokens")

    if is_code and not _RETURN_TYPE.search(code):
        fr.warnings.append("no explicit return type on an exported function")
    return fr


def review_files(files: List[dict]) -> ReviewResult:
    """files: [{path, content}] (content as written)."""
    return ReviewResult(files=[check_file(f["path"], f.get("content", "")) for f in files])


def evidence_from_files(files: List[dict]) -> dict:
    """Roadmap M6 — score the change against POST-EXECUTION facts, not the plan's
    prose: which canonical primitives / shared building blocks the generated code
    actually reuses, and how many files it touched. This is observable evidence the
    Debate's reuse claim was honored, independent of how the plan was worded."""
    reused = set()
    for f in files:
        code = _strip_comments(f.get("content", ""))
        for name in (_PRIMITIVE_NAMES | _FEATURE_NAMES):
            if name in code:
                reused.add(name)
    return {
        "reused_components": sorted(reused),
        "files_touched": [f.get("path") for f in files],
        "n_files": len(files),
    }


def write_review_md(exec_result, review: ReviewResult, out_dir: Path, checks=None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "REVIEW.md"
    checks = checks or []
    ran = [c for c in checks if not c.skipped]
    tests_ok = all(c.passed for c in ran)
    gate_ok = review.passed and tests_ok
    status = "PASS ✅ — ready for human review" if gate_ok else "FAIL ❌ — fix before review"
    lines = [
        "# REVIEW.md — Phase 4 (Test & Human-in-the-Loop)",
        "",
        f"**Automated gate: {status}**",
        "",
        f"- Branch: `{exec_result.branch}` (in isolated copy: `{exec_result.workdir}`)",
        f"- Generated by: `{exec_result.provider}` "
        f"({'live model' if exec_result.is_live else 'deterministic mock'})",
        f"- Files changed: {', '.join(exec_result.changed_files) or '—'}",
        "",
    ]
    attempt_log = getattr(exec_result, "attempt_log", []) or []
    if len(attempt_log) > 1 or any(not a.get("passed") for a in attempt_log):
        lines += ["## Repair loop (roadmap M2)", ""]
        lines.append(
            f"The gate ran {len(attempt_log)} attempt(s); the Developer was re-asked "
            f"with the violations fed back until the gate passed (max "
            f"{getattr(exec_result, 'max_attempts', len(attempt_log))})."
        )
        lines.append("")
        for a in attempt_log:
            icon = "✅" if a.get("passed") else "🔁"
            head = f"- {icon} **Attempt {a.get('round')}** — {'PASS' if a.get('passed') else 'failed, repairing'}"
            lines.append(head)
            for v in a.get("violations", [])[:8]:
                lines.append(f"    - {v}")
        lines.append("")
    if checks:
        lines += ["## Real checks (tsc + jest, run in the isolated copy)", ""]
        for c in checks:
            icon = "⏭️" if c.skipped else ("✅" if c.passed else "❌")
            lines.append(f"- {icon} **{c.name}** — {c.mark}" + (f": {c.detail.splitlines()[0]}" if c.detail and not c.passed else ""))
        lines.append("")
    lines += [
        "## Compliance results",
        "",
    ]
    for fr in review.files:
        head = "PASS" if fr.passed else "FAIL"
        lines.append(f"### [{head}] `{fr.path}`")
        lines.append("")
        for v in fr.violations:
            lines.append(f"- ❌ {v}")
        for w in fr.warnings:
            lines.append(f"- ⚠️ {w}")
        if not fr.violations and not fr.warnings:
            lines.append("- ✅ all checks passed")
        lines.append("")

    lines += [
        "## Diff",
        "",
        "```diff",
        exec_result.diff.strip() or "(no diff)",
        "```",
        "",
        "## Human-in-the-loop — your decision",
        "",
        "The pipeline has **halted and will not merge.** To act on this change:",
        "",
        f"- **Inspect:** `cd {exec_result.workdir} && git diff main..{exec_result.branch}`",
        "- **Approve:** merge the branch, or copy the reviewed file(s) into `target_repo/`.",
        "- **Reject:** delete the isolated copy under `out/exec/` and adjust the plan.",
        "",
        "_No production system was touched; all work is confined to the isolated copy._",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path
