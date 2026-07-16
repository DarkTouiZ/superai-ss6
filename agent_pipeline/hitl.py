"""Risk-based Human-in-the-Loop approval (spec §21).

The system stays agentic without a human approving every internal step: approval is
required by *risk*. Low-risk work needs only final review; medium/high-risk work must not
start executing without a recorded, matching ``HumanApproval``. An agent can never create
its own approval — approval is an explicit human action captured in an artifact
(``out/approvals.json``), never inferred from merely running ``execute`` (§21.2).

Effective risk combines the pre-planning ``ImpactAnalysis`` risk with the *chosen plan's*
``files_touched``: retrieval grounds context, but the plan states intent, so a plan that
will modify a protected area is high risk even if the requirement looked benign.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Literal, Optional

from agent_pipeline import normalize

RISK_ORDER = {"low": 0, "medium": 1, "high": 2}

Decision = Literal["approved", "changes_requested", "rejected"]
Stage = Literal["packet", "plan", "risk_exception", "final_review"]


@dataclass
class HumanApproval:
    stage: Stage
    decision: Decision
    approved_by: str
    packet_version: int
    plan_id: Optional[str] = None
    environment_version: int = 0
    risk_level: str = "low"
    approved_at: str = ""
    notes: str = ""

    def __post_init__(self) -> None:
        if not self.approved_at:
            self.approved_at = datetime.now(timezone.utc).isoformat(timespec="seconds")


def plan_protected_touches(plan: dict) -> List[str]:
    """Protected areas the chosen plan declares it will touch (files_touched)."""
    return normalize.protected_touches(plan.get("files_touched") or [])


def risk_from_files(impact: Optional[dict], files) -> tuple[str, List[str]]:
    """Effective risk from the impact level + an explicit set of file paths.

    Used both pre-execution (the plan's declared files_touched) and post-execution (the
    ACTUAL changed files from git), so a change that writes a protected area escalates to
    high even if the requirement/plan looked benign. Returns ``(risk_level, reasons)``."""
    reasons: List[str] = list((impact or {}).get("risk_reasons", []))
    risk = (impact or {}).get("proposed_risk_level", "low")
    touched = normalize.protected_touches(files or [])
    if touched:
        reasons.append(f"modifies protected area(s): {', '.join(touched)}")
        if RISK_ORDER["high"] > RISK_ORDER.get(risk, 0):
            risk = "high"
    return risk, reasons


def effective_risk(impact: Optional[dict], chosen_plan: Optional[dict]) -> tuple[str, List[str]]:
    """Effective risk from the impact level + the chosen plan's DECLARED files_touched."""
    return risk_from_files(impact, (chosen_plan or {}).get("files_touched") or [])


def requires_pre_execution_approval(risk_level: str) -> bool:
    """Medium/high risk must have a matching approved plan before execution (§21.1)."""
    return RISK_ORDER.get(risk_level, 0) >= RISK_ORDER["medium"]


# --------------------------------------------------------------------------- #
# Approval store (out/approvals.json)
# --------------------------------------------------------------------------- #
def approvals_path(out_dir: Path) -> Path:
    return Path(out_dir) / "approvals.json"


def load_approvals(out_dir: Path) -> List[HumanApproval]:
    p = approvals_path(out_dir)
    if not p.exists():
        return []
    try:
        rows = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    out: List[HumanApproval] = []
    for r in rows if isinstance(rows, list) else []:
        try:
            out.append(HumanApproval(**{k: r[k] for k in r if k in HumanApproval.__dataclass_fields__}))
        except TypeError:
            continue
    return out


def record_approval(out_dir: Path, approval: HumanApproval) -> Path:
    """Append an explicit human approval to the store (the only way approval is created)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = load_approvals(out_dir)
    existing.append(approval)
    p = approvals_path(out_dir)
    p.write_text(json.dumps([asdict(a) for a in existing], indent=2), encoding="utf-8")
    return p


def find_matching_approval(
    approvals: List[HumanApproval], *, packet_version: int, plan_id: Optional[str],
    environment_version: int, risk_level: str,
) -> Optional[HumanApproval]:
    """A valid pre-execution approval must be an approved plan-stage decision for THIS
    packet version, plan, and environment version, covering at least this risk level
    (spec §21.2). A materially changed packet (new version) invalidates a stale approval.
    """
    if plan_id is None:
        return None  # a plan with no id can never be matched (no wildcard authorization)
    for a in approvals:
        if (a.stage == "plan" and a.decision == "approved"
                and a.packet_version == packet_version
                and a.plan_id == plan_id
                and a.environment_version == environment_version
                and RISK_ORDER.get(a.risk_level, 0) >= RISK_ORDER.get(risk_level, 0)):
            return a
    return None


@dataclass
class ApprovalCheck:
    risk_level: str
    required: bool
    approved: bool
    reasons: List[str] = field(default_factory=list)
    matched: Optional[dict] = None

    @property
    def blocked(self) -> bool:
        return self.required and not self.approved


def check_execution_allowed(
    out_dir: Path, *, impact: Optional[dict], chosen_plan: Optional[dict],
    packet_version: int, environment_version: int,
    changed_files: Optional[List[str]] = None,
) -> ApprovalCheck:
    """Decide whether medium/high-risk execution may proceed given recorded approvals.

    Pre-execution (``changed_files=None``) judges risk from the plan's DECLARED
    files_touched. Post-execution, pass the ACTUAL ``changed_files`` from git so a plan
    that under-declared its touches (e.g. also wrote a migration) is re-risked and its
    prior lower-risk approval no longer suffices (spec §21 escalation)."""
    if changed_files is not None:
        risk, reasons = risk_from_files(impact, changed_files)
    else:
        risk, reasons = effective_risk(impact, chosen_plan)
    required = requires_pre_execution_approval(risk)
    if not required:
        return ApprovalCheck(risk_level=risk, required=False, approved=True, reasons=reasons)
    match = find_matching_approval(
        load_approvals(out_dir),
        packet_version=packet_version,
        plan_id=(chosen_plan or {}).get("id"),
        environment_version=environment_version,
        risk_level=risk,
    )
    return ApprovalCheck(
        risk_level=risk, required=True, approved=match is not None,
        reasons=reasons, matched=asdict(match) if match else None,
    )
