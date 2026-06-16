#!/usr/bin/env python3
"""Week 1 entrypoint: build the RAG index over target_repo/ + context.md.

Usage:
    python scripts/init_rag.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_pipeline.rag.retriever import build_index  # noqa: E402


def main() -> int:
    print("Building SS6 RAG index ...")
    report, _store = build_index(reset=True)
    print("\nIndex built:")
    print(f"  chunks      : {report.n_chunks}")
    print(f"  files       : {report.n_files}")
    print(f"  embedder    : {report.embedder}")
    print(f"  semantic    : {report.is_semantic}")
    print(f"  store backend: {report.backend}")
    if not report.is_semantic:
        print("\n  NOTE: running on the lexical fallback embedder. Install "
              "sentence-transformers for true semantic retrieval.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
