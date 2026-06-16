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

| Date | Embedder | Store | Recall@1 | Notes |
|------|----------|-------|---------:|-------|
| 2026-06-15 | hashing-fallback (offline) | numpy | ~36% (5/14) | lexical only; non-paraphrased queries (tokens/context/avatar) hit rank 1, proving files are indexed; paraphrase queries MISS as designed |
| _pending_ | sentence-transformers/all-MiniLM-L6-v2 | chromadb | _run locally_ | **this is the real baseline** |

To get the real number: `pip install -r requirements.txt` then
`python eval/recall_at_k.py` (prints `semantic=True`). Re-tune `SS6_MIN_SCORE`
against the semantic run before trusting the false-positive figure — two hard
negatives (biometric, Redis) score ~0.31–0.40 under the **lexical** fallback and
need the semantic model + threshold to separate cleanly.

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

## Unit tests

`pytest -q` → **17 passed** (RAG plumbing, normalization, Evaluator scoring,
Developer branch+compliance, debate sensitivity). Backend pure-logic verified
separately offline: **21/21** (pricing/money/ETA) + **22/22** (coupons, points,
refunds, payment-state-machine, restock/transfer, registry). DB integrity
(referential + money arithmetic) validated across all four migrations.
