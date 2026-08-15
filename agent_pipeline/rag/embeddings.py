"""Embedding backends.

Primary: ``sentence-transformers`` (all-MiniLM-L6-v2), a standard local encoder.
Automatic retrieval probes the local cache only; an explicit ``semantic`` mode is
required before the model loader may use the network.

Fallback: a deterministic hashing embedder used ONLY when sentence-transformers
(or its model download) is unavailable, e.g. in offline CI. It lets the whole
pipeline + Recall@k harness run end-to-end so we can test plumbing. It is NOT a
real semantic model and should not be used to judge retrieval quality — the eval
report flags when it is active.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import List, Protocol

import numpy as np

from agent_pipeline import config


class Embedder(Protocol):
    name: str
    is_semantic: bool

    def encode(self, texts: List[str]) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    """Wraps a sentence-transformers model. Lazily loaded."""

    is_semantic = True

    def __init__(
        self,
        model_name: str = config.EMBED_MODEL,
        *,
        local_files_only: bool = True,
    ) -> None:
        from sentence_transformers import SentenceTransformer  # local import: optional dep

        self.name = f"sentence-transformers/{model_name}"
        self._model = SentenceTransformer(
            model_name,
            local_files_only=local_files_only,
        )

    def encode(self, texts: List[str]) -> np.ndarray:
        vecs = self._model.encode(texts, normalize_embeddings=True, convert_to_numpy=True)
        return np.asarray(vecs, dtype=np.float32)


class HashingEmbedder:
    """Deterministic offline fallback: hashed token bag → L2-normalized vector.

    A bag-of-hashed-tokens projection. Captures lexical overlap only. Good enough
    to verify the ingest→store→retrieve→eval loop without network access.
    """

    is_semantic = False
    name = "hashing-fallback"

    def __init__(self, dim: int = config.EMBED_DIM) -> None:
        self.dim = dim

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype=np.float32)
        tokens = re.findall(r"[A-Za-z0-9_]+", text.lower())
        for tok in tokens:
            h = int(hashlib.md5(tok.encode()).hexdigest(), 16)
            idx = h % self.dim
            sign = 1.0 if (h >> 8) & 1 else -1.0
            v[idx] += sign
        norm = float(np.linalg.norm(v))
        if norm > 0:
            v /= norm
        return v

    def encode(self, texts: List[str]) -> np.ndarray:
        return np.vstack([self._vec(t) for t in texts]) if texts else np.zeros((0, self.dim), np.float32)


def get_embedder(
    *,
    allow_download: bool = False,
    require_semantic: bool = False,
) -> Embedder:
    """Return the best available embedder, falling back to hashing if needed.

    The safe default is a cache-only semantic probe. Network access is possible
    only when a caller explicitly passes ``allow_download=True`` (the
    ``SS6_RETRIEVER=semantic`` contract). In strict or required-semantic mode, a
    missing model is raised instead of degrading to the lexical fallback.
    """
    try:
        return SentenceTransformerEmbedder(local_files_only=not allow_download)
    except Exception as exc:  # ImportError or model download failure
        if config.STRICT or require_semantic:
            raise RuntimeError(
                "The semantic embedder is required but unavailable "
                f"({exc.__class__.__name__}: {exc}). Install sentence-transformers "
                "and cache the model, or run explicit semantic mode with network "
                "access."
            ) from exc
        import sys
        print(f"[embeddings] sentence-transformers unavailable ({exc.__class__.__name__}); "
              f"using deterministic hashing fallback. Retrieval quality will be lexical only.",
              file=sys.stderr)
        return HashingEmbedder()
