"""Evaluator agent — Phase 3 ("Debate").

Mathematically scores the candidate plans (A/B/C) against the project priorities
from ``context.md`` §7 and selects the fittest. Scoring is **pure, deterministic
Python** — no LLM — so it is reproducible, free, explainable, and directly testable
(Rule of Engagement #3: we can prove which plan the Debate chose and why).

Each plan gets a 0..1 sub-score on four dimensions, derived from observable plan
features (not just its self-declared focus label):

  * reuse       — fraction of canonical primitives reused.
  * blueprint   — adherence signals: primitive reuse + services/tokens/api-client/
                  test mentions (context.md §3/§4/§5).
  * performance — performance-oriented techniques mentioned (memoize, virtualize,
                  precompute, cache, batch, pagination…), plus focus prior.
  * speed       — low implementation effort (few steps / files), plus focus prior.

weighted_total = Σ weight_d · score_d, with weights from ``config.PRIORITY_WEIGHTS``
(overridable). The highest weighted_total wins.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from agent_pipeline import config
from agent_pipeline.normalize import canonical_primitive

DIMENSIONS = ("reuse", "blueprint", "performance", "speed")

_PERF_KEYWORDS = (
    "memoiz", "virtualiz", "precompute", "cache", "lazy", "batch",
    "pagination", "index", "debounce", "throttle", "selector",
)
_BLUEPRINT_KEYWORDS = (
    "service", "token", "client", "test", "store", "primitive",
    "reuse", "context.md", "format", "type",
)
_N_CANONICAL = len(config.CANONICAL_PRIMITIVES)


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _plan_text(plan: dict) -> str:
    parts = [plan.get("summary", "")]
    parts += plan.get("steps", [])
    return " ".join(parts).lower()


def _canonical_reuse_count(plan: dict) -> int:
    stems = {canonical_primitive(p) for p in plan.get("primitives_reused", [])}
    return len(stems & config.CANONICAL_PRIMITIVES)


def score_plan(plan: dict) -> Dict[str, float]:
    """Return the four 0..1 sub-scores for a single plan."""
    focus = plan.get("priority_focus", "")
    text = _plan_text(plan)

    n_reuse = _canonical_reuse_count(plan)
    reuse = _clamp(n_reuse / _N_CANONICAL)

    bp_hits = sum(1 for kw in _BLUEPRINT_KEYWORDS if kw in text)
    blueprint = _clamp(0.5 * (n_reuse / _N_CANONICAL) + 0.5 * min(1.0, bp_hits / 4.0))

    perf_hits = sum(1 for kw in _PERF_KEYWORDS if kw in text)
    performance = _clamp(0.5 * (focus == "performance") + 0.5 * min(1.0, perf_hits / 2.0))

    effort = len(plan.get("steps", [])) + len(plan.get("files_touched", []))
    # fewer steps/files => faster to ship. Map effort∈[2..10] to ~[1..0].
    effort_score = _clamp(1.0 - (effort - 2) / 8.0)
    speed = _clamp(0.5 * (focus == "speed") + 0.5 * effort_score)

    return {"reuse": reuse, "blueprint": blueprint,
            "performance": performance, "speed": speed}


@dataclass
class PlanScore:
    plan_id: str
    focus: str
    subscores: Dict[str, float]
    weighted_total: float


@dataclass
class DebateResult:
    weights: Dict[str, float]
    ranking: List[PlanScore]  # sorted best-first
    winner_id: str
    winner_focus: str
    rationale: str
    margin: float  # winner_total - runner_up_total


class EvaluatorAgent:
    def __init__(self, weights: Optional[Dict[str, float]] = None) -> None:
        self.weights = dict(weights or config.PRIORITY_WEIGHTS)
        total = sum(self.weights.values())
        if total <= 0:
            raise ValueError("priority weights must sum to a positive number")
        # normalize so weights always sum to 1 (robust to custom profiles)
        self.weights = {k: v / total for k, v in self.weights.items()}

    def _weighted(self, sub: Dict[str, float]) -> float:
        return sum(self.weights.get(d, 0.0) * sub.get(d, 0.0) for d in DIMENSIONS)

    def evaluate(self, plans: List[dict]) -> DebateResult:
        scored = [
            PlanScore(
                plan_id=p.get("id", "?"),
                focus=p.get("priority_focus", ""),
                subscores=score_plan(p),
                weighted_total=round(self._weighted(score_plan(p)), 4),
            )
            for p in plans
        ]
        ranking = sorted(scored, key=lambda s: s.weighted_total, reverse=True)
        winner = ranking[0]
        margin = round(winner.weighted_total - (ranking[1].weighted_total if len(ranking) > 1 else 0.0), 4)

        top_dim = max(self.weights, key=self.weights.get)
        rationale = (
            f"Plan {winner.plan_id} ('{winner.focus}') wins with weighted score "
            f"{winner.weighted_total} (margin {margin}). Under the active priorities "
            f"the dominant weight is '{top_dim}' ({self.weights[top_dim]:.2f}); "
            f"Plan {winner.plan_id} scores {winner.subscores[top_dim]:.2f} there."
        )
        return DebateResult(
            weights=self.weights,
            ranking=ranking,
            winner_id=winner.plan_id,
            winner_focus=winner.focus,
            rationale=rationale,
            margin=margin,
        )


def result_to_dict(res: DebateResult) -> dict:
    return {
        "weights": res.weights,
        "winner_id": res.winner_id,
        "winner_focus": res.winner_focus,
        "margin": res.margin,
        "rationale": res.rationale,
        "ranking": [
            {"plan_id": s.plan_id, "focus": s.focus,
             "subscores": {k: round(v, 4) for k, v in s.subscores.items()},
             "weighted_total": s.weighted_total}
            for s in res.ranking
        ],
    }


def write_debate_md(res: DebateResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "DEBATE.md"
    w = res.weights
    lines = [
        "# DEBATE.md — Evaluator scoring",
        "",
        f"**Winner: Plan {res.winner_id}** ({res.winner_focus}) — "
        f"margin {res.margin} over runner-up.",
        "",
        res.rationale,
        "",
        "## Weights (context.md §7)",
        "",
        "| reuse | blueprint | performance | speed |",
        "|------:|----------:|------------:|------:|",
        f"| {w['reuse']:.2f} | {w['blueprint']:.2f} | {w['performance']:.2f} | {w['speed']:.2f} |",
        "",
        "## Scores",
        "",
        "| Plan | focus | reuse | blueprint | performance | speed | **weighted** |",
        "|------|-------|------:|----------:|------------:|------:|-------------:|",
    ]
    for s in res.ranking:
        sb = s.subscores
        marker = " ⬅ winner" if s.plan_id == res.winner_id else ""
        lines.append(
            f"| {s.plan_id}{marker} | {s.focus} | {sb['reuse']:.2f} | {sb['blueprint']:.2f} | "
            f"{sb['performance']:.2f} | {sb['speed']:.2f} | **{s.weighted_total:.3f}** |"
        )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path
