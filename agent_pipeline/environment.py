"""Load and validate the operational environment contract (spec §19).

``environment.md`` is the descriptive map of how the current system works (see the file
for the separation from the normative ``context.md``). This module loads it, validates
that the required sections and frontmatter are present, and computes a **freshness**
signal by comparing the file's ``last_verified_source_commit`` with the commit that last
touched ``target_repo``. Stale does not mean unusable — it means the prompt and review
packet must disclose that operational facts require verification against the live code.

No secrets are read or emitted: only the frontmatter and the human-authored Markdown are
surfaced, never ``.env`` contents.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from agent_pipeline import config

# Section titles the contract must contain (spec §19.2). Matched case-insensitively as
# substrings of the Markdown headings so light wording changes don't break validation.
REQUIRED_SECTIONS = [
    "System overview",
    "Repository map",
    "Runtime and data flows",
    "Service and dependency boundaries",
    "Public/shared contracts",
    "Existing extension points",
    "Build, test, and validation commands",
    "Protected areas",
    "Change-impact rules",
    "Risk classification",
    "Human-in-the-loop policy",
    "Required review evidence",
]
REQUIRED_FRONTMATTER = [
    "schema_version",
    "system",
    "environment_version",
    "last_verified_source_commit",
    "verified_by",
]


@dataclass
class EnvironmentContract:
    schema_version: int
    system: str
    environment_version: int
    last_verified_source_commit: str
    verified_by: str
    markdown: str
    stale: bool
    warnings: List[str] = field(default_factory=list)
    present: bool = True

    def summary(self) -> dict:
        """Compact, secret-free record for plans.json / REVIEW.md (spec §19.4)."""
        return {
            "present": self.present,
            "system": self.system,
            "environment_version": self.environment_version,
            "last_verified_source_commit": self.last_verified_source_commit,
            "verified_by": self.verified_by,
            "stale": self.stale,
            "warnings": list(self.warnings),
        }


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split ``--- ... ---`` YAML-ish frontmatter (simple ``key: value`` lines, no PyYAML
    dependency) from the Markdown body. Returns (frontmatter_dict, body).

    The closing fence must be a line that is exactly ``---`` so a ``---`` horizontal rule
    later in the body cannot truncate parsing (D3)."""
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        return {}, text
    fm_lines: list[str] = []
    body_start = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            body_start = i + 1
            break
        fm_lines.append(lines[i])
    if body_start is None:
        return {}, text
    body = "".join(lines[body_start:]).lstrip("\n")
    fm: dict = {}
    for line in fm_lines:
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        fm[key.strip()] = val.strip().strip('"').strip("'")
    return fm, body


def _current_source_commit() -> Optional[str]:
    """Full hash of the commit that last touched target_repo, or None if unavailable."""
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", str(config.TARGET_REPO_DIR)],
            cwd=str(config.PROJECT_ROOT), capture_output=True, text=True, timeout=15,
        )
        commit = out.stdout.strip()
        return commit or None
    except Exception:
        return None


def _int(val, default: int = 0) -> int:
    try:
        return int(str(val).strip())
    except (TypeError, ValueError):
        return default


def validate_environment(contract: "EnvironmentContract") -> List[str]:
    """Return a list of validation problems (empty means valid). Missing required
    sections or frontmatter are problems (spec §19.4)."""
    problems: List[str] = []
    if not contract.present:
        return [f"environment.md not found at {config.ENVIRONMENT_FILE}"]
    body_lower = contract.markdown.lower()
    for section in REQUIRED_SECTIONS:
        if section.lower() not in body_lower:
            problems.append(f"missing required section: '{section}'")
    if contract.schema_version <= 0:
        problems.append("frontmatter: schema_version missing or not a positive integer")
    if not contract.system or contract.system == "unknown":
        problems.append("frontmatter: 'system' missing")
    if not contract.last_verified_source_commit:
        problems.append("frontmatter: 'last_verified_source_commit' missing")
    return problems


def load_environment(path: Optional[Path] = None) -> EnvironmentContract:
    """Load the environment contract, validate it, and compute freshness.

    Missing file → a degraded-mode contract with ``present=False`` and a clear warning
    (the pipeline may continue but must disclose it). Stale (source moved past the
    verified commit) sets ``stale=True`` with a warning; it does not raise.
    """
    path = Path(path) if path is not None else config.ENVIRONMENT_FILE
    if not path.exists():
        return EnvironmentContract(
            schema_version=0, system="unknown", environment_version=0,
            last_verified_source_commit="", verified_by="unknown",
            markdown="", stale=True, present=False,
            warnings=[f"environment.md not found at {path}; operational facts are "
                      f"unverified — verify all system claims against retrieved code"],
        )

    text = path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    warnings: List[str] = []

    missing_fm = [k for k in REQUIRED_FRONTMATTER if k not in fm]
    for k in missing_fm:
        warnings.append(f"frontmatter missing '{k}'")

    verified_commit = fm.get("last_verified_source_commit", "") or ""
    current = _current_source_commit()
    if not verified_commit or verified_commit == "unknown":
        stale = True
        warnings.append("last_verified_source_commit is unknown; treat operational facts as unverified")
    elif current is None:
        stale = False
        warnings.append("could not determine current source commit (git unavailable); freshness unverified")
    else:
        stale = not current.startswith(verified_commit)
        if stale:
            warnings.append(
                f"environment.md is STALE: verified at {verified_commit} but target_repo is now "
                f"at {current[:len(verified_commit) or 7]} — re-verify the map against code"
            )

    if str(fm.get("verified_by", "")).strip() in ("", "unknown"):
        warnings.append("environment.md has not been human-verified (verified_by: unknown)")

    contract = EnvironmentContract(
        schema_version=_int(fm.get("schema_version")),
        system=fm.get("system", "unknown") or "unknown",
        environment_version=_int(fm.get("environment_version")),
        last_verified_source_commit=verified_commit,
        verified_by=fm.get("verified_by", "unknown") or "unknown",
        markdown=body,
        stale=stale,
        warnings=warnings,
        present=True,
    )
    problems = validate_environment(contract)
    contract.warnings = warnings + problems
    return contract
