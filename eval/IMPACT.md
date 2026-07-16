# IMPACT.md — SS6 gate-pass **consistency** benchmark (not requirement-satisfaction)

Run `2026-07-14T12:46:02+00:00` · provider `mock` (live=False) · 6 requirements.

> **What this measures:** on the deterministic mock the Developer emits a *constant* vertical-slice template regardless of the requirement string, so a green gate on every row demonstrates **consistency + a productivity proxy (lines drafted)**, NOT that each distinct requirement was correctly implemented. A requirement-satisfaction claim needs a live provider and a per-requirement oracle.

- **Gate-pass consistency:** 100.0% (compliant on every run)
- **Mean gate attempts per requirement:** 1.0 (repair loop, roadmap M2 — 0 needed a repair)
- **Lines drafted per requirement:** 64.0 (a human would otherwise write these from a blank file)
- **Files drafted per requirement:** 5.0
- **Total lines drafted:** 384
- **Mean wall-clock per requirement:** 7.76s

| Requirement | Winner | Candidate files (RAG) | Files | LOC drafted | Attempts | Gate | s |
|-------------|--------|----------------------:|------:|------------:|:-------:|:----:|--:|
| Add a Top Customers by Spend analytics endpoint | B/reuse | 4 | 5 | 64 | 1 | PASS | 11.24 |
| Add a low-stock reorder alert screen for store managers | B/reuse | 3 | 5 | 64 | 1 | PASS | 7.07 |
| Let customers redeem ALL Member points at checkout | B/reuse | 3 | 5 | 64 | 1 | PASS | 7.0 |
| Add a daily revenue-by-store report endpoint | B/reuse | 4 | 5 | 64 | 1 | PASS | 7.0 |
| Add a courier performance leaderboard | B/reuse | 4 | 5 | 64 | 1 | PASS | 7.16 |
| Add order cancellation with an automatic refund flow | B/reuse | 3 | 5 | 64 | 1 | PASS | 7.11 |

_LOC/files are counted from the exact executed candidate (committed diff), not a re-generation. Per-requirement LOC range: [64, 64]._