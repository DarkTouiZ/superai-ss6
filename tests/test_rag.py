"""Smoke tests for the Week 1 RAG plumbing. Run: pytest -q"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_pipeline.rag.ingest import load_chunks
from agent_pipeline.rag.embeddings import HashingEmbedder
from agent_pipeline.rag.retriever import Retriever


def test_ingest_produces_chunks():
    chunks = load_chunks()
    assert len(chunks) > 0
    paths = {c.rel_path for c in chunks}
    assert "context.md" in paths
    # eleven-7 backend pricing service + SQL schema (new suffix) are indexed
    assert any(p.endswith("pricing.ts") for p in paths)
    assert any(p.endswith("001_schema.sql") for p in paths)
    assert all(c.text for c in chunks)


def test_hashing_embedder_is_normalized():
    emb = HashingEmbedder()
    vecs = emb.encode(["hello world", "revenue dashboard"])
    assert vecs.shape == (2, emb.dim)
    norms = (vecs ** 2).sum(axis=1) ** 0.5
    assert all(abs(nrm - 1.0) < 1e-5 for nrm in norms)


def test_retriever_finds_relevant_file():
    r = Retriever(rebuild=True)
    paths = r.retrieve_paths("format integer satang money into a baht string", top_k=5)
    assert "target_repo/backend/src/utils/money.ts" in paths
