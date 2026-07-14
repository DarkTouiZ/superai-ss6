"""Real code grounding: chunks carry source text + citations, bounded (spec §20.1-2)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_pipeline import grounding as g
from agent_pipeline.rag.vector_store import Hit


class FakeRetriever:
    def __init__(self, hits):
        self._hits = hits

    def query(self, text, top_k=8):
        return self._hits[:top_k]

    def retrieve_paths(self, text, top_k=8):
        seen = []
        for h in self._hits:
            if h.rel_path not in seen:
                seen.append(h.rel_path)
        return seen


def _hit(path, text, s, e, score, kind="code"):
    return Hit(f"{path}#{s}", path, text, score,
               {"rel_path": path, "kind": kind, "start_line": s, "end_line": e})


def test_grounding_carries_source_text_and_lines():
    r = FakeRetriever([_hit("backend/src/services/pricing.ts", "export function fee(){return 1;}", 1, 3, 0.9)])
    chunks = g.build_grounding(r, "how is the delivery fee computed?")
    assert chunks
    c = chunks[0]
    assert c.text and "fee" in c.text          # actual code, not just a path
    assert c.start_line == 1 and c.end_line == 3
    assert c.cite() == "backend/src/services/pricing.ts:1-3"


def test_grounding_dedupes_identical_ranges():
    h = _hit("a/b.ts", "x", 1, 5, 0.5)
    r = FakeRetriever([h, h, h])
    chunks = g.build_grounding(r, "q")
    assert len(chunks) == 1


def test_char_budget_bounds_output_but_keeps_one():
    big = "y" * 5000
    hits = [_hit(f"a/f{i}.ts", big, 1, 100, 0.9 - i * 0.1) for i in range(5)]
    r = FakeRetriever(hits)
    chunks = g.build_grounding(r, "q", char_budget=1000)
    assert 1 <= len(chunks) < 5           # budget stopped it early, but never empty


def test_candidate_files_and_snapshot_have_no_full_text():
    r = FakeRetriever([
        _hit("backend/src/services/a.ts", "secret code body", 1, 2, 0.9),
        _hit("backend/src/services/a.ts", "other", 3, 4, 0.8),   # same file, diff range
        _hit("frontend/src/app/x.ts", "zz", 1, 2, 0.7),
    ])
    chunks = g.build_grounding(r, "q")
    files = g.candidate_files(chunks)
    assert files == ["backend/src/services/a.ts", "frontend/src/app/x.ts"]  # deduped, ranked
    snap = g.snapshot(chunks)
    assert all("text" not in row for row in snap)          # compact, no source dump
    assert all({"rel_path", "start_line", "end_line", "score", "kind"} <= row.keys() for row in snap)


def test_prompt_block_cites_evidence():
    r = FakeRetriever([_hit("backend/src/services/pricing.ts", "export const fee = 1;", 10, 12, 0.9)])
    chunks = g.build_grounding(r, "q")
    block = g.to_prompt_block(chunks)
    assert "backend/src/services/pricing.ts:10-12" in block
    assert "export const fee" in block                     # the real code is present
