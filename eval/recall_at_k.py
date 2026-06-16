#!/usr/bin/env python3
"""Recall@k evaluation for the Phase 1 ("Understand") RAG retriever.

This is the metric that proves the retrieval node works. For each labeled query we
ask the retriever for its top-k file paths and check whether the relevant file(s)
appear.

Metrics reported:
  * Recall@k  — fraction of positive queries whose relevant set is (at least
                partially) hit within the top-k. "Hit if ANY relevant file is in
                top-k" — standard hit-rate for code search where one good file
                answers the query.
  * MRR       — mean reciprocal rank of the first relevant file (rank quality).
  * FP rate   — over the hard-negative queries (answer absent from the repo), the
                fraction where the top hit still clears RETRIEVAL_MIN_SCORE, i.e.
                the retriever confidently returned something for an unanswerable
                query. Lower is better. Requires a store that returns scores.

Run:
    python eval/recall_at_k.py
    python eval/recall_at_k.py --k 1 3 5 --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_pipeline import config  # noqa: E402
from agent_pipeline.rag.retriever import Retriever  # noqa: E402

DATASET = Path(__file__).resolve().parent / "rag_eval_dataset.json"


def _first_relevant_rank(ranked_paths: list[str], relevant: set[str]) -> int | None:
    for i, path in enumerate(ranked_paths, 1):
        if path in relevant:
            return i
    return None


def evaluate(k_values: tuple[int, ...]) -> dict:
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    queries = data["queries"]
    negatives = data.get("negatives", [])
    max_k = max(k_values)

    retriever = Retriever(rebuild=True)
    semantic = retriever.embedder.is_semantic

    per_query = []
    recall_hits = {k: 0 for k in k_values}
    reciprocal_ranks = []

    for item in queries:
        relevant = set(item["relevant"])
        ranked = retriever.retrieve_paths(item["query"], top_k=max_k)
        rank = _first_relevant_rank(ranked, relevant)
        reciprocal_ranks.append(1.0 / rank if rank else 0.0)
        for k in k_values:
            if rank is not None and rank <= k:
                recall_hits[k] += 1
        per_query.append({
            "id": item["id"],
            "query": item["query"],
            "first_relevant_rank": rank,
            "top_paths": ranked[:max_k],
        })

    # Hard negatives: count a false positive when the top hit clears the threshold.
    fp = 0
    per_negative = []
    for item in negatives:
        hits = retriever.query(item["query"], top_k=1)
        top_score = hits[0].score if hits else float("-inf")
        is_fp = top_score >= config.RETRIEVAL_MIN_SCORE
        fp += int(is_fp)
        per_negative.append({
            "id": item["id"],
            "query": item["query"],
            "top_score": round(float(top_score), 4) if hits else None,
            "false_positive": is_fp,
        })

    n = len(queries)
    n_neg = len(negatives)
    report = {
        "embedder": retriever.embedder.name,
        "semantic": semantic,
        "min_score": config.RETRIEVAL_MIN_SCORE,
        "n_queries": n,
        "n_negatives": n_neg,
        "recall_at_k": {str(k): round(recall_hits[k] / n, 4) for k in k_values},
        "mrr": round(sum(reciprocal_ranks) / n, 4),
        "false_positive_rate": round(fp / n_neg, 4) if n_neg else None,
        "per_query": per_query,
        "per_negative": per_negative,
    }
    return report


def _print_human(report: dict) -> None:
    print("\n=== SS6 RAG — Recall@k report ===")
    print(f"embedder : {report['embedder']}  (semantic={report['semantic']})")
    print(f"queries  : {report['n_queries']} positive, {report['n_negatives']} hard-negative")
    for k, v in report["recall_at_k"].items():
        print(f"Recall@{k} : {v:.2%}")
    print(f"MRR      : {report['mrr']:.4f}")
    if report["false_positive_rate"] is not None:
        print(f"FP rate  : {report['false_positive_rate']:.2%}  "
              f"(top hit ≥ {report['min_score']} on answer-absent queries)")
    if not report["semantic"]:
        print("\nNOTE: lexical fallback embedder in use — numbers reflect plumbing, "
              "not semantic retrieval quality. Install sentence-transformers to grade.")
    print("\nPer-query first-relevant rank:")
    for q in report["per_query"]:
        rank = q["first_relevant_rank"]
        mark = "MISS" if rank is None else f"rank {rank}"
        print(f"  {q['id']:>3}  {mark:<8}  {q['query']}")
    if report["per_negative"]:
        print("\nHard negatives (want: no confident hit):")
        for q in report["per_negative"]:
            mark = "FALSE-POS" if q["false_positive"] else "ok"
            print(f"  {q['id']:>3}  {mark:<10} top_score={q['top_score']}  {q['query']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Recall@k for the SS6 retriever.")
    parser.add_argument("--k", type=int, nargs="+", default=list(config.EVAL_K_VALUES))
    parser.add_argument("--json", action="store_true", help="emit JSON only")
    args = parser.parse_args()

    report = evaluate(tuple(sorted(set(args.k))))
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
