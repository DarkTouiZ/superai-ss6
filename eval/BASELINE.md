# Evaluation baselines — eleven-7 target

Reference numbers for each phase's eval harness, measured against the **eleven-7**
codebase (Node.js + Angular + MySQL + AWS SNS/SQS/SMS). Update when the corpus,
model, or eval set changes.

> Environment note: the numbers below marked _offline_ were produced with the
> deterministic **mock** LLM and the **lexical hashing fallback** retriever
> (`sentence-transformers`/`chromadb` not installed). They verify the pipeline
> **wiring and the gates end to end**. The true **semantic** Recall@k must be
> re-run on a machine with the embedding model — see Phase 1.

## Corpus

eleven-7 (with the payments/promotions/returns/inventory expansion + branded
service registry). RAG indexes **75 files → 153 chunks** (suffixes: .ts, .js,
.sql, .scss, .html, .yml, .md). Canonical primitives: the five Angular shared
components (`Card, Badge, MetricTile, Button, Avatar`). Backend services carry
branded codenames (ShelfScan, PricePilot, OrderForge, FleetDash, PulseNotify,
PaySwift, PerksEngine, CareDesk, StockKeeper) via `backend/src/services/registry.ts`.

## Phase 1 — RAG retrieval (`eval/recall_at_k.py`)

eleven-7 v1 eval set: 14 paraphrased positives over backend/frontend/SQL targets +
look-alike distractors (snsClient vs smsClient, orderRepository vs productRepository,
money.ts vs pricing.ts, Card vs MetricTile vs Badge) + 4 hard negatives
(GraphQL, biometric login, k8s HPA, Redis cache — all ABSENT).

18-query v2 eval set (paraphrased positives + 4 hard negatives: GraphQL, biometric
login, k8s HPA, Redis cache — all ABSENT from the repo).

| Date | Retriever | Recall@1 | Recall@3 | Recall@5 | MRR | FP rate |
|------|-----------|---------:|---------:|---------:|----:|--------:|
| 2026-06-18 | hashing-fallback (legacy) | 33.3% | 44.4% | 50.0% | 0.39 | 50% |
| 2026-06-18 | **BM25 + OOV coverage** (new offline default) | **77.8%** | 83.3% | 88.9% | **0.81** | **25%** |
| 2026-06-18 | sentence-transformers/all-MiniLM-L6-v2 (semantic, chromadb) | 72.2% | **88.9%** | **94.4%** | 0.80 | 75% |

**Read of the result (roadmap M5):** replacing the hashing fallback with BM25 was the
big win — it more than doubled Recall and MRR for $0 and no model. The semantic encoder
edges ahead at deeper cut-offs (Recall@3/@5) but, notably, BM25 **beats it at Recall@1
and on false-positive rate**: the small MiniLM model confidently matches absent concepts
(GraphQL/Kubernetes/Redis) by analogy, whereas the BM25 path's out-of-vocabulary
coverage signal correctly withholds confidence. Takeaway: the strongest retriever is a
**hybrid** — BM25 (with coverage gating) for precision and OOV rejection, semantic for
recall at depth. Reproduce offline with `SS6_RETRIEVER=bm25 python eval/recall_at_k.py`;
the semantic row needs `pip install -e ".[semantic]"`.

## Phase 2 — Design quality (`eval/design_quality.py`)

| Date | Provider | Completeness | UML | Test coverage | Grounding | Overall |
|------|----------|:------------:|:---:|:-------------:|:---------:|:-------:|
| 2026-06-15 | mock (offline) | PASS | PASS (typed) | PASS (6 cases, 4 api) | PASS (ratio 1.0) | **PASS** |

Grounding now matches eleven-7 Angular primitive names (`card`, `badge`, …).

## Phase 2 — Plan quality (`eval/plan_quality.py`)

| Date | Provider | Schema | Archetypes | Mean pairwise sim | Grounding | Overall |
|------|----------|:------:|:----------:|------------------:|:---------:|:-------:|
| 2026-06-15 | mock (offline) | PASS | PASS | 0.1015 (<0.60) | PASS | **PASS** |

Caveat: gates verified on the mock. Plan **content** quality needs a human
spot-check on the first live-LLM run (`SS6_LLM_PROVIDER=anthropic|gemini|ollama`).

## Phase 3 — Debate / Evaluator (`eval/debate_quality.py`)

Deterministic weighted scoring (no LLM), proven via weight-sensitivity.

| Weight profile | Expected focus | Winner | Result |
|----------------|----------------|:------:|:------:|
| default (§7) | reuse | B (reuse) | PASS |
| performance-heavy | performance | A | PASS |
| speed-heavy | speed | C | PASS |
| reuse-heavy | reuse | B | PASS |

Default run winner: **Plan B (reuse), margin 0.1738**. Identical across
mock/Ollama/Gemini/Claude — only plan *content* varies by model, not the math.

## Phase 4 — Execute / Review (`eval/execution_quality.py`)

Proves the compliance gate discriminates on the eleven-7 rules.

| Case | Expectation | Result |
|------|-------------|:------:|
| compliant Angular reference (composes Card, uses ApiService, token vars) | passes | PASS |
| inline hex color | fails (§3) | PASS |
| direct `fetch()` | fails (§4) | PASS |
| `HttpClient` used inside a component | fails (§4) | PASS |
| no primitive/service reuse | fails (§3) | PASS |
| no export | fails | PASS |

The Developer commits to an isolated git copy under `out/exec/`; Review halts for
human approval and never auto-merges. Default run: generated
`frontend/src/app/features/top-customers/top-customers.component.ts`, compliance
**PASS**, halted for review.

**Live run (2026-06-18, Ollama `qwen2.5-coder:7b`):** the real model's code **compiled
and passed jest (tsc ✅ jest ✅)** but **failed context.md compliance** (didn't reuse the
canonical primitives; modified a shared primitive). The **repair loop ran all 3 attempts**
with violations fed back; the model couldn't converge, so the **gate stayed FAIL and the
pipeline halted — non-compliant code was not passed to review** (`gate_passed=False,
repaired=False`). The Debate, on live plans, chose **Plan A (performance)** vs the mock's
Plan B (reuse). This live run also surfaced and fixed a gate bug (the "must export" rule
firing on `.html`/`.scss` assets).

## Unit tests

`pytest -q` → **34 passed** (RAG plumbing + BM25 retriever, normalization, Evaluator
scoring + invariance, Developer branch+compliance, repair loop, surgical/unified-diff
edits, security scan, clarification, tracing, debate sensitivity). Backend pure-logic verified
separately offline: **21/21** (pricing/money/ETA) + **22/22** (coupons, points,
refunds, payment-state-machine, restock/transfer, registry). DB integrity
(referential + money arithmetic) validated across all four migrations.
