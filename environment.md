---
schema_version: 1
system: eleven-7
environment_version: 1
last_verified_source_commit: "4d9edf2"
verified_by: "unknown"
---

# Environment and Integration Contract

> Operational map of the **current** eleven-7 system: how it is built, how data flows,
> and where a new feature normally fits. This is descriptive (how things *are*), whereas
> [`context.md`](context.md) is normative (rules every change *must* obey). When the two
> disagree, `context.md` wins for architecture rules and the live code/tests win for
> observed facts (see §10, §3 precedence). This file may go stale — treat its facts as
> claims to verify against retrieved code, not as ground truth.
>
> **This first version was auto-populated by inspecting the repository and has not yet
> been human-verified** (`verified_by: unknown`). Facts that could not be confirmed by
> inspection are recorded as `unknown` and listed in §14.

## 1. System overview

eleven-7 is a mock goods/products delivery platform used as the test bed for the SS6
pipeline. It is a three-tier app: an Angular single-page frontend, a Node.js + Express
(TypeScript) REST API, and a MySQL database, plus AWS SNS/SQS/SMS messaging emulated
locally by LocalStack. Everything runs locally via Docker Compose; no production system
exists. Product scope and the fixed stack are defined normatively in `context.md` §1–§2.

## 2. Repository map

Paths are relative to `target_repo/`. Ownership is not recorded in the repo, so `Owner`
is `unknown` pending human sign-off.

| Area | Path | Responsibility | Owner |
|---|---|---|---|
| Backend API | `backend/src` | Express REST API (TypeScript) | unknown |
| — routes | `backend/src/routes/index.ts` | HTTP route table (public surface) | unknown |
| — controllers | `backend/src/controllers` | HTTP request/response handling only | unknown |
| — services | `backend/src/services` | business logic (see `context.md` §4) | unknown |
| — repositories | `backend/src/repositories` | all DB access (see `context.md` §4) | unknown |
| — aws | `backend/src/aws` | SNS/SQS/SMS access | unknown |
| — db | `backend/src/db/pool.ts` | MySQL connection pool | unknown |
| — middleware | `backend/src/middleware` | validation, error handling | unknown |
| — workers | `backend/src/workers` | queue consumers (SQS) | unknown |
| — types/utils/config | `backend/src/{types,utils,config}` | shared types, helpers, config | unknown |
| DB migrations | `backend/db/migrations/*.sql` | schema + seed (001–004) | unknown |
| Frontend | `frontend/src/app` | Angular SPA | unknown |
| — core | `frontend/src/app/core/services` | `ApiService`, `MoneyPipe` (shared singletons) | unknown |
| — shared | `frontend/src/app/shared/components` | canonical UI primitives (see §6) | unknown |
| — features | `frontend/src/app/features` | feature screens compose primitives | unknown |
| — styles | `frontend/src/styles` | design tokens (`tokens.scss`) | unknown |
| Infra | `docker-compose.yml`, `infra/`, `localstack/` | local orchestration + AWS emulation | unknown |

## 3. Runtime and data flows

- **Read path:** Angular feature screen → `ApiService` (the only HTTP client) → Express
  route → controller → service → repository → MySQL, and back.
- **Async/messaging path:** service publishes to SNS/SQS via `backend/src/aws/*`; a
  `backend/src/workers/*` consumer processes the queue (e.g. SMS notifications).
- **Money:** amounts are integer satang end-to-end; the frontend renders via `MoneyPipe`
  (normative rule in `context.md`). Never use floats for money.

## 4. Service and dependency boundaries

Backend runtime dependencies (from `backend/package.json`): `express`, `mysql2`,
`@aws-sdk/client-sns`, `@aws-sdk/client-sqs`, `cors`, `dotenv`, `zod`. Frontend is
Angular (`ng`). Adding a new runtime dependency is a **medium-risk** change (§11) and
must be justified against maintenance/compatibility cost.

Boundary rules (enforced by `context.md` §4 and the review gate):

- Controllers do not contain business logic; services do.
- Database access lives only in `backend/src/repositories`.
- The frontend talks to the API only through `ApiService` — never `fetch`/`HttpClient`
  in a component.
- AWS access goes only through `backend/src/aws/*`.

## 5. Public/shared contracts

Public HTTP surface (from `backend/src/routes/index.ts`, verify against code before
relying on it):

```
GET  /api/v1/health
GET  /api/v1/services
GET  /api/v1/products            GET  /api/v1/products/low-stock
POST /api/v1/orders              GET  /api/v1/orders        GET /api/v1/orders/:id
GET  /api/v1/couriers            GET  /api/v1/orders/:orderId/delivery
GET  /api/v1/dashboard/revenue
GET  /api/v1/promotions          POST /api/v1/promotions/validate
GET  /api/v1/customers/:customerId/points
GET  /api/v1/orders/:orderId/payments  POST /api/v1/payments/:id/capture
POST /api/v1/refunds
GET  /api/v1/support/tickets     POST /api/v1/support/tickets   POST /api/v1/returns
GET  /api/v1/stores/:storeId/low-stock  POST /api/v1/inventory/transfers
```

