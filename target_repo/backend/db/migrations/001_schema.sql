-- eleven-7 — goods/products delivery platform
-- Migration 001: schema
--
-- Conventions (see ../../../context.md):
--   * All money is stored in INTEGER minor units (satang). Never FLOAT/DECIMAL for money.
--   * Every table has created_at / updated_at.
--   * Foreign keys are explicit and indexed.
--   * Ennumerated lifecycle states use ENUM columns.
--
-- Engine: InnoDB (transactions + FK), utf8mb4 (full Unicode incl. Thai + emoji).

CREATE DATABASE IF NOT EXISTS eleven7
  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE eleven7;
-- Ensure the loading client treats the file as UTF-8 (the mysql CLI can default to
-- latin1, which would double-encode accented text like "Café").
SET NAMES utf8mb4;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS payments;
DROP TABLE IF EXISTS deliveries;
DROP TABLE IF EXISTS order_items;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS inventory;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS categories;
DROP TABLE IF EXISTS addresses;
DROP TABLE IF EXISTS couriers;
DROP TABLE IF EXISTS stores;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS users;
SET FOREIGN_KEY_CHECKS = 1;

-- Stores (eleven-7 branches — orders are fulfilled from the nearest one) --------
CREATE TABLE stores (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  code          VARCHAR(16) NOT NULL,            -- branch code e.g. E7-00321
  name          VARCHAR(160) NOT NULL,
  district      VARCHAR(120) NOT NULL,           -- service zone, matched to address.district
  city          VARCHAR(120) NOT NULL,
  lat           DECIMAL(10,7) NULL,
  lng           DECIMAL(10,7) NULL,
  opens_at      TIME NOT NULL DEFAULT '06:00:00',
  closes_at     TIME NOT NULL DEFAULT '22:00:00',
  is_24h        TINYINT(1) NOT NULL DEFAULT 0,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_stores_code (code),
  KEY idx_stores_district (district)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Staff / back-office accounts -------------------------------------------------
CREATE TABLE users (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  email         VARCHAR(190) NOT NULL,
  full_name     VARCHAR(160) NOT NULL,
  role          ENUM('admin','dispatcher','support') NOT NULL DEFAULT 'support',
  password_hash VARCHAR(255) NOT NULL,
  is_active     TINYINT(1) NOT NULL DEFAULT 1,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_users_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Customers --------------------------------------------------------------------
CREATE TABLE customers (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  full_name     VARCHAR(160) NOT NULL,
  phone         VARCHAR(20)  NOT NULL,           -- E.164, used for SMS
  email         VARCHAR(190) NULL,
  loyalty_tier  ENUM('standard','silver','gold','platinum') NOT NULL DEFAULT 'standard',
  points_balance INT NOT NULL DEFAULT 0,          -- ALL Member points (earn & burn)
  marketing_opt_in TINYINT(1) NOT NULL DEFAULT 1,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_customers_phone (phone),
  KEY idx_customers_tier (loyalty_tier)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Delivery addresses (a customer may have several) -----------------------------
CREATE TABLE addresses (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  customer_id   BIGINT UNSIGNED NOT NULL,
  label         VARCHAR(40) NOT NULL DEFAULT 'home',
  line1         VARCHAR(255) NOT NULL,
  line2         VARCHAR(255) NULL,
  district      VARCHAR(120) NOT NULL,
  city          VARCHAR(120) NOT NULL,
  postal_code   VARCHAR(12)  NOT NULL,
  lat           DECIMAL(10,7) NULL,              -- geo for dispatch (not money)
  lng           DECIMAL(10,7) NULL,
  is_default    TINYINT(1) NOT NULL DEFAULT 0,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_addresses_customer (customer_id),
  CONSTRAINT fk_addresses_customer FOREIGN KEY (customer_id)
    REFERENCES customers(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Couriers (delivery riders) ---------------------------------------------------
CREATE TABLE couriers (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  full_name     VARCHAR(160) NOT NULL,
  phone         VARCHAR(20)  NOT NULL,
  vehicle       ENUM('motorbike','bicycle','car','van') NOT NULL DEFAULT 'motorbike',
  status        ENUM('offline','available','on_delivery','on_break') NOT NULL DEFAULT 'offline',
  zone          VARCHAR(120) NOT NULL,           -- service zone, matched to address.district
  rating        DECIMAL(3,2) NOT NULL DEFAULT 5.00,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_couriers_phone (phone),
  KEY idx_couriers_status_zone (status, zone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Product categories -----------------------------------------------------------
CREATE TABLE categories (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  slug          VARCHAR(80) NOT NULL,
  name          VARCHAR(120) NOT NULL,
  sort_order    INT NOT NULL DEFAULT 0,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_categories_slug (slug)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Products ---------------------------------------------------------------------
CREATE TABLE products (
  id            BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  category_id   BIGINT UNSIGNED NOT NULL,
  sku           VARCHAR(40) NOT NULL,
  name          VARCHAR(200) NOT NULL,
  description   VARCHAR(500) NULL,
  unit          VARCHAR(24) NOT NULL DEFAULT 'each',  -- each, pack, kg, bottle...
  price_satang  INT UNSIGNED NOT NULL,                -- minor units (THB satang)
  is_active     TINYINT(1) NOT NULL DEFAULT 1,
  created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_products_sku (sku),
  KEY idx_products_category (category_id),
  CONSTRAINT fk_products_category FOREIGN KEY (category_id)
    REFERENCES categories(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Inventory (stock on hand per product) ----------------------------------------
CREATE TABLE inventory (
  product_id      BIGINT UNSIGNED NOT NULL,
  qty_on_hand     INT NOT NULL DEFAULT 0,
  reorder_level   INT NOT NULL DEFAULT 10,
  updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (product_id),
  CONSTRAINT fk_inventory_product FOREIGN KEY (product_id)
    REFERENCES products(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Orders -----------------------------------------------------------------------
CREATE TABLE orders (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_no          VARCHAR(20) NOT NULL,         -- human ref e.g. E7-240612-0007
  customer_id       BIGINT UNSIGNED NOT NULL,
  address_id        BIGINT UNSIGNED NOT NULL,
  store_id          BIGINT UNSIGNED NOT NULL,     -- fulfilling branch
  fulfillment_type  ENUM('delivery','pickup') NOT NULL DEFAULT 'delivery',
  status            ENUM('pending','confirmed','preparing','dispatched','delivered','cancelled')
                      NOT NULL DEFAULT 'pending',
  subtotal_satang   INT UNSIGNED NOT NULL DEFAULT 0,
  delivery_fee_satang INT UNSIGNED NOT NULL DEFAULT 0,
  discount_satang   INT UNSIGNED NOT NULL DEFAULT 0,
  total_satang      INT UNSIGNED NOT NULL DEFAULT 0,
  placed_at         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_orders_order_no (order_no),
  KEY idx_orders_customer (customer_id),
  KEY idx_orders_status (status),
  KEY idx_orders_placed_at (placed_at),
  KEY idx_orders_store (store_id),
  CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id)
    REFERENCES customers(id) ON DELETE RESTRICT,
  CONSTRAINT fk_orders_address FOREIGN KEY (address_id)
    REFERENCES addresses(id) ON DELETE RESTRICT,
  CONSTRAINT fk_orders_store FOREIGN KEY (store_id)
    REFERENCES stores(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Order line items (price captured at time of order) ---------------------------
CREATE TABLE order_items (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_id          BIGINT UNSIGNED NOT NULL,
  product_id        BIGINT UNSIGNED NOT NULL,
  product_name      VARCHAR(200) NOT NULL,        -- denormalized snapshot
  qty               INT NOT NULL,
  unit_price_satang INT UNSIGNED NOT NULL,        -- captured price (minor units)
  line_total_satang INT UNSIGNED NOT NULL,        -- qty * unit_price_satang
  PRIMARY KEY (id),
  KEY idx_order_items_order (order_id),
  KEY idx_order_items_product (product_id),
  CONSTRAINT fk_order_items_order FOREIGN KEY (order_id)
    REFERENCES orders(id) ON DELETE CASCADE,
  CONSTRAINT fk_order_items_product FOREIGN KEY (product_id)
    REFERENCES products(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Deliveries (one per order once dispatched) -----------------------------------
CREATE TABLE deliveries (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_id          BIGINT UNSIGNED NOT NULL,
  courier_id        BIGINT UNSIGNED NULL,
  status            ENUM('queued','assigned','picked_up','en_route','delivered','failed')
                      NOT NULL DEFAULT 'queued',
  assigned_at       TIMESTAMP NULL,
  delivered_at      TIMESTAMP NULL,
  eta_minutes       INT NULL,
  proof_photo_url   VARCHAR(500) NULL,
  created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_deliveries_order (order_id),
  KEY idx_deliveries_courier (courier_id),
  KEY idx_deliveries_status (status),
  CONSTRAINT fk_deliveries_order FOREIGN KEY (order_id)
    REFERENCES orders(id) ON DELETE CASCADE,
  CONSTRAINT fk_deliveries_courier FOREIGN KEY (courier_id)
    REFERENCES couriers(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Payments ---------------------------------------------------------------------
CREATE TABLE payments (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  order_id          BIGINT UNSIGNED NOT NULL,
  method            ENUM('promptpay','credit_card','cash_on_delivery','wallet') NOT NULL,
  status            ENUM('pending','authorized','captured','failed','refunded') NOT NULL DEFAULT 'pending',
  amount_satang     INT UNSIGNED NOT NULL,
  provider_ref      VARCHAR(80) NULL,
  created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_payments_order (order_id),
  CONSTRAINT fk_payments_order FOREIGN KEY (order_id)
    REFERENCES orders(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Notifications outbox (record of every SNS/SMS the app emitted) ----------------
CREATE TABLE notifications (
  id                BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  customer_id       BIGINT UNSIGNED NULL,
  order_id          BIGINT UNSIGNED NULL,
  channel           ENUM('sms','sns_topic','email') NOT NULL,
  template          VARCHAR(60) NOT NULL,         -- e.g. order_confirmed, out_for_delivery
  destination       VARCHAR(190) NOT NULL,        -- phone / topic arn / email
  body              VARCHAR(640) NOT NULL,
  status            ENUM('queued','sent','failed') NOT NULL DEFAULT 'queued',
  provider_message_id VARCHAR(120) NULL,          -- SNS MessageId
  created_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_notifications_order (order_id),
  KEY idx_notifications_customer (customer_id),
  KEY idx_notifications_status (status),
  CONSTRAINT fk_notifications_customer FOREIGN KEY (customer_id)
    REFERENCES customers(id) ON DELETE SET NULL,
  CONSTRAINT fk_notifications_order FOREIGN KEY (order_id)
    REFERENCES orders(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
