# SuperAI SS6 — Engineering Roadmap

**Vision:** A plain-English requirement becomes a *conventions-compliant, test-passing, review-ready* change on an isolated branch — with the consequential decision (which plan wins) made by auditable math and the consequential action (merge) reserved for a human.

This roadmap turns the current MVP into a tool you can trust near a real codebase. It is sequenced so that **each layer is trustworthy before the next is added** — never add agents faster than you can verify their output.

---

## 0. Where we are today (MVP — shipped)

| Capability | Status |
|---|---|
| 5-phase pipeline: Understand → Plan → Debate → Execute → Review | ✅ end-to-end |
| RAG retrieval over the codebase + blueprint | ✅ (lexical fallback in CI) |
| Architect produces 3 distinct plans (A/B/C) | ✅ |
| Deterministic, auditable Debate scorer | ✅ |
| Developer writes code on an **isolated git branch** (never the real repo) | ✅ |
| Compliance gate + **halt for human review** (no auto-merge) | ✅ |
| Per-phase evaluation harness | ✅ |
| Runs **$0 / fully offline** on a deterministic mock; provider-agnostic | ✅ |
| Real `tsc` + `jest` gate (`run_tests=True`), verified green in CI sandbox | ✅ **M1 done** |
| Repair loop on gate failure (generate → gate → feed back → regenerate) | ✅ **M2 done** |
| Security scan in the gate (secrets / dynamic eval) | ✅ **M7 slice done** |
| Edits to existing files via surgical anchored diffs | ✅ **M3 slice done** |
| Clarification step for vague requirements | ✅ **M7 slice done** |
| Per-phase tracing + evidence-based reporting | ✅ **M6/M7 slice done** |
| Benchmark records repair/attempt metrics | ✅ **M4 slice done** |
| Strong offline retriever (BM25 + OOV coverage) | ✅ **M5 done** |
| True semantic Recall@k baseline measured (MiniLM, Recall@5 94.4%) | ✅ **M5 done** |
| Unified-diff edits via git apply --3way (idempotent, conflict-aware) | ✅ **M3 full done** |
| Winner validated vs execution evidence + order invariance | ✅ **M6 slice done** |
| Live LLM generation on Ollama 7B, full gate + repair loop | ✅ **M4 done** |
| Generalize across a second real repo | ⏳ M6 (needs another codebase) |

> **Progress (v1.1):** M1 (real gate), M2 (repair loop), and the M7 security slice are
> implemented, unit-tested (20/20 green), and demonstrated offline at $0. Reproduce:
> ```bash
> # Repair loop + real gate together: fails once, repairs, passes tsc+jest
> SS6_LLM_PROVIDER=mock SS6_DEMO_REPAIR=1 \
>   python -c "from agent_pipeline import run; print(run('Add a Top Customers by Spend analytics endpoint', out_dir='./out', run_tests=True)['review']['attempt_log'])"
> ```

### Guiding invariants (never trade these away)
1. **Hard repo isolation** — all work happens in a throwaway copy.
2. **Deterministic, explainable Debate** — the winner is justified by numbers, reproducibly.
3. **Human-in-the-loop merge** — the pipeline halts; a person approves.
4. **An eval harness per phase** — every capability is measured, not asserted.

---

## Milestones

Each milestone lists **Goal · Why · Tasks · Done-when**. Effort is a rough size (S/M/L).

### M1 — Make the gate real ✅ *(highest priority · L · DONE for tsc+jest; ESLint/AST next)*
- **Status:** The gate runs real `tsc --noEmit` + `jest` in the isolated copy (`run_tests=True`), verified green in the CI sandbox. Remaining: make it the default everywhere and add ESLint + an AST pass to replace the regex pre-filter.
- **Goal:** Default gate runs real `tsc` typecheck + `jest` + ESLint inside the isolated branch copy; regex checks become a fast pre-filter only.
- **Why:** The whole product's credibility rests on "the gate is trustworthy." Regex (`_HEX`, `_FETCH`, `_RETURN_TYPE` in `review.py`) can be fooled and ignores types and scope.
- **Tasks:** containerize the toolchain so `--run-tests` is the default; add ESLint with the project ruleset; replace AST-shaped regex checks with a real TypeScript AST pass; surface every failure in `REVIEW.md` with file + line.
- **Done-when:** a deliberately non-compliant change is *failed by the type/test gate*, not just the regex, on every run.

