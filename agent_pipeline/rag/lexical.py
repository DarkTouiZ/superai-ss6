"""Lexical BM25 retriever — a strong, dependency-free offline baseline (roadmap M5).

The previous offline fallback (a hashed bag-of-tokens projected to a fixed-width
vector, scored by cosine) loses almost all signal: hash collisions and the lack of
IDF weighting make it little better than chance on this corpus. BM25 is the standard
lexical ranking function (the same family Elasticsearch/Lucene use): it weights rare
terms via IDF and saturates term frequency, so it is a *real* baseline we can measure
— not just a plumbing check — while still needing no model download or GPU.

When ``sentence-transformers`` IS installed, the semantic encoder is still used; BM25
only replaces the weak hashing fallback. Identifier-aware tokenization splits
camelCase / snake_case so a query like "delivery fee" matches ``deliveryFee`` /
``delivery_fee`` in the code.
"""
from __future__ import annotations

import math
import os
import re
from collections import Counter
from typing import List

from agent_pipeline import config
from agent_pipeline.rag.ingest import Chunk, load_chunks
from agent_pipeline.rag.vector_store import Hit

_WORD = re.compile(r"[A-Za-z0-9]+")
# split an identifier into sub-words: deliveryFee -> [delivery, fee]; ALL_CAPS too.
_SUBWORD = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+")

# Saturation scale mapping a raw BM25 score into a pseudo-similarity in [0,1): a
# match's top score is high (>min_score) while an answer-absent query stays low, so
# the eval's false-positive gate (score >= RETRIEVAL_MIN_SCORE) keeps working.
BM25_SCALE = float(os.getenv("SS6_BM25_SCALE", "12.0"))


def tokenize(text: str) -> List[str]:
    toks: List[str] = []
    for w in _WORD.findall(text):
        parts = _SUBWORD.findall(w) or [w]
        for p in parts:
            p = p.lower()
            if len(p) >= 2:
                toks.append(p)
    return toks


class BM25Index:
    """In-memory BM25 over the chunk corpus. Mirrors the store's query() shape."""

    is_semantic = False
    name = "bm25-lexical"

    def __init__(self, chunks: List[Chunk], k1: float = 1.5, b: float = 0.75) -> None:
        self.chunks = chunks
        self.k1, self.b = k1, b
        self._tf = [Counter(tokenize(c.text)) for c in chunks]
        self._len = [sum(tf.values()) for tf in self._tf]
        n_docs = len(chunks)
        self.avgdl = (sum(self._len) / n_docs) if n_docs else 0.0
        df: Counter = Counter()
        for tf in self._tf:
            df.update(tf.keys())
        # BM25 IDF (Robertson/Sparck-Jones), floored at 0 so common terms can't go negative.
        self.idf = {
            t: max(0.0, math.log(1 + (n_docs - n + 0.5) / (n + 0.5)))
            for t, n in df.items()
        }
        self.vocab = set(df.keys())

    def coverage(self, q_tokens: List[str]) -> float:
        """Fraction of the query's *content* terms (len>=4) that exist anywhere in the
        corpus. A query whose distinctive words are out-of-vocabulary (e.g. 'GraphQL',
        'Kubernetes', 'Redis') gets low coverage — an honest confidence signal that the
        repo probably can't answer it, without needing a semantic model. Query-level, so
        it scales all candidates equally and never changes the ranking (only confidence)."""
        content = [t for t in q_tokens if len(t) >= 4]
        if not content:
            return 1.0
        return sum(1 for t in content if t in self.vocab) / len(content)

    def _raw_score(self, q_tokens: List[str], i: int) -> float:
        tf, dl = self._tf[i], self._len[i]
        denom_dl = self.b * (dl / self.avgdl if self.avgdl else 1.0)
        s = 0.0
        for t in q_tokens:
            f = tf.get(t, 0)
            if not f:
                continue
            s += self.idf.get(t, 0.0) * (f * (self.k1 + 1)) / (f + self.k1 * (1 - self.b + denom_dl))
        return s

    def query(self, text: str, top_k: int = config.DEFAULT_TOP_K) -> List[Hit]:
        q = tokenize(text)
        cov = self.coverage(q)  # query-level confidence multiplier (ranking-invariant)
        scored = [(i, self._raw_score(q, i)) for i in range(len(self.chunks))]
        scored.sort(key=lambda t: -t[1])
        hits: List[Hit] = []
        for i, raw in scored[:top_k]:
            c = self.chunks[i]
            sim = (raw / (raw + BM25_SCALE)) * cov  # saturating map × OOV coverage
            hits.append(Hit(c.id, c.rel_path, c.text, round(sim, 4), c.metadata))
        return hits

    @classmethod
    def build(cls) -> "BM25Index":
        chunks = load_chunks()
        if not chunks:
            raise RuntimeError("No chunks produced — is target_repo/ empty?")
        return cls(chunks)
