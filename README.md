# SuperAI SS6 — Autonomous AI Software Engineering Pipeline

An MVP multi-agent pipeline that ingests a requirement, plans the architecture,
debates competing technical approaches, and executes the winning plan against a
localized codebase — here, **eleven-7**, a mock goods/products delivery app
(Node.js + Angular + MySQL + AWS SNS/SQS/SMS) in `target_repo/`. Built on
**LangGraph** (orchestration), **SentenceTransformers + ChromaDB** (local RAG), and
**Anthropic Claude** (agent reasoning).

> Status: **Weeks 1–4 complete — full pipeline.** Understand → Plan → Debate →
> Execute → Review all run end to end, each with its own evaluation harness.
> Everything is mocked/local and self-contained; no production systems are touched.

## The four phases

| Phase | Owner agent | Output | Eval metric |
|-------|-------------|--------|-------------|
| 1. Understand | RAG / Retriever | retrieved code + `context.md` rules | **Recall@k**, MRR — `eval/recall_at_k.py` |
| 2. Plan | Architect | `PLANS.md` (Plan A/B/C) | **schema / distinctiveness / grounding / coverage** — `eval/plan_quality.py` |
| 3. Debate | Evaluator | mathematically scored winner | **weight-sensitivity** — `eval/debate_quality.py` |
| 3b. Execute | Developer | code on an isolated git branch | _gate: Review compliance suite_ |
| 4. Review | Compliance suite + HITL | REVIEW.md + halt for approval | **gate discrimination** — `eval/execution_quality.py` |

The full pipeline is implemented: RAG retrieval; the Design + Architect agents
(design artifacts + three grounded plans); the Evaluator that scores plans against
`context.md` §7 and picks the winner; the Developer that writes the winning plan's
code on an **isolated git branch** (never the real repo); and the Review phase that
runs a context.md compliance suite and **halts for human PR approval — no
auto-merge.** Each phase ships its own evaluation harness.

## Layout

```
.
├── context.md                  # System Blueprint: architectural + design rules
├── requirements.txt
├── agent_pipeline/
│   ├── config.py               # central config (paths, model names, k)
│   ├── rag/
│   │   ├── ingest.py           # parse codebase + context.md → chunks
│   │   ├── embeddings.py       # SentenceTransformer w/ offline fallback
│   │   ├── vector_store.py     # ChromaDB persistent store wrapper
│   │   └── retriever.py        # high-level query API
│   ├── graph/state.py          # shared LangGraph pipeline state (Week 2+)
│   └── agents/                 # Architect/Evaluator/Developer (Week 2+)
├── scripts/
│   ├── init_rag.py             # Week 1 entrypoint: build the index
│   └── query_rag.py            # manual query CLI
├── eval/
│   ├── rag_eval_dataset.json   # labeled queries → relevant files
│   └── recall_at_k.py          # Recall@k / MRR harness
├── target_repo/                # eleven-7: MOCK goods-delivery app (Node/Angular/MySQL/AWS) — the test bed
└── tests/test_rag.py
```

## Quickstart

```bash
pip install -r requirements.txt           # enables real embeddings + Chroma + Claude

# Phase 1 — retrieval
python scripts/init_rag.py                 # build the index over target_repo/ (eleven-7)
python scripts/query_rag.py "how is a delivery fee worked out from the cart total?"
python eval/recall_at_k.py                 # report Recall@k and MRR

# Phases 2–3 — design artifacts, plans, and the debate (one command)
python scripts/run_plan.py                 # writes DESIGN.md, PLANS.md, DEBATE.md, plans.json
python eval/design_quality.py --design out/plans.json  # gate UML/API/tests
python eval/plan_quality.py   --plans  out/plans.json  # gate the plans
python eval/debate_quality.py --plans  out/plans.json  # prove the winner is correct

# Phase 3 alone (re-score existing plans, e.g. with different weights)
python scripts/run_debate.py

# Phases 3b–4 — implement the winning plan, test, halt for human review
python scripts/run_execute.py              # writes code on an isolated git branch + REVIEW.md
python eval/execution_quality.py           # prove the compliance gate discriminates
```

The Developer never edits `target_repo/` or your outer project: it copies the repo
into `out/exec/<branch>/repo` (override with `SS6_EXEC_DIR`), does all git there, and
stops. You review `out/REVIEW.md` and decide whether to merge.

### Free LLM for the PoC (no Anthropic bill)

The agents are provider-agnostic — pick one with `SS6_LLM_PROVIDER`:

```bash
# Option 1 — Ollama: local, free, private (nothing leaves your machine)
#   brew install ollama && ollama serve         # in one terminal
#   ollama pull qwen2.5-coder:7b                 # one-time ~4GB
SS6_LLM_PROVIDER=ollama python scripts/run_plan.py

# Option 2 — Google Gemini free tier (cloud). Key: https://aistudio.google.com/apikey
export GEMINI_API_KEY="..."
SS6_LLM_PROVIDER=gemini python scripts/run_plan.py

# Option 3 — Anthropic Claude (paid)
export ANTHROPIC_API_KEY="sk-ant-..."
SS6_LLM_PROVIDER=anthropic python scripts/run_plan.py
```

Default `SS6_LLM_PROVIDER=auto` resolves anthropic-key → gemini-key → local-ollama →
mock. With no provider configured it uses the deterministic **mock** so everything
still runs at $0 (templated, not real reasoning). `SS6_STRICT=1` makes a requested
provider fail loudly instead of falling back.

### Getting the true semantic Recall@k baseline

The first `init_rag.py` run after `pip install` downloads the
`all-MiniLM-L6-v2` model (~80 MB) once, then runs fully offline. When the real
encoder is active the eval prints `semantic=True`; the lexical fallback prints
`semantic=False`. Run the baseline on a machine with network access to the model
host:

```bash
python scripts/init_rag.py        # expect: embedder sentence-transformers/..., semantic True
python eval/recall_at_k.py        # this is your real semantic Recall@k baseline
```

If `sentence-transformers`/`chromadb` are unavailable (offline CI), the pipeline
auto-falls back to a deterministic hashing embedder + in-memory store so the eval
still runs end-to-end — for plumbing checks, not for grading model quality. Set
`SS6_CHROMA_DIR` to a writable path if the project dir is read-only.

To use **live Anthropic Claude** for the Architect (instead of the offline mock),
set `ANTHROPIC_API_KEY`; the plan eval prints `live=True` when a real model ran.

For baseline/CI runs, set `SS6_STRICT=1` so a missing `sentence-transformers`/
`chromadb` raises instead of silently degrading to the lexical fallback — this
prevents "looked fine, was actually the fallback" results.

## Design rules

The agents must obey `context.md`. Week 1 only *retrieves* those rules; later
phases enforce them. See `context.md` for the full blueprint.
