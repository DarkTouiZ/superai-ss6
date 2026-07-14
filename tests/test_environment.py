"""Environment contract loading/validation + freshness (spec §19).  Run: pytest -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_pipeline import config, environment as env_mod
from agent_pipeline.environment import load_environment, validate_environment, REQUIRED_SECTIONS


def test_repo_environment_loads_and_validates():
    """The committed environment.md parses, has all required sections, and exposes a
    version + freshness signal."""
    contract = load_environment()
    assert contract.present is True
    assert contract.system == "eleven-7"
    assert contract.schema_version >= 1
    assert contract.environment_version >= 1
    assert validate_environment(contract) == [], contract.warnings


def test_missing_file_is_degraded_not_fatal(tmp_path):
    contract = load_environment(tmp_path / "does_not_exist.md")
    assert contract.present is False
    assert contract.stale is True
    assert any("not found" in w for w in contract.warnings)
    # a missing contract fails validation (so callers can surface it)
    assert validate_environment(contract)


def test_missing_section_fails_validation(tmp_path):
    md = tmp_path / "environment.md"
    md.write_text(
        "---\nschema_version: 1\nsystem: eleven-7\nenvironment_version: 1\n"
        "last_verified_source_commit: \"abc1234\"\nverified_by: unknown\n---\n\n"
        "# Environment\n\n## 1. System overview\n\nonly this section exists\n",
        encoding="utf-8",
    )
    contract = load_environment(md)
    problems = validate_environment(contract)
    assert problems, "expected missing-section problems"
    assert any("Repository map" in p for p in problems)


def test_stale_when_verified_commit_diverges(tmp_path, monkeypatch):
    md = tmp_path / "environment.md"
    body_sections = "\n".join(f"## {i+1}. {s}\n\ncontent\n" for i, s in enumerate(REQUIRED_SECTIONS))
    md.write_text(
        "---\nschema_version: 1\nsystem: eleven-7\nenvironment_version: 1\n"
        "last_verified_source_commit: \"deadbeef\"\nverified_by: Safe\n---\n\n" + body_sections,
        encoding="utf-8",
    )
    # pretend target_repo currently sits at a different commit
    monkeypatch.setattr(env_mod, "_current_source_commit", lambda: "f00dcafe" * 5)
    contract = load_environment(md)
    assert contract.stale is True
    assert any("STALE" in w for w in contract.warnings)


def test_fresh_when_verified_commit_matches(tmp_path, monkeypatch):
    md = tmp_path / "environment.md"
    body_sections = "\n".join(f"## {i+1}. {s}\n\ncontent\n" for i, s in enumerate(REQUIRED_SECTIONS))
    md.write_text(
        "---\nschema_version: 1\nsystem: eleven-7\nenvironment_version: 2\n"
        "last_verified_source_commit: \"abc1234\"\nverified_by: Safe\n---\n\n" + body_sections,
        encoding="utf-8",
    )
    monkeypatch.setattr(env_mod, "_current_source_commit", lambda: "abc1234def567890")
    contract = load_environment(md)
    assert contract.stale is False
    assert contract.verified_by == "Safe"


def test_no_secrets_leak_into_summary():
    contract = load_environment()
    blob = str(contract.summary()).lower()
    for needle in ("password", "secret", "aws_secret", "api_key", "token"):
        assert needle not in blob
