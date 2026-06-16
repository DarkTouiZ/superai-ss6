"""Vector store wrapper.

Primary backend: **ChromaDB** persistent client (the stack we standardized on).
Fallback: an in-memory NumPy cosine index, used only when ``chromadb`` is not
installed, so the pipeline and eval still run. Both expose the same tiny API:
``add`` and ``query``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

import numpy as np

from agent_pipeline import config


@dataclass
class Hit:
    chunk_id: str
    rel_path: str
    text: str
    score: float          # cosine similarity in [-1, 1]; higher = closer
    metadata: dict


class _NumpyStore:
    """Minimal in-memory cosine store (fallback when Chroma is absent)."""

    backend = "numpy-memory"

    def __init__(self) -> None:
        self._ids: List[str] = []
        self._docs: List[str] = []
        self._meta: List[dict] = []
        self._mat: Optional[np.ndarray] = None

    def add(self, ids, embeddings, documents, metadatas) -> None:
        emb = np.asarray(embeddings, dtype=np.float32)
        self._ids.extend(ids)
        self._docs.extend(documents)
        self._meta.extend(metadatas)
        self._mat = emb if self._mat is None else np.vstack([self._mat, emb])

    def query(self, embedding, top_k) -> List[Hit]:
        if self._mat is None or len(self._ids) == 0:
            return []
        q = np.asarray(embedding, dtype=np.float32).reshape(-1)
        # rows are unit-norm, q is unit-norm → dot product == cosine similarity.
        # errstate guards against spurious BLAS warnings (e.g. macOS Accelerate) and
        # any zero-norm row; nan/inf are coerced to the lowest similarity.
        with np.errstate(divide="ignore", over="ignore", invalid="ignore"):
            sims = self._mat.astype(np.float64) @ q.astype(np.float64)
        sims = np.nan_to_num(sims, nan=-1.0, posinf=-1.0, neginf=-1.0)
        order = np.argsort(-sims)[:top_k]
        return [
            Hit(self._ids[i], self._meta[i].get("rel_path", ""), self._docs[i],
                float(sims[i]), self._meta[i])
            for i in order
        ]


class _ChromaStore:
    """ChromaDB-backed persistent store."""

    backend = "chromadb"

    def __init__(self, persist_dir: str, collection: str, reset: bool = False) -> None:
        import chromadb  # local import: optional dep

        self._client = chromadb.PersistentClient(path=persist_dir)
        # Reset at the collection level (not via rmtree): Chroma caches the client
        # per path in-process, so deleting files out from under it corrupts the
        # handle. Dropping + recreating the collection is the safe, idempotent reset.
        if reset:
            try:
                self._client.delete_collection(name=collection)
            except Exception:
                pass  # collection didn't exist yet
        # cosine space to match our normalized embeddings
        self._col = self._client.get_or_create_collection(
            name=collection, metadata={"hnsw:space": "cosine"}
        )

    def add(self, ids, embeddings, documents, metadatas) -> None:
        self._col.add(
            ids=ids,
            embeddings=[list(map(float, e)) for e in np.asarray(embeddings)],
            documents=documents,
            metadatas=metadatas,
        )

    def query(self, embedding, top_k) -> List[Hit]:
        res = self._col.query(
            query_embeddings=[list(map(float, np.asarray(embedding).reshape(-1)))],
            n_results=top_k,
        )
        ids = res["ids"][0]
        docs = res["documents"][0]
        metas = res["metadatas"][0]
        dists = res["distances"][0]  # cosine distance = 1 - cosine similarity
        hits = []
        for cid, doc, meta, dist in zip(ids, docs, metas, dists):
            hits.append(Hit(cid, meta.get("rel_path", ""), doc, 1.0 - float(dist), meta))
        return hits


def get_store(reset: bool = False):
    """Return a persistent Chroma store, or a NumPy fallback if Chroma is absent."""
    try:
        import chromadb  # noqa: F401

        config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        return _ChromaStore(str(config.CHROMA_DIR), config.COLLECTION_NAME, reset=reset)
    except Exception as exc:
        if config.STRICT:
            raise RuntimeError(
                "SS6_STRICT is set but chromadb is unavailable "
                f"({exc.__class__.__name__}: {exc}). Install chromadb or unset SS6_STRICT."
            ) from exc
        import sys
        print(f"[vector_store] chromadb unavailable ({exc.__class__.__name__}); "
              f"using in-memory NumPy store (not persisted).", file=sys.stderr)
        return _NumpyStore()