Shared frontend singletons: `ApiService` and `MoneyPipe` (`frontend/src/app/core/services`).
Shared DB schema: `backend/db/migrations/*.sql`. Changing any of these is a contract change
and must preserve backward compatibility unless a breaking change is explicitly approved (§11).

## 6. Existing extension points

- **New backend endpoint:** add a service (`services/`), a repository method
  (`repositories/`), a controller (`controllers/`), and register one route in
  `routes/index.ts` (prefer a surgical anchored insert). Add a jest test under
  `services/__tests__`.
- **New frontend screen:** add a feature under `app/features` that composes the canonical
  primitives in `app/shared/components` (`card`, `metric-tile`, `button`, `avatar`,
  `badge`) and reads data via `ApiService`; style with tokens only.
- **New async job:** publish via `aws/*`, consume in `workers/*`.
- **Schema change:** add a new numbered migration under `backend/db/migrations`
  (do not edit an applied migration). This is medium/high risk (§11).

## 7. Build, test, and validation commands

Backend commands from `backend/package.json`; frontend from `frontend/package.json`.
SS6's real gate runs the backend `tsc`/`jest` (and, for frontend changes, `tsc --noEmit`)
inside an isolated copy, reusing a cached `node_modules` with no network by default.

| Change area | Required command | Required evidence |
|---|---|---|
| Backend TS | `npx tsc --noEmit -p tsconfig.json` (script: `lint`/`build`) | type-check clean |
| Backend tests | `jest --runInBand` (script: `test`) | tests pass |
| Frontend TS | `npx tsc --noEmit -p tsconfig.json` | type-check clean |
| Frontend tests | `ng test --watch=false` (script: `test`) | tests pass |
| DB migration | `node scripts/migrate.js` (script: `migrate`) + rollback note | applies cleanly; rollback described |
| Docker/infra | `docker compose config` / build | config valid; human-approved |

## 8. Environment variables and local dependencies

Configuration is read via `dotenv` (`backend/src/config`, `frontend/src/environments`).
Local dependencies: Docker (MySQL, LocalStack), Node.js, Angular CLI. **Do not record
secret values here.** Specific variable names are `unknown` in this version and should be
enumerated from `.env.example`/config on human verification (§14).

## 9. Protected areas

Changes here require explicit human approval (high risk, §11):

- `backend/db/migrations/*` (applied schema — never edit in place)
- `backend/src/db/pool.ts` and DB connection/credential handling
- `backend/src/aws/*` (messaging integration)
- `docker-compose.yml`, `infra/`, `localstack/` (infrastructure)
- `frontend/src/app/core/services/api.service.ts` (shared HTTP contract)
- Auth/permissions/payment/refund flows (`payments`, `refunds` routes)

## 10. Change-impact rules

- A change touching only `services/`+`repositories/`+`controllers/`+one route, plus a
  test, is the normal extension shape (low/medium risk).
- A change to a **public route contract**, **DB schema**, **shared frontend singleton**,
  **auth/payment**, or **infrastructure** raises risk to medium/high and pulls in the
  matching required checks and human approval.
- If retrieved code contradicts a fact in this file, treat the fact as **stale** and
  report the conflict rather than silently trusting either source.

## 11. Risk classification

| Risk | Examples in eleven-7 |
|---|---|
| Low | docs, tests, an isolated pure helper in `utils/` with no public contract |
| Medium | new endpoint/route, new feature screen, new service/repository behavior, new dependency |
| High | auth/permissions, `payments`/`refunds`, DB migration, `aws/*`, secrets, infra, any breaking public-contract change |

## 12. Human-in-the-loop policy

- Low risk: pre-execution approval optional; final human review required.
- Medium risk: pre-execution plan approval required; final review required.
- High risk: pre-execution approval with explicit risk/rollback review; final review
  required (consider two reviewers).
- **Every merge/deploy requires human approval regardless of risk.** SS6 halts before
  merge and never auto-merges. (Enforcement is added in the risk/HITL phase.)

## 13. Required review evidence

Before a human can approve, `REVIEW.md` must show: the actual changed files and diff;
which required checks ran and their PASS/FAIL/UNVERIFIED status; acceptance-criteria
evidence; and any security/schema/public-contract impact. See `context.md` §7 for the
Debate priorities used to pick a plan.

## 14. Known limitations and unknowns

- `verified_by` is `unknown`: this map has not been human-reviewed yet.
- Component/area **owners** are `unknown` (not recorded in the repo).
- Specific **environment variable names** are `unknown` (enumerate from config on review).
- The `/api/v1` prefix is inferred from the demo endpoint; confirm the exact base path
  in `backend/src/server.ts`/route registration.
- This file must be re-verified whenever `target_repo` changes past
  `last_verified_source_commit`.