### M2 — Add a repair loop ✅ *(highest leverage · M · DONE)*
- **Status:** Implemented in `developer.execute` + `api.execute` with a configurable retry budget (`SS6_MAX_REPAIR`, default 3). Violations from compliance and the real tsc/jest gate are fed back into the next attempt; `REVIEW.md` now shows a "Repair loop" section with per-attempt status. Unit-tested and demonstrated offline (`SS6_DEMO_REPAIR=1`): attempt 1 fails on a `fetch()` violation, attempt 2 passes.
- **Goal:** `generate → gate → feed violations back → regenerate → re-gate`, with a retry budget.
- **Why:** Today a gate failure just halts. The repair loop is what turns "drafts code" into "converges on compliant code" — the single most valuable feature not yet present.
- **Tasks:** capture structured violations from M1; build a Developer "repair" prompt that receives the failing diff + violations; cap retries (e.g. 3) and record each attempt in the review packet.
- **Done-when:** at least one class of initially-failing change is automatically driven to PASS within the retry budget, with the attempt history logged.

### M3 — Edit existing files, not just create new ones ✅ *(hardest gap · L · DONE)*
- **Status (done):** Two edit modes on existing files in the isolated copy, both idempotent across repair attempts and reporting unresolved changes as a hard "conflict" the repair loop reacts to: (1) **surgical anchored edits** (`{path, edits:[{anchor, insert_after/insert_before/replace}]}`) — route registration is now a +2-line diff to the real `routes/index.ts` with all 21 existing routes preserved; (2) **unified diffs** (`{path, diff}`) applied via `git apply --3way`, so a model-generated patch with slightly stale context still merges through the blob index. Both verified by tests; tsc+jest stay green. **Remaining (nice-to-have):** automatic conflict *resolution* (vs. reporting) on true 3-way conflicts.
- **Goal:** Developer applies diffs/patches to existing files with multi-file coherence and conflict handling.
- **Why:** Real engineering modifies existing code. New-file-only generation is the main gap between "impressive demo" and "usable tool."
- **Tasks:** switch the Developer contract from full-file output to a patch/diff format; add a safe apply step (3-way merge) inside the isolated branch; detect and report conflicts instead of overwriting.
- **Done-when:** a requirement that *modifies* an existing service/controller produces a correct, compiling diff against the current file.

### M4 — Generate with a real (free) model and measure quality ✅ *(M · DONE)*
- **Status (done — live run captured):** Ran the full pipeline on **Ollama `qwen2.5-coder:7b`** (local, free). Findings:
  - The live model produced genuinely different plans — the deterministic Debate picked **Plan A (performance)**, vs the mock's Plan B (reuse): proof the math scores real content, not a template.
  - On the full Execute→Review: the 7B's code **compiled and passed jest (tsc ✅ jest ✅)** but **failed context.md compliance** (it didn't reuse the canonical primitives and even modified a shared primitive). The **repair loop ran the full 3 attempts**, feeding violations back each time; the small model couldn't converge, so the **gate stayed FAIL and the pipeline halted — non-compliant code was NOT passed to review.** This is the safety property working against a real, imperfect model — a stronger demonstration than a clean pass.
  - Dogfooding bonus: the live run surfaced a real gate bug (the "must export" rule wrongly fired on `.html`/`.scss` assets), now **fixed** and regression-tested.
  - The impact benchmark records `attempts`/`repaired`; metrics measure convergence, not just constant mock output.
- **Goal:** Default development runs on a free local model (Ollama); add metrics that measure code quality, not just consistency.
- **Why:** The mock emits constant output (5 files / 109 LOC), so "100% pass" currently means "templated output passes a regex gate." Real generation exposes real failure modes.
- **Tasks:** wire `SS6_LLM_PROVIDER=ollama` as the dev default; extend `impact_study.py` to record compile-pass, test-pass, and a diff-quality score; report variance across runs.
- **Done-when:** the impact benchmark reports *compile + test pass rates from a live model*, with variance, not constant mock numbers.

