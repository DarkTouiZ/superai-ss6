"""Developer agent — Phase 3b ("Execute").

Takes the debate-winning plan plus the design artifacts and writes the code into an
**isolated git copy** of the target repo on a new feature branch. It never edits the
real repo — the human reviews the branch diff and decides.

Code generation is provider-agnostic (Ollama / Gemini / Anthropic / mock). The model
is asked for ``{"files":[{"path","content"}]}`` grounded in the design and the
canonical primitives; the deterministic mock returns a compliant feature file so the
whole Execute→Review chain runs offline.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import List, Optional

from agent_pipeline import config, vcs
from agent_pipeline.llm import get_llm
from agent_pipeline.normalize import canonical_path

SYSTEM_PROMPT = (
    "You are the Developer agent in an autonomous software-engineering pipeline for "
    "eleven-7 (Node.js + Express backend, Angular frontend, MySQL, AWS SNS/SQS/SMS). "
    "Implement the WINNING plan, strictly obeying the System Blueprint (context.md): "
    "compose the canonical Angular primitives instead of re-implementing UI; use the "
    "design tokens in tokens.scss only (no inline hex colors or magic numbers); the "
    "frontend talks to the API only through ApiService (never fetch/HttpClient in a "
    "component); backend DB access goes through repositories and AWS access through "
    "src/aws/*; business logic lives in services, not controllers/components; give "
    "exported functions explicit return types. Respond with a single JSON object "
    "{\"files\":[{\"path\":\"frontend/src/...\" or \"backend/src/...\",\"content\":\"<full file>\"}]}. "
    "Output complete, compilable TypeScript."
)


@dataclass
class ExecResult:
    branch: str
    files: List[dict]            # [{path, content}] as written
    workdir: str                # isolated repo path
    diff: str
    diff_stat: str
    changed_files: List[str]
    provider: str
    is_live: bool
    attempts: int = 1                       # how many generate→gate rounds ran
    attempt_log: List[dict] = None          # [{round, passed, violations[]}]
    max_attempts: int = 1
    repaired: bool = False                  # True if it failed then passed via repair
    gate_review: object = None              # final ReviewResult (set by the gate)
    gate_tests: List = None                 # final real-check results (set by the gate)

    def __post_init__(self) -> None:
        if self.attempt_log is None:
            self.attempt_log = []
        if self.gate_tests is None:
            self.gate_tests = []


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40] or "feature"


def _build_user_prompt(
    requirement: str,
    winner: dict,
    design: dict,
    feedback: Optional[List[str]] = None,
    repair_round: int = 0,
) -> str:
    grounding = {
        "task": "code",
        "requirement": requirement,
        "primitives": sorted(config.CANONICAL_PRIMITIVES),
        "services": [s for s in design.get("services_used", [])],
        "repair_round": repair_round,
        "prior_violations": feedback or [],
    }
    repair_block = ""
    if feedback:
        bullets = "\n".join(f"  - {v}" for v in feedback)
        repair_block = (
            "\nYOUR PREVIOUS ATTEMPT FAILED THE GATE. Fix EVERY violation below and "
            "resubmit the COMPLETE corrected files (same JSON shape). Do not introduce "
            "new violations:\n"
            f"{bullets}\n"
        )
    return (
        f"REQUIREMENT:\n{requirement}\n\n"
        f"WINNING PLAN (id {winner.get('id')}, focus {winner.get('priority_focus')}):\n"
        f"{json.dumps(winner, indent=2)}\n\n"
        f"DESIGN ARTIFACTS:\n{json.dumps(design, indent=2)}\n\n"
        f"SYSTEM BLUEPRINT (context.md):\n{config.CONTEXT_FILE.read_text(encoding='utf-8')}\n"
        f"{repair_block}\n"
        f"<<GROUNDING:{json.dumps(grounding)}>>\n"
    )


class DeveloperAgent:
    def __init__(self) -> None:
        self.llm = get_llm()

    def generate_files(
        self,
        requirement: str,
        winner: dict,
        design: dict,
        feedback: Optional[List[str]] = None,
        repair_round: int = 0,
    ) -> List[dict]:
        user = _build_user_prompt(requirement, winner, design, feedback, repair_round)
        resp = self.llm.complete(SYSTEM_PROMPT, user)
        files = self._parse(resp.text)
        self._provider, self._is_live = resp.provider, resp.is_live
        return files

    @staticmethod
    def _apply_edits(existing: str, edits: List[dict]) -> tuple[str, List[str]]:
        """Apply anchored edits to existing file text (roadmap M3). Idempotent: an
        edit whose payload is already present is skipped, so re-running across repair
        attempts never double-inserts. Returns (new_text, conflicts)."""
        text = existing
        conflicts: List[str] = []
        for e in edits:
            anchor = e.get("anchor")
            if "replace" in e:
                payload = e["replace"]
                if payload and payload in text:
                    continue  # already applied
                if not anchor or anchor not in text:
                    conflicts.append(f"replace anchor not found: {anchor!r}")
                    continue
                text = text.replace(anchor, payload, 1)
            elif "insert_after" in e or "insert_before" in e:
                payload = e.get("insert_after") or e.get("insert_before")
                if payload and payload in text:
                    continue  # already applied (idempotent)
                if not anchor or anchor not in text:
                    conflicts.append(f"insert anchor not found: {anchor!r}")
                    continue
                text = (
                    text.replace(anchor, anchor + payload, 1)
                    if "insert_after" in e
                    else text.replace(anchor, payload + anchor, 1)
                )
            else:
                conflicts.append("edit had no replace/insert_after/insert_before")
        return text, conflicts

    @classmethod
    def _write_files(cls, wc, files: List[dict]) -> tuple[List[dict], List[str]]:
        """Write generated files into the working copy. An entry may be a full file
        ({path, content}) or a surgical edit of an existing file ({path, edits:[...]}
        — roadmap M3). Returns (effective_files, conflicts) where effective_files are
        {path, content} reflecting the final on-disk content (used for the gate)."""
        effective: List[dict] = []
        conflicts: List[str] = []
        for f in files:
            rel = f["path"]
            # write under the repo's src/ tree; normalize to a clean repo-relative path
            rel = rel[len("target_repo/"):] if rel.startswith("target_repo/") else rel
            dest = wc.path / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            edits = f.get("edits") or ([f["edit"]] if "edit" in f else None)
            if "diff" in f:
                # roadmap M3 (full): apply a real unified diff via git apply --3way.
                ok, msg = vcs.apply_patch(wc, f["diff"])
                if not ok:
                    conflicts.append(f"{rel}: patch did not apply ({msg})")
                final = dest.read_text(encoding="utf-8") if dest.exists() else ""
                effective.append({"path": f["path"], "content": final, "patched": True})
            elif edits is not None:
                existing = dest.read_text(encoding="utf-8") if dest.exists() else ""
                if not existing:
                    conflicts.append(f"{rel}: target file to edit does not exist")
                new_text, probs = cls._apply_edits(existing, edits)
                conflicts += [f"{rel}: {p}" for p in probs]
                dest.write_text(new_text, encoding="utf-8")
                effective.append({"path": f["path"], "content": new_text, "edited": True})
            else:
                dest.write_text(f["content"], encoding="utf-8")
                effective.append({"path": f["path"], "content": f["content"]})
        return effective, conflicts

    def execute(
        self,
        requirement: str,
        winner: dict,
        design: dict,
        gate=None,
        max_attempts: int = 1,
    ) -> ExecResult:
        """Generate code on an isolated branch. When a ``gate`` callable is supplied,
        run the **repair loop** (roadmap M2): write files → gate → if it fails, feed
        the violations back and regenerate, up to ``max_attempts`` times. Only the
        final (best) attempt is committed.

        ``gate`` signature: ``gate(files, workdir) -> GateOutcome`` (``.passed``,
        ``.feedback``, ``.review``, ``.tests``).
        """
        slug = _slug(requirement)
        wc = vcs.make_working_copy(slug)
        branch = f"ss6/{slug}"
        vcs.create_branch(wc, branch)

        max_attempts = max(1, int(max_attempts))
        feedback: Optional[List[str]] = None
        attempt_log: List[dict] = []
        effective: List[dict] = []
        final_outcome = None

        for attempt in range(1, max_attempts + 1):
            files = self.generate_files(
                requirement, winner, design, feedback=feedback, repair_round=attempt - 1
            )
            effective, conflicts = self._write_files(wc, files)
            if gate is None:
                attempt_log.append({"round": attempt, "passed": not conflicts, "violations": conflicts})
                if not conflicts:
                    break
                feedback = [f"edit conflict — {c}" for c in conflicts]
                continue
            outcome = gate(effective, str(wc.path))
            if conflicts:  # an anchored edit that didn't apply is a hard failure
                outcome.passed = False
                outcome.feedback = list(outcome.feedback) + [f"edit conflict — {c}" for c in conflicts]
            final_outcome = outcome
            attempt_log.append(
                {"round": attempt, "passed": outcome.passed, "violations": list(outcome.feedback)}
            )
            if outcome.passed:
                break
            feedback = outcome.feedback  # carry violations into the next attempt

        vcs.commit_all(wc, f"feat: {requirement[:60]} (Plan {winner.get('id')})")
        repaired = len(attempt_log) > 1 and attempt_log[-1]["passed"]
        return ExecResult(
            branch=branch,
            files=effective,
            workdir=str(wc.path),
            diff=vcs.diff_against_base(wc),
            diff_stat=vcs.diff_stat(wc),
            changed_files=vcs.changed_files(wc),
            provider=getattr(self, "_provider", "mock"),
            is_live=getattr(self, "_is_live", False),
            attempts=len(attempt_log),
            attempt_log=attempt_log,
            max_attempts=max_attempts,
            repaired=repaired,
            gate_review=getattr(final_outcome, "review", None),
            gate_tests=list(getattr(final_outcome, "tests", []) or []),
        )

    @staticmethod
    def _parse(text: str) -> List[dict]:
        s = text.strip()
        if "```" in s and "{" not in s.split("```")[0]:
            s = s.split("```")[1]
            s = s[4:] if s.lower().startswith("json") else s
        start, end = s.find("{"), s.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("Developer response contained no JSON object.")
        obj = json.loads(s[start : end + 1])
        files = obj.get("files", [])
        if not files:
            raise ValueError("Developer response had no files.")
        for f in files:
            if "path" not in f:
                raise ValueError("each file needs a 'path'.")
            if not any(key in f for key in ("content", "edit", "edits", "diff")):
                raise ValueError("each file needs 'content', 'edit'/'edits', or 'diff'.")
        return files
