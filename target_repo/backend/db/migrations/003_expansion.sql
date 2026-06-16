-- eleven-7 — Migration 003: expansion schema
-- Adds payments lifecycle (PaySwift), promotions + ALL points (PerksEngine),
-- returns + support tickets (CareDesk), and per-store inventory + transfers
-- (StockKeeper). All money remains INTEGER satang.
USE eleven7;
SET NAMES utf8mb4;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS stock_transfers;
DROP TABLE IF EXISTS store_inventory;
DROP TABLE IF EXISTS ticket_messages;
DROP TABLE IF EXISTS support_tickets;
DROP TABLE IF EXISTS returns;
DROP TABLE IF EXISTS refunds;
DROP TABLE IF EXISTS payment_events;
DROP TABLE IF EXISTS point_transactions;
DROP TABLE IF EXISTS promotions;
SET FOREIGN_KEY_CHECKS = 1;

-- PerksEngine: promotions / coupon codes ---------------------------------------
CREATE TABLE promotions (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  code              VARCHAR(40) NOT NULL,
  kind              ENUM('percent','fixed','free_delivery') NOT NULL,
  value             INT NOT NULL DEFAULT 0,        -- percent: 0-100; fixed: satang; free_delivery: ignored
  min_subtotal_satang INT UNSIGNED NOT NULL DEFAULT 0,
  max_discount_satang INT UNSIGNED NULL,           -- cap for percent coupons
  is_active         TINYINT(1) NOT NULL DEFAULT 1,
  starts_at         TIMESTAMP NULL,
  ends_at           TIMESTAMP NULL,
  created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_promotions_code (code),
  KEY idx_promotions_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- PerksEngine: ALL Member point ledger -----------------------------------------
CREATE TABLE point_transactions (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  customer_id       BIGINT UNSIGNED NOT NULL,
  order_id          BIGINT UNSIGNED NULL,
  kind              ENUM('earn','redeem','adjust') NOT NULL,
  points            INT NOT NULL,                  -- positive earn, negative redeem
  note              VARCHAR(160) NULL,
  created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_point_tx_customer (customer_id),
  KEY idx_point_tx_order (order_id),
  CONSTRAINT fk_point_tx_customer FOREIGN KEY (customer_id)
    REFERENCES customers(id) ON DELETE CASCADE,
  CONSTRAINT fk_point_tx_order FOREIGN KEY (order_id)
    REFERENCES orders(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- PaySwift: payment lifecycle audit trail --------------------------------------
CREATE TABLE payment_events (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  payment_id        BIGINT UNSIGNED NOT NULL,
  type              ENUM('authorized','captured','refunded','failed','voided') NOT NULL,
  amount_satang     INT UNSIGNED NOT NULL,
  provider_ref      VARCHAR(80) NULL,
  created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_payment_events_payment (payment_id),
  CONSTRAINT fk_payment_events_payment FOREIGN KEY (payment_id)
    REFERENCES payments(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- PaySwift: refunds ------------------------------------------------------------
CREATE TABLE refunds (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_id          BIGINT UNSIGNED NOT NULL,
  payment_id        BIGINT UNSIGNED NOT NULL,
  amount_satang     INT UNSIGNED NOT NULL,
  reason            VARCHAR(200) NOT NULL,
  status            ENUM('requested','approved','processed','rejected') NOT NULL DEFAULT 'requested',
  created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_refunds_order (order_id),
  CONSTRAINT fk_refunds_order FOREIGN KEY (order_id)
    REFERENCES orders(id) ON DELETE CASCADE,
  CONSTRAINT fk_refunds_payment FOREIGN KEY (payment_id)
    REFERENCES payments(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- CareDesk: returns ------------------------------------------------------------
CREATE TABLE returns (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_id          BIGINT UNSIGNED NOT NULL,
  status            ENUM('requested','approved','picked_up','refunded','rejected') NOT NULL DEFAULT 'requested',
  reason            VARCHAR(200) NOT NULL,
  created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_returns_order (order_id),
  CONSTRAINT fk_returns_order FOREIGN KEY (order_id)
    REFERENCES orders(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- CareDesk: support tickets ----------------------------------------------------
CREATE TABLE support_tickets (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_id          BIGINT UNSIGNED NULL,
  customer_id       BIGINT UNSIGNED NOT NULL,
  subject           VARCHAR(200) NOT NULL,
  category          ENUM('delivery','payment','product','account','other') NOT NULL DEFAULT 'other',
  priority          ENUM('low','normal','high','urgent') NOT NULL DEFAULT 'normal',
  status            ENUM('open','pending','resolved','closed') NOT NULL DEFAULT 'open',
  assigned_user_id  BIGINT UNSIGNED NULL,
  created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_tickets_customer (customer_id),
  KEY idx_tickets_status (status),
  CONSTRAINT fk_tickets_customer FOREIGN KEY (customer_id)
    REFERENCES customers(id) ON DELETE CASCADE,
  CONSTRAINT fk_tickets_order FOREIGN KEY (order_id)
    REFERENCES orders(id) ON DELETE SET NULL,
  CONSTRAINT fk_tickets_user FOREIGN KEY (assigned_user_id)
    REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE ticket_messages (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  ticket_id         BIGINT UNSIGNED NOT NULL,
  author            ENUM('customer','agent') NOT NULL,
  body              VARCHAR(1000) NOT NULL,
  created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_ticket_messages_ticket (ticket_id),
  CONSTRAINT fk_ticket_messages_ticket FOREIGN KEY (ticket_id)
    REFERENCES support_tickets(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- StockKeeper: per-store inventory ---------------------------------------------
CREATE TABLE store_inventory (
  store_id          BIGINT UNSIGNED NOT NULL,
  product_id        BIGINT UNSIGNED NOT NULL,
  qty_on_hand       INT NOT NULL DEFAULT 0,
  reorder_level     INT NOT NULL DEFAULT 10,
  updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (store_id, product_id),
  KEY idx_store_inventory_product (product_id),
  CONSTRAINT fk_store_inventory_store FOREIGN KEY (store_id)
    REFERENCES stores(id) ON DELETE CASCADE,
  CONSTRAINT fk_store_inventory_product FOREIGN KEY (product_id)
    REFERENCES products(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- StockKeeper: stock transfers between branches --------------------------------
CREATE TABLE stock_transfers (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  from_store_id     BIGINT UNSIGNED NOT NULL,
  to_store_id       BIGINT UNSIGNED NOT NULL,
  product_id        BIGINT UNSIGNED NOT NULL,
  qty               INT NOT NULL,
  status            ENUM('requested','in_transit','received','cancelled') NOT NULL DEFAULT 'requested',
  created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_transfers_product (product_id),
  CONSTRAINT fk_transfers_from FOREIGN KEY (from_store_id)
    REFERENCES stores(id) ON DELETE CASCADE,
  CONSTRAINT fk_transfers_to FOREIGN KEY (to_store_id)
    REFERENCES stores(id) ON DELETE CASCADE,
  CONSTRAINT fk_transfers_product FOREIGN KEY (product_id)
    REFERENCES products(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
