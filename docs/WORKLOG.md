# SS6 Work Log

A running, chronological log of the spec-upgrade work: what we did, why, how it was
verified, and what comes next. Newest entries are appended at the bottom. Each phase maps
to the review brief `superai-feature-intake-form-update-spec.md` and lands as its own
tested commit on branch `ss6/spec-upgrade` (branched from `main`).

- **Goal:** implement the Feature-Intake / ProblemPacket upgrade + mandatory safety fixes
  from the 2026-07-14 review, turning "AI generates software from a prompt" into a
  traceable, human-accountable software-delivery loop — without breaking existing behavior.
- **Ground rules:** verify each spec claim against real code before fixing; every phase
  ships tests; keep `ss6 plan/run "..."` working; commit per phase; never auto-merge.
- **Branch:** `ss6/spec-upgrade` · **Started:** 2026-07-14

---

## 2026-07-14

### Session setup
- Located the project at `/Users/adisorn/Claude/Projects/SuperAI SS6 Project`; read `README.md`,
  inspected structure and git history (last release: v1.1).
- Read the review brief `superai-feature-intake-form-update-spec.md` in full.
- **Verified the brief against the actual code** — every Section 22 defect was real, and the
  intake/environment layers genuinely did not exist. Built an 8-phase task list following the
  spec's mandated order (§24). Established a green baseline: **35 tests passing**.
- Decisions with the user: commit each phase on a branch; do the P1-adjacent phases (0–3)
  first, then reassess.

### Phase 0 — Safety baseline (spec §22) — commit `2b843e5`
- **§22.1 path traversal:** `developer._safe_dest` / `_diff_target_paths` reject absolute
  paths, `..`, prefix-confusion, escapes, and off-allowlist roots — before any fs touch, and
  for every path a diff references.
- **§22.2 repair isolation:** `vcs.reset_to_base` resets the isolated tree to baseline before
  each attempt; the gate reviews the actual git diff (`vcs.working_tree_files`), not the LLM's
  file manifest — so a stale file from an earlier attempt can't survive.
- **§22.3 honest gate:** `checks` now reports `PASS/FAIL/UNVERIFIED/NOT_REQUIRED`; a required
  check that could not run is UNVERIFIED and never becomes `gate_passed=True` (killed the
  `all([])→True` silent pass in both `checks.py` and `review.py`).
- **§22.4 check selection:** checks chosen from the actual changed paths (backend vs frontend);
  no silent `npm install` (offline by default; opt-in `SS6_ALLOW_NPM_INSTALL`).
- **Verify:** full suite **35 → 50**; end-to-end `--run-tests` gate → `tsc PASS`, `jest PASS`.

### Phase 1 — environment.md contract + loader (spec §19) — commit `4724d80`
- New `environment.md` (system map / integration contract) populated from real repo
  inspection; unverified facts marked `unknown`.
- New `agent_pipeline/environment.py`: `EnvironmentContract` + `load_environment` /
  `validate_environment`; frontmatter parse (no PyYAML), required-section validation, and
  git freshness vs the commit that last touched `target_repo`. Missing file = degraded-mode
  warning, not a crash. No secrets read/emitted.
- Recorded in `plans.json` and disclosed in `REVIEW.md`.
- **Verify:** full suite **50 → 56**; freshness computes `stale=False`, honestly flags the
  unverified map.

### Phase 2 — real code grounding + impact analysis (spec §20) — commit `e7bcbf0`
- New `grounding.py`: `GroundingChunk` (path/line/score/kind + text), built once per run,
  deduped + char-budget bounded, shared by Design & Architect; cited code blocks injected into
  both prompts; compact secret-free snapshot in `plans.json`. Mock's `<<GROUNDING>>` marker
  preserved (offline behavior unchanged).
- New `impact.py`: deterministic `ImpactAnalysis` before planning (affected areas, contracts at
  risk, schema/security impact, required checks, protected areas, risk level + reasons), cited
  to environment/context + grounding; written to `IMPACT.md`; feeds the Phase 4 risk gate.
- **Verify:** full suite **56 → 69**; confirmed real code reaches the prompt with `path:line`
  citations. (Fixed a `target_repo/` prefix bug so area/check matching works.)

### Phase 3 — ProblemPacket intake + readiness (spec §5–8, §13, §17, §18) — commit `fc575bb`
- New `intake.py`: `ProblemPacket` (+ SystemContext/ConstraintSet/EvaluationMethod/Assumption/
  OpenQuestion/IntakeReadiness) and living-packet fields (version/change_log/obsolete/reusable).
  `validate_packet`, `compute_readiness`, `questions_for_packet`, `requirement_text`,
  `load_intake` (JSON canonical + Markdown). Optional fields default to unknown/not_provided.
