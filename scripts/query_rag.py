#!/usr/bin/env python3
"""Manual query CLI for the RAG retriever.

Usage:
    python scripts/query_rag.py "how is a customer contact card rendered?"
    python scripts/query_rag.py "money formatting rules" --k 3
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_pipeline.rag.retriever import Retriever  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Query the SS6 RAG index.")
    parser.add_argument("query", help="natural-language query")
    parser.add_argument("--k", type=int, default=5, help="top-k chunks to return")
    args = parser.parse_args()

    retriever = Retriever(rebuild=True)
    hits = retriever.query(args.query, top_k=args.k)

    print(f'\nQuery: {args.query!r}\n')
    for rank, hit in enumerate(hits, 1):
        print(f"[{rank}] {hit.chunk_id}  (score={hit.score:.3f})")
        preview = hit.text.replace("\n", " ")[:120]
        print(f"     {preview}...\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
