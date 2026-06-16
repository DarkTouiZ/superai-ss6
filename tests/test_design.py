"""Week 2 enrichment tests: DesignAgent artifacts + design-quality gates. pytest -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_pipeline.agents.design import DesignAgent, write_design_md
from eval.design_quality import evaluate


def test_design_agent_emits_all_artifacts(tmp_path):
    d = DesignAgent().generate("Add a top customers by revenue screen")
    a = d.artifacts
    assert a["uml_mermaid"].startswith(("classDiagram", "sequenceDiagram", "flowchart", "graph"))
    assert a["api_spec"] and a["test_cases"]
    md = write_design_md(d, tmp_path)
    text = md.read_text()
    assert "```mermaid" in text and "## Test cases" in text


def test_design_eval_passes_all_gates(tmp_path):
    d = DesignAgent().generate("Add a top customers by revenue screen")
    report = evaluate(d.artifacts)
    assert report["completeness"], report["missing_fields"]
    assert report["uml_sane"]
    assert report["tests_cover"], report["test_types"]
    assert report["grounding_ok"], report["grounding_errors"]
    assert report["pass"]


def test_design_has_functional_and_nonfunctional_tests():
    d = DesignAgent().generate("Add a revenue dashboard")
    types = {tc["type"] for tc in d.artifacts["test_cases"]}
    assert "functional" in types and "non_functional" in types
