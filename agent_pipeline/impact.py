"""Change-impact analysis before planning (spec §20.3).

Before Plan A/B/C are written, we produce a structured ``ImpactAnalysis`` from the
retrieved grounding + the requirement, cited against ``environment.md`` (protected areas,
risk classes) and ``context.md``. The Architect plans then respond to this shared map
rather than each inventing their own, and Phase 4's risk gate consumes the proposed risk
level. The analysis is deterministic (no LLM, $0, testable): it maps grounded file paths
to system areas and combines them with requirement keywords.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# Area detection from a repo-relative path → human-readable area label.
_AREA_RULES = [
    ("backend/db/migrations", "database schema (migrations)"),
    ("backend/src/db", "database connection layer"),
    ("backend/src/aws", "AWS messaging (SNS/SQS/SMS)"),
    ("backend/src/routes", "backend routes (public API surface)"),
    ("backend/src/controllers", "backend controllers"),
    ("backend/src/repositories", "backend repositories (DB access)"),
    ("backend/src/services", "backend services (business logic)"),
    ("backend/src/workers", "backend workers (queue consumers)"),
    ("frontend/src/app/core", "frontend core services (ApiService/MoneyPipe)"),
    ("frontend/src/app/shared", "frontend shared primitives"),
    ("frontend/src/app/features", "frontend feature screens"),
]

# Protected areas (mirrors environment.md §9): touching these is high risk.
_PROTECTED = [
    "backend/db/migrations",
    "backend/src/db",
    "backend/src/aws",
    "frontend/src/app/core/services/api.service.ts",
    "docker-compose.yml",
    "infra/",
    "localstack/",
]

_SECURITY_WORDS = {
    "auth", "authentication", "authorization", "login", "permission", "role", "rbac",
    "password", "secret", "token", "payment", "pay", "refund", "checkout", "billing",
    "pii", "privacy", "gdpr", "sensitive", "credential",
}
_SCHEMA_WORDS = {"schema", "migration", "table", "column", "index", "database", "sql"}
_CONTRACT_WORDS = {"endpoint", "api", "route", "contract", "response", "payload"}


@dataclass
class ImpactAnalysis:
    likely_affected_areas: List[str] = field(default_factory=list)
    existing_extension_points: List[str] = field(default_factory=list)
    public_contracts_at_risk: List[str] = field(default_factory=list)
    data_or_schema_impact: List[str] = field(default_factory=list)
    security_or_privacy_impact: List[str] = field(default_factory=list)
    required_checks: List[str] = field(default_factory=list)
    protected_areas_touched: List[str] = field(default_factory=list)
    unknowns: List[str] = field(default_factory=list)
    proposed_risk_level: str = "low"          # low | medium | high
    risk_reasons: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)   # path:line citations used

    def to_dict(self) -> dict:
        return {
            "likely_affected_areas": self.likely_affected_areas,
            "existing_extension_points": self.existing_extension_points,
            "public_contracts_at_risk": self.public_contracts_at_risk,
            "data_or_schema_impact": self.data_or_schema_impact,
            "security_or_privacy_impact": self.security_or_privacy_impact,
            "required_checks": self.required_checks,
            "protected_areas_touched": self.protected_areas_touched,
            "unknowns": self.unknowns,
            "proposed_risk_level": self.proposed_risk_level,
            "risk_reasons": self.risk_reasons,
            "evidence": self.evidence,
        }


def _words(text: str) -> set:
    return {w.strip(".,:;!?()[]'\"").lower() for w in (text or "").split()}


def analyze_impact(requirement: str, grounding, environment=None) -> ImpactAnalysis:
    """Build an ImpactAnalysis from the requirement + grounding chunks (path/line
    evidence). ``environment`` (optional) contributes freshness unknowns.
    ``grounding`` is a list of GroundingChunk (or objects exposing ``rel_path``/``cite``)."""
    paths = []
    evidence = []
    for c in grounding or []:
        rel = getattr(c, "rel_path", "") or (c.get("rel_path", "") if isinstance(c, dict) else "")
        if rel:
            # Grounding paths carry the target_repo/ prefix (the RAG label space); strip it
            # so area/protected/check matching sees repo-relative paths (backend/…, frontend/…).
            paths.append(rel[len("target_repo/"):] if rel.startswith("target_repo/") else rel)
        cite = getattr(c, "cite", None)
        evidence.append(cite() if callable(cite) else rel)

    ia = ImpactAnalysis(evidence=sorted(set(e for e in evidence if e)))
    words = _words(requirement)

    # 1) affected areas from grounded paths
    areas: List[str] = []
    for rel in paths:
        for prefix, label in _AREA_RULES:
            if rel.startswith(prefix) and label not in areas:
                areas.append(label)
    ia.likely_affected_areas = areas

    touches_backend = any(p.startswith("backend/") for p in paths)
    touches_frontend = any(p.startswith("frontend/") for p in paths)

    # 2) extension points (from environment.md §6, chosen by touched area)
    if touches_backend:
        ia.existing_extension_points.append(
            "backend: add service + repository method + controller + register one route")
    if touches_frontend:
        ia.existing_extension_points.append(
            "frontend: add a feature that composes shared primitives via ApiService")

    # 3) protected areas / schema / security / contracts
    ia.protected_areas_touched = sorted({pr for p in paths for pr in _PROTECTED if p.startswith(pr)})

    schema_hit = any("migration" in a or "database" in a for a in areas) or bool(words & _SCHEMA_WORDS)
    if schema_hit:
        ia.data_or_schema_impact.append("database schema/migration may be involved (verify against code)")

    security_hit = bool(words & _SECURITY_WORDS) or any(
        p.startswith(("backend/src/aws",)) for p in paths)
    if security_hit:
        ia.security_or_privacy_impact.append(
            "requirement or touched area implicates auth/payment/privacy — review authorization + sensitive data")

    contract_hit = (
        any("routes" in a or "core services" in a for a in areas)
        or bool(words & _CONTRACT_WORDS)
    )
    if contract_hit:
        ia.public_contracts_at_risk.append("public HTTP route / ApiService contract may change — keep backward compatible")

    # 4) required checks from touched areas (feeds §22.4 gate)
    if touches_backend:
        ia.required_checks += ["backend: tsc --noEmit", "backend: jest"]
    if touches_frontend:
        ia.required_checks += ["frontend: tsc --noEmit"]
    if schema_hit:
        ia.required_checks.append("db: migration apply + rollback evidence (human)")

    # 5) risk level + reasons
    reasons: List[str] = []
    if ia.protected_areas_touched:
        reasons.append(f"protected area(s) touched: {', '.join(ia.protected_areas_touched)} (environment.md §9)")
    if ia.security_or_privacy_impact:
        reasons.append("security/privacy-sensitive (environment.md §11)")
    if schema_hit:
        reasons.append("database schema/migration impact (environment.md §11)")
    if ia.protected_areas_touched or ia.security_or_privacy_impact or schema_hit:
        risk = "high"
    elif touches_backend or touches_frontend or contract_hit:
        risk = "medium"
        reasons.append("adds/changes an endpoint, screen, or service (environment.md §11)")
    else:
        risk = "low"
        reasons.append("no backend/frontend/contract impact detected in grounding")
    ia.proposed_risk_level = risk
    ia.risk_reasons = reasons

    # 6) unknowns
    if not paths:
        ia.unknowns.append("no code grounding retrieved — impact is under-evidenced; verify manually")
    if environment is not None:
        stale = getattr(environment, "stale", None)
        warns = getattr(environment, "warnings", None)
        if stale is None and isinstance(environment, dict):
            stale = environment.get("stale")
            warns = environment.get("warnings")
        if stale:
            ia.unknowns.append("environment.md is stale/unverified — operational facts need re-verification")
        for w in (warns or [])[:3]:
            if "human-verified" in w or "unknown" in w:
                ia.unknowns.append(w)
    return ia


def impact_prompt_block(ia: ImpactAnalysis) -> str:
    """Compact impact summary to inject into the Architect prompt so plans respond to
    the shared system map instead of inventing their own."""
    return (
        "IMPACT ANALYSIS (respond to this; do not invent a different system map):\n"
        f"- risk: {ia.proposed_risk_level} — {'; '.join(ia.risk_reasons) or 'n/a'}\n"
        f"- affected areas: {', '.join(ia.likely_affected_areas) or 'unknown'}\n"
        f"- public contracts at risk: {', '.join(ia.public_contracts_at_risk) or 'none detected'}\n"
        f"- data/schema impact: {', '.join(ia.data_or_schema_impact) or 'none detected'}\n"
        f"- security/privacy: {', '.join(ia.security_or_privacy_impact) or 'none detected'}\n"
        f"- protected areas touched: {', '.join(ia.protected_areas_touched) or 'none'}\n"
        f"- required checks: {', '.join(ia.required_checks) or 'none'}\n"
        f"- evidence: {', '.join(ia.evidence) or 'none'}\n"
    )


def write_impact_md(ia: ImpactAnalysis, out_dir: Path, requirement: str = "") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    md = out_dir / "IMPACT.md"
    lines = [
        "# IMPACT.md — change-impact analysis (pre-planning)",
        "",
        f"**Requirement:** {requirement}",
        "",
        f"**Proposed risk level:** `{ia.proposed_risk_level}`",
        "",
        "**Risk reasons:**", "",
        *[f"- {r}" for r in ia.risk_reasons or ["—"]],
        "",
        "**Likely affected areas:**", "",
        *[f"- {a}" for a in ia.likely_affected_areas or ["—"]],
        "",
        "**Existing extension points:**", "",
        *[f"- {e}" for e in ia.existing_extension_points or ["—"]],
        "",
        "**Public contracts at risk:**", "",
        *[f"- {c}" for c in ia.public_contracts_at_risk or ["none detected"]],
        "",
        "**Data / schema impact:**", "",
        *[f"- {d}" for d in ia.data_or_schema_impact or ["none detected"]],
        "",
        "**Security / privacy impact:**", "",
        *[f"- {s}" for s in ia.security_or_privacy_impact or ["none detected"]],
        "",
        "**Protected areas touched:**", "",
        *[f"- {p}" for p in ia.protected_areas_touched or ["none"]],
        "",
        "**Required checks:**", "",
        *[f"- {c}" for c in ia.required_checks or ["none"]],
        "",
        "**Unknowns:**", "",
        *[f"- {u}" for u in ia.unknowns or ["none"]],
        "",
        "**Evidence (grounding citations):**", "",
        *[f"- `{e}`" for e in ia.evidence or ["—"]],
        "",
    ]
    md.write_text("\n".join(lines), encoding="utf-8")
    return md
