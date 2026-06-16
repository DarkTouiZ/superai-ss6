-- eleven-7 — Migration 004: seed data for the expansion tables.
USE eleven7;
SET NAMES utf8mb4;

SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE stock_transfers;
TRUNCATE store_inventory;
TRUNCATE ticket_messages;
TRUNCATE support_tickets;
TRUNCATE returns;
TRUNCATE refunds;
TRUNCATE payment_events;
TRUNCATE point_transactions;
TRUNCATE promotions;
SET FOREIGN_KEY_CHECKS = 1;

-- PerksEngine: promotions ------------------------------------------------------
INSERT INTO promotions (id, code, kind, value, min_subtotal_satang, max_discount_satang, is_active, starts_at, ends_at) VALUES
 (1,'WELCOME50','fixed',5000,20000,NULL,1,'2026-06-01 00:00:00','2026-12-31 23:59:59'),
 (2,'FREESHIP','free_delivery',0,10000,NULL,1,'2026-06-01 00:00:00','2026-12-31 23:59:59'),
 (3,'ALL10','percent',10,0,5000,1,'2026-06-01 00:00:00','2026-12-31 23:59:59'),
 (4,'SUMMER15','percent',15,30000,8000,1,'2026-06-01 00:00:00','2026-08-31 23:59:59'),
 (5,'EXPIRED20','percent',20,0,10000,0,'2025-01-01 00:00:00','2025-03-31 23:59:59');

-- PerksEngine: ALL Member point ledger (earn = floor(subtotal/1000)) -----------
INSERT INTO point_transactions (id, customer_id, order_id, kind, points, note) VALUES
 (1,1,1,'earn',21,'order E7-240610-0001'),
 (2,3,2,'earn',42,'order E7-240610-0002'),
 (3,5,3,'earn',27,'order E7-240611-0003'),
 (4,2,4,'earn',14,'order E7-240611-0004'),
 (5,7,5,'earn',32,'order E7-240612-0005'),
 (6,6,10,'earn',9,'order E7-240612-0010'),
 (7,11,12,'earn',21,'order E7-240612-0012'),
 (8,3,2,'redeem',-200,'redeemed 200 points at checkout'),
 (9,12,NULL,'adjust',500,'goodwill credit (CareDesk)');

-- PaySwift: payment lifecycle events -------------------------------------------
INSERT INTO payment_events (id, payment_id, type, amount_satang, provider_ref) VALUES
 (1,1,'authorized',24600,'PP-9F2A11'),
 (2,1,'captured',24600,'PP-9F2A11'),
 (3,2,'authorized',40300,'CC-7731KK'),
 (4,2,'captured',40300,'CC-7731KK'),
 (5,5,'authorized',35700,'CC-9920LM'),
 (6,9,'authorized',15400,'PP-1102ZZ'),
 (7,9,'refunded',15400,'PP-1102ZZ-RF');

-- PaySwift: refunds (order 9 was cancelled & refunded) -------------------------
INSERT INTO refunds (id, order_id, payment_id, amount_satang, reason, status) VALUES
 (1,9,9,15400,'Customer cancelled before dispatch','processed');

-- CareDesk: returns ------------------------------------------------------------
INSERT INTO returns (id, order_id, status, reason) VALUES
 (1,3,'requested','One item arrived damaged'),
 (2,4,'approved','Wrong item delivered');

-- CareDesk: support tickets ----------------------------------------------------
INSERT INTO support_tickets (id, order_id, customer_id, subject, category, priority, status, assigned_user_id) VALUES
 (1,5,7,'Where is my order? Running late','delivery','high','open',2),
 (2,8,12,'Card was charged but order still pending','payment','urgent','pending',3),
 (3,NULL,4,'Cannot update my delivery address','account','normal','open',3),
 (4,3,5,'Requesting a refund for damaged item','product','normal','resolved',3);

INSERT INTO ticket_messages (id, ticket_id, author, body) VALUES
 (1,1,'customer','My order says dispatched 40 minutes ago but nothing yet.'),
 (2,1,'agent','Hi Khun James, the rider Decha is 8 minutes away. Thanks for your patience!'),
 (3,2,'customer','PromptPay shows the charge but the app still says pending.'),
 (4,2,'agent','We see the authorization and are confirming capture now.'),
 (5,4,'customer','One bottle was broken on arrival.'),
 (6,4,'agent','Sorry about that — a refund of THB 99.00 has been approved.');

-- StockKeeper: per-store inventory (stores 1-6 x products 1-10) -----------------
INSERT INTO store_inventory (store_id, product_id, qty_on_hand, reorder_level) VALUES
 (1,1,40,15),(1,2,20,8),(1,5,30,10),(1,6,18,8),(1,9,12,6),(1,16,25,10),(1,18,50,20),(1,24,10,6),(1,31,30,12),(1,34,80,30),
 (2,1,22,15),(2,3,14,8),(2,5,16,10),(2,7,9,6),(2,13,12,6),(2,18,40,20),(2,20,18,8),(2,27,30,12),(2,32,45,15),(2,36,60,25),
 (3,1,18,15),(3,4,11,8),(3,8,7,6),(3,10,9,6),(3,14,15,8),(3,19,28,12),(3,23,8,6),(3,29,10,6),(3,33,40,15),(3,35,20,10),
 (4,1,12,15),(4,2,8,8),(4,5,10,10),(4,11,14,8),(4,17,9,6),(4,21,18,8),(4,25,7,6),(4,28,22,10),(4,31,16,12),(4,34,55,30),
 (5,1,30,15),(5,6,20,8),(5,12,16,8),(5,15,18,10),(5,22,24,12),(5,26,10,6),(5,30,0,8),(5,32,35,15),(5,33,30,15),(5,36,48,25),
 (6,1,9,15),(6,3,8,8),(6,5,12,10),(6,18,45,20),(6,19,20,12),(6,24,8,6),(6,27,16,8),(6,31,14,12),(6,34,40,30),(6,35,12,10);

-- StockKeeper: stock transfers between branches --------------------------------
INSERT INTO stock_transfers (id, from_store_id, to_store_id, product_id, qty, status) VALUES
 (1,1,6,1,20,'in_transit'),
 (2,2,3,8,10,'received'),
 (3,5,4,25,8,'requested');
