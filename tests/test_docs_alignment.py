"""Public-claim honesty: version/license/URLs/clarify wiring (spec §22.6, §22.5)."""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import agent_pipeline
from agent_pipeline import config

ROOT = config.PROJECT_ROOT


def _pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^\s*version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return m.group(1) if m else ""


def test_version_is_aligned():
    assert agent_pipeline.__version__ == "1.2.0"
    assert _pyproject_version() == agent_pipeline.__version__


def test_license_file_exists_and_is_mit():
    lic = ROOT / "LICENSE"
    assert lic.exists(), "pyproject declares MIT but no LICENSE file"
    assert "MIT License" in lic.read_text(encoding="utf-8")


def test_no_placeholder_urls_in_pyproject():
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "example.com" not in text


def test_readme_langgraph_claim_is_honest():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    # must not claim it is *built on* LangGraph orchestration without a StateGraph
    assert "Built on\n**LangGraph**" not in readme
    assert "imperative staged agent pipeline" in readme


def test_clarify_is_wired_into_cli_and_api():
    from agent_pipeline import cli, api
    # CLI exposes the flag
    args = cli.build_parser().parse_args(["run", "fix it", "--clarify"])
    assert args.clarify is True
    # API honors it: a vague requirement returns clarifying questions instead of running
    res = api.run("fix it", allow_clarify=True)
    assert res.get("needs_clarification")


def test_impact_study_counts_from_executed_candidate():
    # the LOC helper reads the committed diff (executed candidate), not a re-generation
    sys.path.insert(0, str(ROOT / "eval"))
    import importlib
    impact_study = importlib.import_module("impact_study")
    loc, n = impact_study._executed_diff_stats({"changed_files": ["a", "b"]})  # no workdir
    assert loc == 0 and n == 2
    # the summary metric is named honestly (consistency, not satisfaction)
    src = (ROOT / "eval" / "impact_study.py").read_text(encoding="utf-8")
    assert "gate_pass_consistency_rate" in src
    assert "requirement-satisfaction" in src.lower()
