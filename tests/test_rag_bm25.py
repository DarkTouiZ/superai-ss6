"""Roadmap M5: the BM25 lexical retriever is a strong offline baseline.  Run: pytest -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_pipeline import config
from agent_pipeline.rag.lexical import BM25Index, tokenize
from agent_pipeline.rag.retriever import Retriever


def test_tokenizer_splits_identifiers():
    toks = tokenize("deliveryFee total_satang ApiService")
    assert {"delivery", "fee", "total", "satang", "api", "service"} <= set(toks)


def test_bm25_retriever_is_lexical_and_returns_paths(monkeypatch):
    monkeypatch.setattr(config, "RETRIEVER", "bm25")
    r = Retriever(rebuild=True)
    assert r.embedder.is_semantic is False
    assert r.report.embedder == "bm25-lexical"
    paths = r.retrieve_paths("how is the delivery fee computed from the cart total?", top_k=5)
    assert paths and len(paths) <= 5


def test_bm25_recall_beats_hashing(monkeypatch):
    """BM25 should clear a strong Recall@5/MRR bar that the hashing fallback misses."""
    monkeypatch.setattr(config, "RETRIEVER", "bm25")
    from eval.recall_at_k import evaluate
    rep = evaluate((1, 3, 5))
    assert rep["semantic"] is False
    assert rep["recall_at_k"]["5"] >= 0.8, rep["recall_at_k"]
    assert rep["mrr"] >= 0.7, rep["mrr"]


def test_oov_coverage_lowers_confidence(monkeypatch):
    """A query whose distinctive terms are absent from the repo gets low coverage."""
    idx = BM25Index.build()
    assert idx.coverage(tokenize("Kubernetes horizontal pod autoscaler")) < 0.5
    assert idx.coverage(tokenize("delivery fee pricing service repository")) >= 0.6
