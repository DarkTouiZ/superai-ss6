"""High-level retrieval API tying ingest → embeddings → vector store together.

``build_index`` populates the store from the target repo + context.md.
``Retriever`` answers natural-language queries with ranked code/blueprint chunks.
This is the Phase 1 ("Understand") interface the later agents will call.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

from agent_pipeline import config
from agent_pipeline.rag.embeddings import Embedder, get_embedder
from agent_pipeline.rag.ingest import Chunk, load_chunks
from agent_pipeline.rag.vector_store import Hit, get_store


@dataclass
class IndexReport:
    n_chunks: int
    n_files: int
    embedder: str
    is_semantic: bool
    backend: str


def build_index(reset: bool = True, embedder: Embedder | None = None, store=None):
    """Chunk the corpus, embed it, and load it into the vector store.

    Returns ``(IndexReport, store)``. The caller should reuse the returned store
    for querying — this matters for the in-memory fallback, whose state lives only
    on that instance (Chroma persists, so any reconnect would also work).
    """
    embedder = embedder or get_embedder()
    chunks: List[Chunk] = load_chunks()
    if not chunks:
        raise RuntimeError("No chunks produced — is target_repo/ empty?")

    store = store if store is not None else get_store(reset=reset)
    embeddings = embedder.encode([c.text for c in chunks])
    store.add(
        ids=[c.id for c in chunks],
        embeddings=embeddings,
        documents=[c.text for c in chunks],
        metadatas=[c.metadata for c in chunks],
    )
    report = IndexReport(
        n_chunks=len(chunks),
        n_files=len({c.rel_path for c in chunks}),
        embedder=embedder.name,
        is_semantic=embedder.is_semantic,
        backend=getattr(store, "backend", "unknown"),
    )
    return report, store


class Retriever:
    """Loads the configured embedder + store and serves queries.

    For the MVP the store is rebuilt in-process (small corpus). When using Chroma,
    pass ``rebuild=False`` to reuse the persisted collection across runs.
    """

    def __init__(self, rebuild: bool = True) -> None:
        self.embedder = get_embedder()
        if rebuild:
            self.report, self.store = build_index(reset=True, embedder=self.embedder)
        else:
            self.report = None
            self.store = get_store(reset=False)

    def query(self, text: str, top_k: int = config.DEFAULT_TOP_K) -> List[Hit]:
        vec = self.embedder.encode([text])[0]
        return self.store.query(vec, top_k=top_k)

    def retrieve_paths(self, text: str, top_k: int = config.DEFAULT_TOP_K) -> List[str]:
        """Ranked, de-duplicated list of file paths — the unit Recall@k grades."""
        seen: list[str] = []
        for hit in self.query(text, top_k=top_k):
            if hit.rel_path not in seen:
                seen.append(hit.rel_path)
        return seen
