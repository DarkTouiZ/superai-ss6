# Feature Intake

## 1. Feature title

Top Customers by Spend analytics endpoint

## 2. User requirement

As a store manager I want to see the top customers ranked by total spend so I can prioritise loyalty outreach.

## 3. User goal / pain

Managers currently export orders to a spreadsheet and pivot by customer manually before each monthly review.

## 4. Desired outcome

A dashboard endpoint returns the top N customers by total spend, ready for the analytics screen to render.

## 5. Acceptance criteria

- GET /api/v1/dashboard/top-customers returns customers ordered by total spend (desc) with a configurable limit.
- Spend totals are computed from real order data and expressed in integer satang (no floats).
- Existing dashboard and order APIs still pass their tests (no regression).

## 6. Current behavior

Order data is visible per-order but there is no aggregated top-customers view.

## 7. Existing system context

- Repo/module: backend/src/services, backend/src/repositories, backend/src/controllers
- Related page/API: GET /api/v1/dashboard/revenue
- Related database/schema: orders, customers
- Related files: backend/src/controllers/dashboardController.ts

## 8. Software engineer requirements

- DB access stays in a repository; business logic in a service; controller stays thin.
- Register exactly one new route; do not alter existing route contracts.

## 9. Constraints

- Security/privacy: aggregated spend is business-sensitive; endpoint must respect existing auth
- Performance: aggregation should be a single indexed query, not per-customer N+1
- Cost: no new paid dependency

## 10. Non-goals / out of scope

- No new frontend screen in this iteration (endpoint only).
- No CSV/PDF export yet.

## 11. Trade-off preference

- safest change
- most maintainable

## 12. Evaluation method

- Unit test: service ranks customers by spend correctly, including empty data
- Integration test: GET /dashboard/top-customers returns ordered results
- Human review: manager confirms the ranking matches expectations

## 13. Human decision points

- Approve whether to add a new endpoint or extend the existing revenue endpoint.

## 14. Feedback source after release

- Real user review
- Manual QA
