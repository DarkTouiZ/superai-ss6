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


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return s[:40] or "feature"


def _build_user_prompt(requirement: str, winner: dict, design: dict) -> str:
    grounding = {
        "task": "code",
        "requirement": requirement,
        "primitives": sorted(config.CANONICAL_PRIMITIVES),
        "services": [s for s in design.get("services_used", [])],
    }
    return (
        f"REQUIREMENT:\n{requirement}\n\n"
        f"WINNING PLAN (id {winner.get('id')}, focus {winner.get('priority_focus')}):\n"
        f"{json.dumps(winner, indent=2)}\n\n"
        f"DESIGN ARTIFACTS:\n{json.dumps(design, indent=2)}\n\n"
        f"SYSTEM BLUEPRINT (context.md):\n{config.CONTEXT_FILE.read_text(encoding='utf-8')}\n\n"
        f"<<GROUNDING:{json.dumps(grounding)}>>\n"
    )


class DeveloperAgent:
    def __init__(self) -> None:
        self.llm = get_llm()

    def generate_files(self, requirement: str, winner: dict, design: dict) -> List[dict]:
        user = _build_user_prompt(requirement, winner, design)
        resp = self.llm.complete(SYSTEM_PROMPT, user)
        files = self._parse(resp.text)
        self._provider, self._is_live = resp.provider, resp.is_live
        return files

    def execute(self, requirement: str, winner: dict, design: dict) -> ExecResult:
        files = self.generate_files(requirement, winner, design)
        slug = _slug(requirement)
        wc = vcs.make_working_copy(slug)
        branch = f"ss6/{slug}"
        vcs.create_branch(wc, branch)

        for f in files:
            rel = f["path"]
            # write under the repo's src/ tree; normalize to a clean repo-relative path
            rel = rel[len("target_repo/"):] if rel.startswith("target_repo/") else rel
            dest = wc.path / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(f["content"], encoding="utf-8")

        vcs.commit_all(wc, f"feat: {requirement[:60]} (Plan {winner.get('id')})")
        return ExecResult(
            branch=branch,
            files=files,
            workdir=str(wc.path),
            diff=vcs.diff_against_base(wc),
            diff_stat=vcs.diff_stat(wc),
            changed_files=vcs.changed_files(wc),
            provider=getattr(self, "_provider", "mock"),
            is_live=getattr(self, "_is_live", False),
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
            if "path" not in f or "content" not in f:
                raise ValueError("each file needs 'path' and 'content'.")
        return files
