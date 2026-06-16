# eleven-7 — goods & products delivery platform (mock)

A realistic, production-shaped **mock** of a convenience-store delivery app in the
style of Thailand's 7-Eleven delivery service — renamed **eleven-7**. Customers
browse store items, place orders fulfilled from the **nearest branch**, pay by
PromptPay / TrueMoney wallet / card / cash, and track a courier to the door.
Everything is mock data, run locally; no real payment, AWS, or customer systems are
touched.

> This repository is also the **target codebase** for the SS6 autonomous
> software-engineering pipeline. The agents read `../context.md` (the System
> Blueprint) and must obey its MUST rules when proposing/implementing changes.

## Stack

| Layer | Tech |
|------|------|
| Frontend | **Angular 17** + TypeScript (ops console: dashboard, catalog, orders, couriers) |
| Backend | **Node.js + Express** + TypeScript REST API |
| Data | **MySQL 8** (money stored as integer satang; schema + seed in `backend/db/migrations`) |
| Messaging | **AWS SNS / SQS / SMS** via aws-sdk v3 — pointed at **LocalStack** (or in-process fake) |
| Infra | **docker-compose** (mysql + localstack + api + worker + frontend) |

## Architecture

```
Angular ops console ──HTTP──▶ Express API ──┬─▶ MySQL (orders, catalog, couriers…)
                                            ├─▶ SQS  eleven7-order-processing  ─▶ order worker
                                            │                                     └─▶ SQS dispatch ─▶ dispatch worker ─▶ courier assign
                                            └─▶ SNS  eleven7-order-events  +  SMS to customer
```

Order lifecycle: `pending → confirmed → preparing → dispatched → delivered`
(or `cancelled`). Placing an order prices the cart, writes order+items in one
transaction, decrements inventory, enqueues SQS for async fulfillment, publishes an
SNS lifecycle event, sends the customer an SMS, and awards **ALL Member** points.

## Run it (full stack)

```bash
cd target_repo
docker compose up --build
# API     → http://localhost:4000/api/v1/health
# Frontend→ http://localhost:4200
```

MySQL auto-applies `backend/db/migrations/*.sql` on first boot; LocalStack creates
the SNS topic + SQS queues via `localstack/init-aws.sh`.

## Run pieces individually (no Docker)

```bash
# Backend
cd backend && cp .env.example .env
npm install
npm run migrate        # apply schema + seed to a running MySQL
npm run dev            # API on :4000
npm run worker         # SQS consumers (separate terminal)
npm test               # unit tests (pricing, money, delivery ETA)

# Offline AWS: set AWS_FAKE_MODE=true to stub SNS/SQS/SMS in-process (no LocalStack).

# Frontend
cd frontend && npm install && npm start   # Angular on :4200
```

## Branded services

eleven-7's internal microservices each carry a product codename (mock names for a
mock app), declared in `backend/src/services/registry.ts` and listed live at
`GET /api/v1/services`:

| Codename | Domain |
|----------|--------|
| **ShelfScan** | product catalog & search |
| **PricePilot** | cart pricing, delivery fees & points accrual |
| **OrderForge** | order placement & lifecycle |
| **FleetDash** | courier assignment & delivery tracking |
| **PulseNotify** | SMS + SNS customer notifications |
| **PaySwift** | payments: authorize / capture / refund |
| **PerksEngine** | coupons & ALL Member points |
| **CareDesk** | returns & support tickets |
| **StockKeeper** | per-store stock, transfers & low-stock alerts |

## API surface (`/api/v1`)

| Method | Path | Service |
|-------|------|---------|
| GET | `/health` · `/services` | — / registry |
| GET | `/products?categoryId=` · `/products/low-stock` | ShelfScan |
| POST | `/orders` · GET `/orders?status=` · `/orders/:id` | OrderForge |
| GET | `/orders/:orderId/delivery` · `/couriers` | FleetDash |
| GET | `/dashboard/revenue` | OrderForge |
| GET | `/promotions` · POST `/promotions/validate` · GET `/customers/:id/points` | PerksEngine |
| GET | `/orders/:orderId/payments` · POST `/payments/:id/capture` · POST `/refunds` | PaySwift |
| GET | `/support/tickets` · POST `/support/tickets` · POST `/returns` | CareDesk |
| GET | `/stores/:storeId/low-stock` · POST `/inventory/transfers` | StockKeeper |

## Data model

Core: `stores, customers, addresses, couriers, categories, products, inventory,
orders, order_items, deliveries, payments, notifications`.
Expansion (migrations 003/004): `promotions, point_transactions, payment_events,
refunds, returns, support_tickets, ticket_messages, store_inventory,
stock_transfers`.

Seeded with 6 branches, 12 customers, 6 couriers, 36 products across 8 categories,
12 orders in mixed lifecycle states, 5 promotions, an ALL-points ledger, a refund,
returns, support tickets with threads, and 60 per-store inventory rows. All money is
**integer satang**; subtotals, totals, payments, point earns, and refunds reconcile
exactly (validated).

## Conventions (enforced by `../context.md`)

- Money is integer minor units; format only at the view layer (`MoneyPipe` / `utils/money.ts`).
- All DB access goes through `backend/src/repositories/`; all AWS access through `backend/src/aws/`.
- Business logic lives in `backend/src/services/`, never in controllers or components.
- Angular screens compose the canonical shared primitives (`Card, Badge, MetricTile, Button, Avatar`) and reference design tokens in `frontend/src/styles/tokens.scss` — no inline hex.
