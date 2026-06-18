# IMPACT.md — SS6 consistency & productivity benchmark

Across **6 requirements**, run on the deterministic mock provider (zero cost, offline):

- **Gate pass-rate:** 100.0% (compliant, review-ready every time)
- **Lines drafted per requirement:** 109.0 (a human would otherwise write these from a blank file)
- **Files drafted per requirement:** 5.0
- **Total lines drafted:** 654
- **Mean wall-clock per requirement:** 1.77s

| Requirement | Winner | Candidate files (RAG) | Files | LOC drafted | Gate | s |
|-------------|--------|----------------------:|------:|------------:|:----:|--:|
| Add a Top Customers by Spend analytics endpoint | B/reuse | 6 | 5 | 109 | PASS | 3.17 |
| Add a low-stock reorder alert screen for store managers | B/reuse | 6 | 5 | 109 | PASS | 1.48 |
| Let customers redeem ALL Member points at checkout | B/reuse | 5 | 5 | 109 | PASS | 1.47 |
| Add a daily revenue-by-store report endpoint | B/reuse | 6 | 5 | 109 | PASS | 1.49 |
| Add a courier performance leaderboard | B/reuse | 6 | 5 | 109 | PASS | 1.53 |
| Add order cancellation with an automatic refund flow | A/performance | 7 | 5 | 109 | PASS | 1.46 |

_On the deterministic mock the generated code volume is constant by design; a live provider would vary it. This benchmark measures consistency, a green gate on every run, and the lines-drafted productivity proxy — reproducibly and for $0._