### M5 — Prove retrieval works ✅ *(S · DONE)*
- **Status (done):** Replaced the weak hashing fallback with a real **BM25 lexical retriever** (identifier-aware tokenization + IDF) plus an **out-of-vocabulary coverage** confidence signal, AND measured the true **semantic** baseline (all-MiniLM-L6-v2 via chromadb). Three-way result on the 18-query set:

  | Retriever | Recall@1 | Recall@3 | Recall@5 | MRR | FP |
  |---|--:|--:|--:|--:|--:|
  | hashing (legacy) | 33% | 44% | 50% | 0.39 | 50% |
  | **BM25 + coverage** | **78%** | 83% | 89% | **0.81** | **25%** |
  | semantic (MiniLM) | 72% | **89%** | **94%** | 0.80 | 75% |

  Key finding: BM25 more than doubled the old numbers for $0; semantic wins at deeper cut-offs but BM25 **beats it at Recall@1 and on false positives** (its OOV coverage gate withholds confidence on absent concepts the encoder over-matches). The strongest design is a **hybrid** (BM25 for precision/OOV-rejection + semantic for recall depth) — a clear next step. Full numbers in `eval/BASELINE.md`.
- **Goal:** Pin `sentence-transformers` + `chromadb`; run and publish the real semantic Recall@k / MRR baseline.
- **Why:** Every run so far fell back to the lexical hashing embedder, so the headline retrieval number has never been measured semantically. `README` already flags this.
- **Tasks:** pin deps; run `eval/recall_at_k.py` with `semantic=True` and `SS6_STRICT=1`; commit the baseline numbers and the dataset version.
- **Done-when:** the eval prints `semantic=True` and a committed baseline exists.

### M6 — Harden the Evaluator and broaden coverage *(M)*
- **Goal:** Make the Debate scorer resistant to wording, and prove the system generalizes.
- **Why:** Scores currently come from keyword-matching the Architect's own plan prose (`_PERF_KEYWORDS`, `_BLUEPRINT_KEYWORDS`) — a plan can "win" by phrasing. And everything is validated on one mock repo with ~6 labeled requirements.
- **Tasks:** score plans against *post-execution facts* (did it actually reuse primitives, did tests pass) rather than plan text; run the pipeline against a second repo (ideally a real OSS one); expand the labeled eval set for statistical significance.
- **Done-when:** swapping plan wording does not change the winner, and a green run exists on a second repo.

### M7 — Productionize the loop *(M)*
- **Goal:** Real PR creation + CI, plus observability and a safety scan.
- **Why:** "Halt + `REVIEW.md`" is the right behavior; the next step is fitting it into a real team workflow.
- **Tasks:** open a draft PR via the platform API on PASS (the demo already does this with `gh`); add per-phase cost/latency/token tracing; add a security scan on generated code; add a clarification step for ambiguous requirements.
- **Done-when:** a passing run opens a draft PR with the review packet attached and a cost/latency trace.

---

## Suggested sequence

```
M1 (real gate) ──▶ M2 (repair loop) ──▶ M3 (edit existing files)
       │                                        │
       └────────────▶ M4 (live model + quality) ┘
M5 (semantic baseline)  ── can run in parallel, low cost
M6 (harden + generalize) ──▶ M7 (PR + CI + observability)
```

M1 and M2 together are the backbone: a real gate plus a repair loop is what makes generation *converge* instead of just *attempt*. Do those first.

---

## Appendix — if you were starting from scratch

1. **Write the blueprint first.** The encoded rules are the moat; everything downstream depends on them.
2. **Build the real gate before any generation.** If you cannot verify output, nothing else matters.
3. **Narrow the scope hard.** One repo, one class of change. Make that loop excellent before generalizing.
4. **Use a free local model from day one** — never a mock for development.
5. **Add the generate → gate → repair loop** as soon as single-shot generation works.
6. **Then** layer RAG grounding, the multi-plan debate, and PR integration — each with its own eval harness.
7. **Keep isolation and human-in-the-loop non-negotiable** the entire time.

> One line: the MVP nailed the *orchestration and safety story*; the roadmap makes the *verification and generation real*, with the **repair loop (M2)** as the highest-leverage single addition.