- `api.plan()/run()` accept `str | ProblemPacket`; packet + readiness recorded in `plans.json`;
  `ss6 plan|run --intake path.(json|md)` (raw requirement OR --intake, not both).
- `examples/`: intake template + `top_customers_intake.{json,md}`.
- **Verify:** full suite **69 → 79**; CLI `--intake` works; raw-string path preserved.

### Self-review of Phases 0–3 (user-requested) — commit `afe7968`
- **D1 (real, fixed):** `analyze_impact` matched keywords against `requirement_text()`, which
  always renders literal `security:`/`privacy:` labels → every packet flagged high-risk. Would
  have broken the Phase 4 risk gate. Now matches the packet's semantic content.
- **D4 (real, fixed):** a generated path resolving to an existing directory raised an uncaught
  `IsADirectoryError` → now a clean conflict.
- **D3 (hardening):** frontmatter parser could truncate on a body `---` rule → closing fence
  must be an exact `---` line.
- **D2 (not a bug):** a feature grounded in `migrations/*.sql` is flagged high/schema —
  conservative/fail-safe. Noted "grounded-for-context vs will-modify" as a Phase 4 refinement.
- **Verify:** full suite **79 → 82**.

### Work log created (user-requested)
- Added this `docs/WORKLOG.md` to record today's actions and keep an ongoing log for all
  subsequent work.

### Phase 4 — risk-based HITL approval (spec §21) — commit `<pending>`
- New `agent_pipeline/hitl.py`: `HumanApproval` record; approval store (`out/approvals.json`);
  `effective_risk` (combines the impact risk with the chosen plan's `files_touched` on
  protected areas — the review's "grounded-for-context vs will-modify" refinement);
  `check_execution_allowed`.
- `api.execute(require_approval, approved_by)`: a medium/high-risk change **refuses to start**
  without a matching recorded approval (bound to packet version + plan id + environment
  version; a materially changed packet or risk-escalating plan invalidates a stale approval).
  Approval is only ever an explicit human action stored in the artifact — never inferred from
  running execute. Python API defaults to `require_approval=False` so eval/benchmark callers
  are unaffected; the CLI enforces it.
- `api.approve()` + `ss6 approve --plan B --approved-by <name>`; `ss6 execute/run --approved-by`
  captures an inline approval. `REVIEW.md` gains a Risk & human-approval section.
- **Verify:** full suite **82 → 93**; CLI flow confirmed end-to-end: `execute` blocks
  (risk=high) → `ss6 approve` → `execute` proceeds.

### Phase 5 — packet/env-aware agents (spec §10.3, §18.9) — commit `<pending>`
- `evaluator.py` gains a packet-aware layer that does NOT change the deterministic winner
  selection (§10.4): `criterion_coverage` / `acceptance_fit` (map each acceptance criterion
  to plan text/files), `constraints_addressed`, `system_fit` (context.md §4 layering gate:
  controller-without-service / DB-without-repository), `enrich_plan` (adds
  acceptance_criteria_covered, constraints_addressed, evaluation_strategy,
  human_decision_points, assumptions, rollback_strategy, and a user-fit + system-fit
  `packet_fit`), and `assess_plans`. `score_plan(plan, packet=None)` accepts a packet for
  signature-compat but base scoring is unchanged.
- `api.plan` enriches every plan and records an `evaluation` summary in `plans.json` when a
  packet is used. Design/Architect/Developer already receive packet context via
  `requirement_text(packet)` (criteria, constraints, non-goals) from Phase 3.
- **Verify:** full suite **93 → 102**; raw-string path unaffected (`evaluation` is null).

### Phase 6 — evidence-complete REVIEW.md (spec §23) — commit `<pending>`
- `review._evidence_sections` renders the §23 evidence from the plan/execute context:
  feature & intent (packet id/version + user goal), selected plan + rollback + user/system
  fit, an acceptance-criteria **checklist with per-criterion evidence**, security/schema/
  public-contract impact, grounding citations (path:line), assumptions/open questions, and
  the context.md rules in force. Added a `gate_passed` clarifier ("technical gate passed —
  NOT that a human approved the merge or the user accepted") and the four explicit human
  decisions (APPROVE / REQUEST FIX / RE-PLAN / REJECT, §21.3). `api.execute` threads the
  evidence bundle into `write_review_md`.
- **Verify:** full suite (pending run); REVIEW.md inspected end-to-end — all §23 sections
  present with the criteria checklist populated.

### Next up
- Phase 7 (honest benchmark + docs/version/LICENSE/LangGraph/clarification alignment, spec
  §22.5–22.6). Then the spec §25 definition-of-done review across all phases.
