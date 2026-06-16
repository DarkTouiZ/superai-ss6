"""Design agent — Phase 2 enrichment ("design the requirement before planning").

Mirrors the early steps of a real SWE process: from a user requirement it produces
the design artifacts that the candidate plans are then judged against —

  * a **UML diagram** (Mermaid) of the components/services involved,
  * an **API / interface spec** (function + component-prop signatures),
  * **test cases** (functional and non-functional),
  * **UX** and **architecture** adherence notes tied to ``context.md``.

Output: ``DESIGN.md`` (human, with a rendered ```mermaid block) plus the structured
``design`` dict folded into ``plans.json``. Provider-agnostic (Ollama / Gemini /
Anthropic / mock). The artifacts are grounded in real retrieved files so the
design-quality eval can check them.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from agent_pipeline import config
from agent_pipeline.llm import get_llm
from agent_pipeline.rag.retriever import Retriever

SYSTEM_PROMPT = (
    "You are the Design agent in an autonomous software-engineering pipeline. "
    "Before any implementation plan is written, you turn a user requirement into "
    "design artifacts, obeying the System Blueprint (context.md). Reuse the canonical "
    "primitives and existing services; reference only real files from the candidate "
    "set. Respond with a single JSON object: {\"design\":{requirement, uml_mermaid, "
    "api_spec[], test_cases[{type,name}], ux_notes, architecture_notes, "
    "primitives_reused[], services_used[]}}.\n"
    "BE THOROUGH, NOT TERSE. Requirements for a complete design:\n"
    "- uml_mermaid: a valid Mermaid 'classDiagram' with AT LEAST 3 classes "
    "(the new screen/component, the services it uses, and a primitive) and their "
    "relationships (-->).\n"
    "- api_spec: AT LEAST 4 entries, each a full TypeScript-style signature "
    "(function or component props), e.g. 'computeRevenueSummary(orders: Order[], "
    "targetCents: number): RevenueSummary'.\n"
    "- test_cases: AT LEAST 6 items with at least 2 'functional' and at least 2 "
    "'non_functional'; explicitly cover empty/partial-data state (context.md §6), "
    "money precision with integer cents (context.md §5), and component reuse.\n"
    "- ux_notes and architecture_notes: each cite the specific context.md rule they "
    "satisfy. test_cases 'type' is 'functional' or 'non_functional'."
)

REQUIRED_DESIGN_FIELDS = {
    "requirement", "uml_mermaid", "api_spec", "test_cases",
    "ux_notes", "architecture_notes",
}


@dataclass
class Design:
    requirement: str
    artifacts: dict
    candidate_files: List[str]
    provider: str
    is_live: bool
    raw: str = ""


def _build_user_prompt(requirement: str, candidate_files: List[str]) -> str:
    primitives = sorted(config.CANONICAL_PRIMITIVES & set(candidate_files)) or sorted(
        config.CANONICAL_PRIMITIVES
    )
    services = [f for f in candidate_files if "/services/" in f]
    grounding = {
        "task": "design",
        "requirement": requirement,
        "candidate_files": candidate_files,
        "primitives": primitives,
        "services": services,
    }
    blueprint = config.CONTEXT_FILE.read_text(encoding="utf-8")
    return (
        f"REQUIREMENT:\n{requirement}\n\n"
        f"SYSTEM BLUEPRINT (context.md):\n{blueprint}\n\n"
        f"CANDIDATE FILES (from RAG retrieval):\n" + "\n".join(candidate_files) + "\n\n"
        f"<<GROUNDING:{json.dumps(grounding)}>>\n"
    )


class DesignAgent:
    def __init__(self, retriever: Optional[Retriever] = None) -> None:
        self.retriever = retriever or Retriever(rebuild=True)
        self.llm = get_llm()

    def generate(self, requirement: str, top_k: int = 8) -> Design:
        candidate_files = self.retriever.retrieve_paths(requirement, top_k=top_k)
        user = _build_user_prompt(requirement, candidate_files)
        resp = self.llm.complete(SYSTEM_PROMPT, user)
        artifacts = self._parse(resp.text)
        return Design(
            requirement=requirement,
            artifacts=artifacts,
            candidate_files=candidate_files,
            provider=resp.provider,
            is_live=resp.is_live,
            raw=resp.text,
        )

    @staticmethod
    def _parse(text: str) -> dict:
        s = text.strip()
        if "```" in s:
            s = s.split("```")[1]
            s = s[4:] if s.lower().startswith("json") else s
        start, end = s.find("{"), s.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("Design response contained no JSON object.")
        obj = json.loads(s[start : end + 1])
        design = obj.get("design")
        if not isinstance(design, dict):
            raise ValueError("Design response had no 'design' object.")
        return design


def write_design_md(design: Design, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    a = design.artifacts
    md_path = out_dir / "DESIGN.md"
    lines = [
        "# DESIGN.md — design artifacts",
        "",
        f"**Requirement:** {design.requirement}",
        "",
        f"_Generated by `{design.provider}` "
        f"({'live model' if design.is_live else 'deterministic mock'})._",
        "",
        "## UML",
        "",
        "```mermaid",
        a.get("uml_mermaid", "%% (no diagram)"),
        "```",
        "",
        "## API / interface spec",
        "",
    ]
    lines += [f"- `{s}`" for s in a.get("api_spec", [])] or ["- —"]
    lines += ["", "## Test cases", ""]
    for tc in a.get("test_cases", []):
        lines.append(f"- **[{tc.get('type', '?')}]** {tc.get('name', '')}")
    lines += [
        "",
        "## Adherence notes",
        "",
        f"- **UX:** {a.get('ux_notes', '—')}",
        f"- **Architecture:** {a.get('architecture_notes', '—')}",
        "",
        f"**Primitives reused:** {', '.join(a.get('primitives_reused', [])) or '—'}",
        "",
        f"**Services used:** {', '.join(a.get('services_used', [])) or '—'}",
        "",
    ]
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path
