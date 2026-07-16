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
    # True when the only reason the gate did not pass is a required check that could not
    # RUN (UNVERIFIED) — compliance is clean and nothing FAILED. No code change can fix a
    # missing tool, so the repair loop must halt rather than regenerate (spec §22.3).
    unverified_only: bool = False


def gate_feedback(review: "ReviewResult", tests: list | None = None) -> List[str]:
    """Flatten a review (+ optional real-check results) into actionable feedback
    lines for the Developer's next repair attempt. A required check that could not
    run (UNVERIFIED, spec §22.3) is surfaced too — it blocks the gate, so the
    reviewer must see it rather than have it vanish as a silent skip."""
    lines = [f"{fr.path}: {v}" for fr in review.files for v in fr.violations]
    for r in tests or []:
        status = getattr(r, "status", "")
        detail = getattr(r, "detail", "")
        first = detail.splitlines()[-1][:160] if detail else ""
        if status == "FAIL":
            lines.append(f"{r.name} failed: {first}")
        elif status == "UNVERIFIED":
            lines.append(f"{r.name} UNVERIFIED (required check could not run): {first}")
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


def _evidence_sections(context: dict) -> List[str]:
    """Render the spec §23 evidence blocks from the plan/execute context: feature intent,
    selected plan, acceptance-criteria checklist, impact, grounding, assumptions, and the
    context.md rules in force."""
    lines: List[str] = []
    packet = context.get("problem_packet") or {}
    winner = context.get("winner") or {}
    impact = context.get("impact") or {}
    grounding = context.get("grounding") or []

    if packet:
        lines += [
            "## Feature & intent (ProblemPacket)",
            "",
            f"- Title: **{packet.get('feature_title', '—')}** · packet v{packet.get('version', 1)}",
            f"- User goal / pain: {packet.get('user_goal_or_pain', '—')}",
            f"- Desired outcome: {packet.get('desired_outcome', '—')}",
            "",
        ]

    if winner:
        lines += [
            "## Selected plan",
            "",
            f"- Plan **{winner.get('id', '?')}** — {winner.get('title', '')} "
            f"(focus: {winner.get('priority_focus', '')})",
            f"- Rollback: {winner.get('rollback_strategy', '—')}",
        ]
        fit = winner.get("packet_fit") or {}
        if fit:
            lines.append(
                f"- Fit: user-fit **{'PASS' if fit.get('user_fit_pass') else 'REVIEW'}** "
                f"(coverage {fit.get('acceptance_coverage')}), system-fit "
                f"**{'PASS' if fit.get('system_fit_pass') else 'REVIEW'}**"
                + (f" — {'; '.join(fit.get('system_fit_reasons', []))}" if fit.get('system_fit_reasons') else ""))
        lines.append("")

    covered = winner.get("acceptance_criteria_covered")
    criteria = covered if covered else [{"criterion": c, "covered": None, "evidence": []}
                                        for c in packet.get("acceptance_criteria", [])]
    if criteria:
        lines += ["## Acceptance criteria (plan-level coverage — not proof of user acceptance)", ""]
        for c in criteria:
            mark = "☑" if c.get("covered") else ("☐" if c.get("covered") is False else "•")
            ev = f" _(evidence: {', '.join(c.get('evidence', []))})_" if c.get("evidence") else ""
            lines.append(f"- {mark} {c.get('criterion', '')}{ev}")
        lines.append("")

    sec = impact.get("security_or_privacy_impact") or []
    schema = impact.get("data_or_schema_impact") or []
    contracts = impact.get("public_contracts_at_risk") or []
    protected = impact.get("protected_areas_touched") or []
    if any([sec, schema, contracts, protected]):
        lines += ["## Security / schema / contract impact", ""]
        for label, items in (("security/privacy", sec), ("data/schema", schema),
                             ("public contracts", contracts), ("protected areas", protected)):
            if items:
                lines.append(f"- **{label}:** {'; '.join(items)}")
        lines.append("")

    if grounding:
        lines += ["## Grounding used during planning (retrieval evidence)", ""]
        for g in grounding[:8]:
            lines.append(f"- `{g.get('rel_path')}:{g.get('start_line')}-{g.get('end_line')}` "
                         f"(score {g.get('score')})")
        lines.append("")

    assumptions = context.get("assumptions") or []
    open_qs = context.get("open_questions") or []
    if assumptions or open_qs:
        lines += ["## Assumptions & open questions", ""]
        for a in assumptions:
            lines.append(f"- _assumption:_ {a.get('text', a) if isinstance(a, dict) else a}")
        for q in open_qs:
            lines.append(f"- _open:_ {q.get('question', q) if isinstance(q, dict) else q}")
        lines.append("")

    lines += [
        "## context.md rules in force (enforced by the compliance gate)",
        "",
        "- §3 reuse canonical primitives; §4 ApiService-only / repositories for DB / logic in "
        "services; §5 tests + integer-satang money; no inline hex, no dynamic eval, no secrets.",
        "",
    ]
    return lines


