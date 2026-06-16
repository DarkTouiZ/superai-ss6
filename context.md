# System Blueprint — `context.md`

This is the single source of architectural truth for **eleven-7**, a goods/products
delivery platform (a mock in the style of a 7-Eleven delivery app). Every agent in
the pipeline (Design, Architect, Evaluator, Developer) must read this file before
acting and must not violate any **MUST** rule. Retrieval of the relevant rule for a
given task is graded in Phase 1.

## 1. Product scope

A delivery platform for convenience-store goods. It lets the business:

- browse a **product catalog** (ready-to-eat meals, All Café drinks, snacks, daily essentials),
- place **orders** fulfilled from the **nearest store/branch** (delivery or pickup),
- dispatch **couriers** and track delivery status to the customer's door,
- notify customers by **SMS** and fan out order lifecycle events on **SNS/SQS**,
- award **ALL Member** loyalty points.

The repo is a monorepo: `backend/` (Node.js API + workers), `frontend/` (Angular ops
console), `backend/db/migrations/` (MySQL schema + seed), plus `docker-compose.yml`
and `localstack/` for AWS emulation.

## 2. Tech stack (fixed)

- **Backend: Node.js + Express + TypeScript** (strict mode on).
- **Frontend: Angular 17 + TypeScript** (standalone components, strict templates).
- **Database: MySQL 8.** All money is stored in **integer minor units (satang)**.
- **Messaging: AWS SNS / SQS / SMS via aws-sdk v3**, pointed at **LocalStack** locally
  (or an in-process fake when `AWS_FAKE_MODE=true`). No other cloud SDKs.
- Config is read from the environment in exactly one module per app
  (`backend/src/config/index.ts`, `frontend/src/environments/`). No scattered `process.env`.

## 3. Component reuse rules (MUST)

- The frontend **MUST** reuse the canonical Angular primitives in
  `frontend/src/app/shared/components/` before creating new ones. The canonical
  primitives are `Card`, `Badge`, `MetricTile`, `Button`, and `Avatar`.
- A new screen **MUST** compose these primitives rather than re-implementing layout.
- Any new shared color, spacing, radius, or font size **MUST** be added to
  `frontend/src/styles/tokens.scss` and referenced by CSS variable (e.g.
  `var(--color-brand)`). **No inline hex colors or magic numbers in components.**

## 4. Architectural rules (MUST)

- Business logic **MUST NOT** live in controllers (backend) or components (frontend).
  Put it in `backend/src/services/` (pure functions) or dedicated frontend services.
- All database access **MUST** go through `backend/src/repositories/`; controllers and
  services never write SQL inline and never open their own connections.
- All AWS access (SNS/SQS/SMS) **MUST** go through `backend/src/aws/`; nothing else
  imports the aws-sdk directly.
- The frontend **MUST** call the API only through `frontend/src/app/core/services/api.service.ts`;
  components never call `fetch` or `HttpClient` directly.
- All money is **integer satang**, formatted only at the view layer
  (`frontend` `MoneyPipe`, `backend` `src/utils/money.ts`). Never use floats for money.
- Every exported function **MUST** have an explicit return type.

## 5. Testing rules (MUST)

- Each service function **MUST** have a unit test under `__tests__/`.
- Revenue/pricing math **MUST** be covered by tests (no floating-point drift).
- A change to a canonical primitive **MUST** keep existing tests green.

## 6. Accessibility & UX (SHOULD)

- Interactive elements **SHOULD** have an `aria-label`.
- Dashboards **SHOULD** degrade gracefully with no/partial data (show an empty state,
  not a crash).

## 7. Pipeline priorities (used by the Debate phase)

When the Evaluator scores Plan A/B/C, weight the project priorities as:

| Priority | Weight |
|----------|-------:|
| Component reuse / maintainability | 0.40 |
| Adherence to these `context.md` rules | 0.30 |
| Performance | 0.20 |
| Speed of delivery | 0.10 |

These weights are the contract the Evaluator agent optimizes against.
