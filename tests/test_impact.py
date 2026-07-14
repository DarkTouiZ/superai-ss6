"""Change-impact analysis before planning (spec §20.3)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_pipeline import impact as impact_mod
from agent_pipeline.grounding import GroundingChunk


def _chunk(path, s=1, e=5):
    return GroundingChunk(f"{path}#{s}", path, s, e, "code", 0.9, "code")


def test_backend_service_change_is_medium_with_backend_checks():
    ia = impact_mod.analyze_impact(
        "Add a top customers analytics endpoint",
        [_chunk("backend/src/services/analytics.ts")],
    )
    assert ia.proposed_risk_level == "medium"
    assert "backend: tsc --noEmit" in ia.required_checks
    assert "backend: jest" in ia.required_checks
    assert any("services" in a for a in ia.likely_affected_areas)


def test_migration_change_is_high_with_schema_impact():
    ia = impact_mod.analyze_impact(
        "Add a new column to store loyalty tier",
        [_chunk("backend/db/migrations/005_loyalty.sql")],
    )
    assert ia.proposed_risk_level == "high"
    assert ia.data_or_schema_impact
    assert any("migrations" in p for p in ia.protected_areas_touched)


def test_protected_aws_area_is_high():
    ia = impact_mod.analyze_impact(
        "Change SMS notification wording",
        [_chunk("backend/src/aws/sns.ts")],
    )
    assert ia.proposed_risk_level == "high"
    assert any("aws" in p for p in ia.protected_areas_touched)


def test_security_keyword_raises_risk_even_without_protected_path():
    ia = impact_mod.analyze_impact(
        "Add refund authorization to checkout payment flow",
        [_chunk("backend/src/services/orders.ts")],
    )
    assert ia.proposed_risk_level == "high"
    assert ia.security_or_privacy_impact


def test_no_grounding_flags_unknown_and_low_risk():
    ia = impact_mod.analyze_impact("Do something vague", [])
    assert ia.proposed_risk_level == "low"
    assert any("no code grounding" in u for u in ia.unknowns)


def test_public_contract_flag_from_routes_area():
    ia = impact_mod.analyze_impact(
        "Add endpoint",
        [_chunk("backend/src/routes/index.ts")],
    )
    assert ia.public_contracts_at_risk


def test_packet_constraint_labels_do_not_spuriously_flag_security():
    """D1 regression: requirement_text() always renders 'security:'/'privacy:' labels;
    a benign packet must NOT be classified as security-sensitive because of them."""
    from agent_pipeline import intake
    benign = intake.ProblemPacket("Rename label", "change dashboard title",
                                  "cosmetic", "nicer title", ["title shows new text"])
    ia = impact_mod.analyze_impact(
        intake.requirement_text(benign),
        [_chunk("frontend/src/app/features/x.ts")], packet=benign)
    assert not ia.security_or_privacy_impact
    assert ia.proposed_risk_level in ("low", "medium")


def test_packet_real_security_constraint_is_still_flagged():
    """The fix must not silence genuine security content in a packet's constraints."""
    from agent_pipeline import intake
    p = intake.ProblemPacket("Refunds", "allow refunds", "x", "y", ["refund works"])
    p.constraints.security = "must check user authorization before issuing a refund"
    ia = impact_mod.analyze_impact(
        intake.requirement_text(p),
        [_chunk("backend/src/services/orders.ts")], packet=p)
    assert ia.security_or_privacy_impact
    assert ia.proposed_risk_level == "high"


def test_impact_md_and_dict_round_trip(tmp_path):
    ia = impact_mod.analyze_impact("Add analytics endpoint",
                                   [_chunk("backend/src/services/analytics.ts")])
    d = ia.to_dict()
    assert d["proposed_risk_level"] == "medium"
    assert set(("likely_affected_areas", "required_checks", "risk_reasons", "evidence")) <= d.keys()
    md = impact_mod.write_impact_md(ia, tmp_path, requirement="Add analytics endpoint")
    text = md.read_text(encoding="utf-8")
    assert "Proposed risk level" in text and "medium" in text
