"""Structured feature intake — the ProblemPacket contract (spec §5–§8, §17, §18).

The pipeline's weakest input was a raw ``requirement: str``: downstream agents could
design, plan, code, and evaluate against unstated assumptions. This module adds a
structured **ProblemPacket** — the canonical, *living* source of truth for a feature —
built from JSON or Markdown intake, with:

- required minimum fields enforced (title, requirement, goal/pain, desired outcome, ≥1
  acceptance criterion) so nothing plans without a measurable definition of done;
- optional fields that default to ``unknown``/``not_provided`` rather than being silently
  treated as "no constraint";
- explicit **assumptions** and **open questions** kept separate from facts;
- a **readiness** score (can_plan / can_execute / can_evaluate);
- ``requirement_text(packet)`` so the existing agents run unchanged (backward compatible);
- living-packet versioning (change_log / obsolete_items / reusable_items, §18).

Plain dataclasses only — no new dependency (spec §16 decision 1).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Literal, Optional

UnknownText = str  # "unknown" | "not_provided" | free text

REQUIRED_FIELDS = [
    "feature_title", "user_requirement", "user_goal_or_pain",
    "desired_outcome", "acceptance_criteria",
]


@dataclass
class SystemContext:
    repo: str = "target_repo"
    modules: List[str] = field(default_factory=list)
    related_files: List[str] = field(default_factory=list)
    related_apis: List[str] = field(default_factory=list)
    related_database_tables: List[str] = field(default_factory=list)
    screenshots_or_links: List[str] = field(default_factory=list)
    notes: UnknownText = "not_provided"

    def is_known(self) -> bool:
        return bool(self.modules or self.related_files or self.related_apis
                    or self.related_database_tables)


@dataclass
class ConstraintSet:
    deadline: UnknownText = "unknown"
    budget: UnknownText = "unknown"
    security: UnknownText = "unknown"
    privacy: UnknownText = "unknown"
    performance: UnknownText = "unknown"
    deployment: UnknownText = "unknown"
    compatibility: UnknownText = "unknown"
    maintainability: UnknownText = "unknown"


@dataclass
class EvaluationMethod:
    type: Literal[
        "unit_test", "integration_test", "benchmark", "human_review",
        "real_user_review", "llm_rubric", "manual_qa", "other",
    ]
    description: str
    required: bool = True


@dataclass
class Assumption:
    id: str
    text: str
    risk: Literal["low", "medium", "high"] = "low"
    needs_human_confirmation: bool = False


@dataclass
class OpenQuestion:
    id: str
    question: str
    blocks_planning: bool = False
    blocks_execution: bool = False
    blocks_evaluation: bool = False


@dataclass
class IntakeReadiness:
    can_plan: bool
    can_execute: bool
    can_evaluate: bool
    missing_critical_fields: List[str] = field(default_factory=list)


# --- Living packet (spec §18.6) --------------------------------------------- #
@dataclass
class ChangeRequest:
    from_text: str
    to_text: str
    reason: str
    source: Literal["human_review", "real_user_feedback", "test_failure",
                    "developer_discovery", "other"] = "other"
    impact: Literal["minor", "medium", "major"] = "minor"


@dataclass
class ObsoleteItem:
    item: str
    reason: str
    superseded_by: Optional[str] = None


@dataclass
class ReusableItem:
    item: str
    reason: str
    confidence: Literal["low", "medium", "high"] = "medium"


@dataclass
class ProblemPacket:
    feature_title: str
    user_requirement: str
    user_goal_or_pain: str
    desired_outcome: str
    acceptance_criteria: List[str]

    requester_type: UnknownText = "not_provided"
    current_behavior: UnknownText = "not_provided"
    existing_system_context: SystemContext = field(default_factory=SystemContext)
    software_engineer_requirements: List[str] = field(default_factory=list)
    constraints: ConstraintSet = field(default_factory=ConstraintSet)
    non_goals: List[str] = field(default_factory=list)
    tradeoff_preference: List[str] = field(default_factory=list)
    evaluation_method: List[EvaluationMethod] = field(default_factory=list)
    human_decision_points: List[str] = field(default_factory=list)
    feedback_source: List[str] = field(default_factory=list)

    assumptions: List[Assumption] = field(default_factory=list)
    open_questions: List[OpenQuestion] = field(default_factory=list)
    readiness: Optional[IntakeReadiness] = None

    # living-packet (spec §18)
    version: int = 1
    previous_packet_id: Optional[str] = None
    change_log: List[ChangeRequest] = field(default_factory=list)
    obsolete_items: List[ObsoleteItem] = field(default_factory=list)
    reusable_items: List[ReusableItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Validation, readiness, questions
# --------------------------------------------------------------------------- #
def validate_packet(packet: ProblemPacket) -> List[str]:
    """Return a list of problems (empty means the required minimum is satisfied)."""
    problems: List[str] = []
    for name in REQUIRED_FIELDS:
        val = getattr(packet, name, None)
        if name == "acceptance_criteria":
            if not val or not any(str(c).strip() for c in val):
                problems.append("acceptance_criteria: at least one concrete criterion is required")
        elif not str(val or "").strip():
            problems.append(f"{name}: required field is empty")
    return problems


def compute_readiness(packet: ProblemPacket) -> IntakeReadiness:
    """Score whether the feature is ready for each stage (spec §8)."""
    missing = validate_packet(packet)
    can_plan = not missing
    can_execute = can_plan and packet.existing_system_context.is_known()
    can_evaluate = bool(packet.acceptance_criteria) and bool(packet.evaluation_method)
    return IntakeReadiness(
        can_plan=can_plan,
        can_execute=can_execute,
        can_evaluate=can_evaluate,
        missing_critical_fields=[m.split(":")[0] for m in missing],
    )


def questions_for_packet(packet: ProblemPacket) -> List[OpenQuestion]:
    """Generate open questions only where missing info affects a stage (spec §10.1)."""
    qs: List[OpenQuestion] = []
    for m in validate_packet(packet):
        field_name = m.split(":")[0]
        qs.append(OpenQuestion(
            id=f"req-{field_name}",
            question=f"Required field '{field_name}' is missing — please provide it.",
            blocks_planning=True, blocks_execution=True, blocks_evaluation=True,
        ))
    if not packet.evaluation_method:
        qs.append(OpenQuestion(
            id="eval-method",
            question="How should we know this feature works: tests, benchmark, human "
                     "review, or real user feedback?",
            blocks_evaluation=True,
        ))
    if not packet.existing_system_context.is_known():
        qs.append(OpenQuestion(
            id="system-context",
            question="Which module/API/page/table does this touch? Naming it lets the "
                     "planner ground the change in the right files.",
            blocks_execution=True,
        ))
    return qs


def finalize(packet: ProblemPacket) -> ProblemPacket:
    """Attach computed readiness + open questions to the packet (idempotent)."""
    packet.readiness = compute_readiness(packet)
    # merge generated questions with any provided, de-duplicating by id
    existing_ids = {q.id for q in packet.open_questions}
    for q in questions_for_packet(packet):
        if q.id not in existing_ids:
            packet.open_questions.append(q)
    return packet


def requirement_text(packet: ProblemPacket) -> str:
    """A rich prompt-compatible requirement string so existing agents run unchanged."""
    ac = "\n".join(f"- {c}" for c in packet.acceptance_criteria) or "- not_provided"
    non_goals = "\n".join(f"- {n}" for n in packet.non_goals) or "- not_provided"
    tradeoff = ", ".join(packet.tradeoff_preference) or "not_provided"
    return (
        f"FEATURE TITLE:\n{packet.feature_title}\n\n"
        f"USER REQUIREMENT:\n{packet.user_requirement}\n\n"
        f"USER GOAL / PAIN:\n{packet.user_goal_or_pain}\n\n"
        f"DESIRED OUTCOME:\n{packet.desired_outcome}\n\n"
        f"ACCEPTANCE CRITERIA:\n{ac}\n\n"
        f"CONSTRAINTS:\n"
        f"- deadline: {packet.constraints.deadline}\n"
        f"- budget: {packet.constraints.budget}\n"
        f"- security: {packet.constraints.security}\n"
        f"- privacy: {packet.constraints.privacy}\n"
        f"- performance: {packet.constraints.performance}\n\n"
        f"NON-GOALS:\n{non_goals}\n\n"
        f"TRADE-OFF PREFERENCE:\n{tradeoff}"
    ).strip()


# --------------------------------------------------------------------------- #
# Loading — JSON (canonical) and Markdown (human)
# --------------------------------------------------------------------------- #
def packet_from_dict(data: dict) -> ProblemPacket:
    """Build a ProblemPacket from a plain dict (the JSON canonical form)."""
    sc = data.get("existing_system_context") or {}
    cs = data.get("constraints") or {}
    ems = data.get("evaluation_method") or []
    packet = ProblemPacket(
        feature_title=str(data.get("feature_title", "")).strip(),
        user_requirement=str(data.get("user_requirement", "")).strip(),
        user_goal_or_pain=str(data.get("user_goal_or_pain", "")).strip(),
        desired_outcome=str(data.get("desired_outcome", "")).strip(),
        acceptance_criteria=[str(c).strip() for c in (data.get("acceptance_criteria") or []) if str(c).strip()],
        requester_type=data.get("requester_type", "not_provided"),
        current_behavior=data.get("current_behavior", "not_provided"),
        existing_system_context=SystemContext(
            repo=sc.get("repo", "target_repo"),
            modules=list(sc.get("modules", [])),
            related_files=list(sc.get("related_files", [])),
            related_apis=list(sc.get("related_apis", [])),
            related_database_tables=list(sc.get("related_database_tables", [])),
            screenshots_or_links=list(sc.get("screenshots_or_links", [])),
            notes=sc.get("notes", "not_provided"),
        ),
        software_engineer_requirements=list(data.get("software_engineer_requirements", [])),
        constraints=ConstraintSet(**{k: cs[k] for k in cs if k in ConstraintSet.__dataclass_fields__}),
        non_goals=list(data.get("non_goals", [])),
        tradeoff_preference=list(data.get("tradeoff_preference", [])),
        evaluation_method=[
            EvaluationMethod(type=e.get("type", "other"), description=e.get("description", ""),
                             required=bool(e.get("required", True)))
            for e in ems if isinstance(e, dict)
        ],
        human_decision_points=list(data.get("human_decision_points", [])),
        feedback_source=list(data.get("feedback_source", [])),
        version=int(data.get("version", 1)),
        previous_packet_id=data.get("previous_packet_id"),
    )
    return finalize(packet)


def _clean_heading(h: str) -> str:
    # "## 5. Acceptance criteria" -> "acceptance criteria"
    h = h.lstrip("#").strip()
    parts = h.split(".", 1)
    if parts[0].strip().isdigit() and len(parts) == 2:
        h = parts[1]
    return h.strip().lower()


def _bullets(block: str) -> List[str]:
    out = []
    for line in block.splitlines():
        s = line.strip()
        if s.startswith(("- ", "* ")):
            item = s[2:].strip()
            if item and item.lower() not in ("...", "…"):
                out.append(item)
    return out


def _first_text(block: str) -> str:
    for line in block.splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            return s
    return ""


def packet_from_markdown(text: str) -> ProblemPacket:
    """Best-effort parse of the intake Markdown template (spec §11) into a packet.

    Section headings are matched by keyword; JSON remains the canonical machine format,
    so anything ambiguous stays a default (unknown/not_provided) rather than a guess.
    """
    # split into (heading -> body) sections
    sections: dict[str, str] = {}
    current = None
    buf: List[str] = []
    for line in text.splitlines():
        if line.lstrip().startswith("##"):
            if current is not None:
                sections[current] = "\n".join(buf).strip()
            current = _clean_heading(line)
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        sections[current] = "\n".join(buf).strip()

    def find(*keywords: str) -> str:
        for key, body in sections.items():
            if all(k in key for k in keywords):
                return body
        return ""

    sc_block = find("existing", "system")
    constraints_block = find("constraint")
    eval_block = find("evaluation")

    data = {
        "feature_title": _first_text(find("feature", "title")),
        "user_requirement": _first_text(find("user", "requirement")),
        "user_goal_or_pain": _first_text(find("goal")) or _first_text(find("pain")),
        "desired_outcome": _first_text(find("desired", "outcome")),
        "acceptance_criteria": _bullets(find("acceptance")),
        "current_behavior": _first_text(find("current", "behavior")) or "not_provided",
        "software_engineer_requirements": _bullets(find("engineer")),
        "non_goals": _bullets(find("non-goal")) or _bullets(find("out of scope")),
        "tradeoff_preference": _bullets(find("trade")),
        "human_decision_points": _bullets(find("human", "decision")),
        "feedback_source": _bullets(find("feedback")),
        "existing_system_context": _system_context_from_bullets(sc_block),
        "constraints": _constraints_from_bullets(constraints_block),
        "evaluation_method": _eval_methods_from_bullets(eval_block),
    }
    return packet_from_dict(data)


def _kv_bullets(block: str) -> dict:
    """Parse '- Key: value' bullets into a lowercased dict."""
    out: dict[str, str] = {}
    for item in _bullets(block):
        if ":" in item:
            k, _, v = item.partition(":")
            out[k.strip().lower()] = v.strip()
    return out


def _system_context_from_bullets(block: str) -> dict:
    kv = _kv_bullets(block)
    def split(v: str) -> List[str]:
        return [x.strip() for x in v.split(",") if x.strip()] if v else []
    apis = kv.get("related api") or kv.get("related page/api") or kv.get("current api", "")
    return {
        "modules": split(kv.get("repo/module") or kv.get("related module") or kv.get("module", "")),
        "related_files": split(kv.get("related files") or kv.get("related file", "")),
        "related_apis": split(apis),
        "related_database_tables": split(kv.get("database") or kv.get("database/schema") or kv.get("table", "")),
        "screenshots_or_links": split(kv.get("screenshots/links") or kv.get("links", "")),
    }


def _constraints_from_bullets(block: str) -> dict:
    kv = _kv_bullets(block)
    alias = {
        "deadline": "deadline", "cost": "budget", "budget": "budget",
        "security": "security", "security/privacy": "security", "privacy": "privacy",
        "performance": "performance", "deployment": "deployment",
        "compatibility": "compatibility", "maintainability": "maintainability",
    }
    out: dict[str, str] = {}
    for k, v in kv.items():
        if k in alias and v:
            out[alias[k]] = v
    return out


def _eval_methods_from_bullets(block: str) -> List[dict]:
    methods = []
    type_map = {
        "unit test": "unit_test", "integration test": "integration_test",
        "benchmark": "benchmark", "human review": "human_review",
        "real user": "real_user_review", "rubric": "llm_rubric", "manual qa": "manual_qa",
    }
    for item in _bullets(block):
        low = item.lower()
        etype = next((v for k, v in type_map.items() if k in low), "other")
        methods.append({"type": etype, "description": item})
    return methods


def load_intake(path: str | Path) -> ProblemPacket:
    """Load a ProblemPacket from a ``.json`` or ``.md`` intake file (spec §17)."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"intake file not found: {path}")
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return packet_from_dict(json.loads(text))
    if path.suffix.lower() in (".md", ".markdown"):
        return packet_from_markdown(text)
    # fall back on content sniffing
    stripped = text.lstrip()
    return packet_from_dict(json.loads(text)) if stripped.startswith("{") else packet_from_markdown(text)
