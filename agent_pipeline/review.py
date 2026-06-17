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

    # Rules that apply everywhere (front end and back end):
    if _FETCH.search(code):
        fr.violations.append("direct fetch() call (route via ApiService/api client — context.md §4)")
    if not _EXPORT.search(code):
        fr.violations.append("no export found (file ships nothing)")

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

    if not _RETURN_TYPE.search(code):
        fr.warnings.append("no explicit return type on an exported function")
    return fr


def review_files(files: List[dict]) -> ReviewResult:
    """files: [{path, content}] (content as written)."""
    return ReviewResult(files=[check_file(f["path"], f["content"]) for f in files])


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