def write_review_md(exec_result, review: ReviewResult, out_dir: Path, checks=None,
                    environment: dict | None = None, approval: dict | None = None,
                    context: dict | None = None) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "REVIEW.md"
    checks = checks or []
    # Use the canonical reducer so the human-facing verdict can never drift from the
    # machine gate (spec §22.3). checks imports only config — no cycle with review.
    from agent_pipeline import checks as checks_mod
    checks_status = checks_mod.gate_status(checks)
    tests_ok = checks_status not in ("FAIL", "UNVERIFIED")
    gate_ok = review.passed and tests_ok
    if not review.passed:
        status = "FAIL ❌ — compliance violations; fix before review"
    elif checks_status == "UNVERIFIED":
        status = "UNVERIFIED ⚠️ — required checks could not run; not ready to merge"
    elif checks_status == "FAIL":
        status = "FAIL ❌ — real checks failed; fix before review"
    else:
        status = "PASS ✅ — ready for human review"
    lines = [
        "# REVIEW.md — Phase 4 (Test & Human-in-the-Loop)",
        "",
        f"**Automated gate: {status}**",
        "",
        "_`gate_passed` means the automated technical gate passed — NOT that a human "
        "approved the merge or that the user accepted the feature (spec §23)._",
        "",
        f"- Branch: `{exec_result.branch}` (in isolated copy: `{exec_result.workdir}`)",
        f"- Generated by: `{exec_result.provider}` "
        f"({'live model' if exec_result.is_live else 'deterministic mock'})",
        f"- Files changed: {', '.join(exec_result.changed_files) or '—'}",
        "",
    ]
    if environment is not None:
        fresh = "STALE ⚠️" if environment.get("stale") else "fresh"
        lines += [
            "## Environment contract (environment.md)",
            "",
            f"- System: `{environment.get('system', 'unknown')}` · "
            f"version {environment.get('environment_version', '?')} · "
            f"verified by `{environment.get('verified_by', 'unknown')}` · **{fresh}**",
            f"- Verified at source commit: `{environment.get('last_verified_source_commit') or 'unknown'}`",
        ]
        for w in (environment.get("warnings") or [])[:6]:
            lines.append(f"  - ⚠️ {w}")
        if not environment.get("present", True):
            lines.append("  - ⚠️ environment.md absent — operational facts are unverified")
        lines.append("")
    if approval is not None:
        req = approval.get("pre_execution_approval_required")
        sufficient = approval.get("approval_sufficient_for_executed_change", True)
        rec = approval.get("pre_execution_approval_recorded")
        state = "not required" if not req else (
            "recorded ✅" if (rec and sufficient) else "MISSING/INSUFFICIENT ⚠️")
        exec_risk = approval.get("risk_level", "unknown")
        decl_risk = approval.get("declared_risk_level", exec_risk)
        risk_line = f"- Effective risk (from files actually written): **{exec_risk}**"
        if approval.get("post_execution_escalation"):
            risk_line += (f" — ⚠️ ESCALATED from declared **{decl_risk}**; the executed diff "
                          f"touched protected area(s): {', '.join(approval.get('executed_protected_areas', []))}")
        lines += [
            "## Risk & human approval (spec §21)",
            "",
            risk_line,
            f"  - reasons: {'; '.join(approval.get('risk_reasons', []) or ['n/a'])}",
            f"- Pre-execution approval: **{state}**"
            + (f" (enforced={approval.get('enforced')})" if req else ""),
        ]
        if req and not sufficient:
            lines.append("  - ⚠️ The executed change needs approval it does not have — treat as "
                         "**unapproved** and re-approve for the escalated risk before merge.")
        lines.append(
            "- Final human review before merge: **required** — the pipeline never auto-merges.")
        m = approval.get("matched_approval")
        if m:
            lines.append(f"  - approved by `{m.get('approved_by')}` at {m.get('approved_at')} "
                         f"(plan {m.get('plan_id')}, packet v{m.get('packet_version')})")
        lines.append("")
    if context:
        lines += _evidence_sections(context)
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
        lines += [f"## Real checks (selected by changed area) — status: {checks_status}", ""]
        _icon = {"PASS": "✅", "FAIL": "❌", "UNVERIFIED": "⚠️", "NOT_REQUIRED": "⏭️"}
        for c in checks:
            icon = _icon.get(getattr(c, "status", ""), "•")
            detail = f": {c.detail.splitlines()[0]}" if c.detail and not c.passed else ""
            lines.append(f"- {icon} **{c.name}** — {c.mark}{detail}")
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
        "## Human-in-the-loop — your decision (spec §21.3)",
        "",
        "The pipeline has **halted and will not merge.** Choose one:",
        "",
        f"- **APPROVE** — accept the diff for your external merge workflow "
        f"(`cd {exec_result.workdir} && git diff main..{exec_result.branch}`).",
        "- **REQUEST FIX** — feed structured feedback back into the repair loop.",
        "- **RE-PLAN** — the requirement/system understanding changed; revise the packet and re-plan.",
        "- **REJECT** — stop; the isolated copy under `out/exec/` and these artifacts are preserved.",
        "",
        "_No production system was touched; all work is confined to the isolated copy. "
        "A human — not the agent — owns the merge/deploy decision._",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path
