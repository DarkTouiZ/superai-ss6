-- eleven-7 — Migration 002: realistic mock/seed data
-- Currency: Thai Baht. All amounts in satang (1 THB = 100 satang).
USE eleven7;
SET NAMES utf8mb4;  -- correct UTF-8 load (e.g. "All Café")

SET FOREIGN_KEY_CHECKS = 0;
TRUNCATE notifications;
TRUNCATE payments;
TRUNCATE deliveries;
TRUNCATE order_items;
TRUNCATE orders;
TRUNCATE inventory;
TRUNCATE products;
TRUNCATE categories;
TRUNCATE addresses;
TRUNCATE couriers;
TRUNCATE stores;
TRUNCATE customers;
TRUNCATE users;
SET FOREIGN_KEY_CHECKS = 1;

-- Stores (eleven-7 branches across Bangkok; nearest one fulfills the order) -----
INSERT INTO stores (id, code, name, district, city, lat, lng, opens_at, closes_at, is_24h) VALUES
 (1,'E7-00110','eleven-7 Sukhumvit 31','Watthana','Bangkok',13.7385,100.5615,'00:00:00','23:59:59',1),
 (2,'E7-00204','eleven-7 Sathorn Square','Sathon','Bangkok',13.7225,100.5295,'06:00:00','22:00:00',0),
 (3,'E7-00318','eleven-7 Charoen Krung','Bang Rak','Bangkok',13.7215,100.5165,'06:00:00','23:00:00',0),
 (4,'E7-00422','eleven-7 Ratchada 18','Huai Khwang','Bangkok',13.7695,100.5745,'00:00:00','23:59:59',1),
 (5,'E7-00537','eleven-7 Phahonyothin','Chatuchak','Bangkok',13.8295,100.5605,'06:00:00','22:00:00',0),
 (6,'E7-00641','eleven-7 Ladprao 101','Bang Kapi','Bangkok',13.7775,100.6425,'06:00:00','22:00:00',0);

-- Staff -----------------------------------------------------------------------
INSERT INTO users (id, email, full_name, role, password_hash, is_active) VALUES
 (1,'ops@eleven7.app','Anchalee Wong','admin','$2b$10$mockmockmockmockmockmoO0a',1),
 (2,'dispatch@eleven7.app','Krit Suksai','dispatcher','$2b$10$mockmockmockmockmockmoO0b',1),
 (3,'support@eleven7.app','Nadia Rahman','support','$2b$10$mockmockmockmockmockmoO0c',1);

-- Customers -------------------------------------------------------------------
INSERT INTO customers (id, full_name, phone, email, loyalty_tier, points_balance, marketing_opt_in) VALUES
 (1,'Somchai Jaidee','+66811112201','somchai.j@example.com','gold',1240,1),
 (2,'Pimchanok Srisai','+66811112202','pim.srisai@example.com','silver',430,1),
 (3,'David Carter','+66811112203','d.carter@example.com','platinum',5820,1),
 (4,'Ratana Phongam','+66811112204','ratana.p@example.com','standard',75,0),
 (5,'Wei Chen','+66811112205','wei.chen@example.com','gold',1610,1),
 (6,'Suda Meechai','+66811112206',NULL,'standard',20,1),
 (7,'James Okafor','+66811112207','j.okafor@example.com','silver',560,1),
 (8,'Kanya Boonliang','+66811112208','kanya.b@example.com','standard',140,1),
 (9,'Thanaphon Rit','+66811112209','thanaphon@example.com','silver',690,0),
 (10,'Maria Lopez','+66811112210','m.lopez@example.com','gold',2050,1),
 (11,'Niran Chaiya','+66811112211','niran.c@example.com','standard',45,1),
 (12,'Aiko Tanaka','+66811112212','aiko.t@example.com','platinum',7300,1);

-- Addresses -------------------------------------------------------------------
INSERT INTO addresses (id, customer_id, label, line1, line2, district, city, postal_code, lat, lng, is_default) VALUES
 (1,1,'home','88/12 Soi Sukhumvit 31','Floor 7','Watthana','Bangkok','10110',13.7382,100.5610,1),
 (2,2,'home','199 Phahonyothin Rd',NULL,'Chatuchak','Bangkok','10900',13.8290,100.5600,1),
 (3,3,'condo','1 Sathorn Square','Unit 2204','Sathon','Bangkok','10120',13.7220,100.5290,1),
 (4,4,'home','45/3 Charoen Krung 50',NULL,'Bang Rak','Bangkok','10500',13.7220,100.5160,1),
 (5,5,'office','323 United Center','Silom Fl 18','Bang Rak','Bangkok','10500',13.7250,100.5340,1),
 (6,6,'home','12 Ratchadaphisek 18',NULL,'Huai Khwang','Bangkok','10310',13.7690,100.5740,1),
 (7,7,'home','77 Ekkamai 12',NULL,'Watthana','Bangkok','10110',13.7270,100.5850,1),
 (8,8,'home','250 Ladprao 101',NULL,'Bang Kapi','Bangkok','10240',13.7770,100.6420,1),
 (9,9,'home','9/9 Rama 9 Soi 7',NULL,'Huai Khwang','Bangkok','10310',13.7560,100.5660,1),
 (10,10,'condo','The Base Park','Unit 1510','Watthana','Bangkok','10110',13.7300,100.5900,1),
 (11,11,'home','5 Thonglor 25',NULL,'Watthana','Bangkok','10110',13.7400,100.5830,1),
 (12,12,'office','GreenTower 21F','Asok','Watthana','Bangkok','10110',13.7370,100.5600,1),
 (13,3,'office','Empire Tower','Unit 4701','Sathon','Bangkok','10120',13.7210,100.5280,0);

-- Couriers --------------------------------------------------------------------
INSERT INTO couriers (id, full_name, phone, vehicle, status, zone, rating) VALUES
 (1,'Boonmee Lertsak','+66822220001','motorbike','available','Watthana',4.92),
 (2,'Chai Wattana','+66822220002','motorbike','available','Sathon',4.81),
 (3,'Decha Inta','+66822220003','bicycle','on_delivery','Bang Rak',4.66),
 (4,'Farid Hasan','+66822220004','motorbike','available','Huai Khwang',4.88),
 (5,'Gosol Pintu','+66822220005','car','on_break','Chatuchak',4.45),
 (6,'Henry Adams','+66822220006','van','available','Bang Kapi',4.73);

-- Categories ------------------------------------------------------------------
-- Browse categories mirror the 7-Eleven delivery app's top-level menu.
INSERT INTO categories (id, slug, name, sort_order) VALUES
 (1,'ready-to-eat','Ready-to-Eat Meals',1),
 (2,'all-cafe','All Café Coffee & Drinks',2),
 (3,'bakery','Bakery & Toasties',3),
 (4,'beverages','Beverages',4),
 (5,'snacks','Snacks & Sweets',5),
 (6,'household','Daily Essentials',6),
 (7,'frozen','Frozen & Slurpee',7),
 (8,'personal-care','Personal Care',8);

-- Products (price_satang = THB * 100) -----------------------------------------
INSERT INTO products (id, category_id, sku, name, description, unit, price_satang, is_active) VALUES
 (1,1,'PRD-RTE-001','Pork & Basil Rice Bowl','Microwave-ready pad krapao with rice','box',3500,1),
 (2,1,'PRD-RTE-002','Chicken Teriyaki Rice Box','Heat-and-eat teriyaki on rice','box',5900,1),
 (3,1,'PRD-RTE-003','Tuna Spicy Salad Wrap','Chilled tortilla wrap','each',4500,1),
 (4,1,'PRD-RTE-004','Stir-fried Noodle Box','Pad see ew, ready to heat','box',5500,1),
 (5,2,'PRD-CAFE-001','All Café Iced Americano','Freshly brewed, cup','cup',5800,1),
 (6,2,'PRD-CAFE-002','All Café Iced Latte','Espresso & fresh milk','cup',7900,1),
 (7,2,'PRD-CAFE-003','All Café Cappuccino (Hot)','Double shot, hot','cup',9900,1),
 (8,2,'PRD-CAFE-004','All Café Cold Brew 500ml','Slow-steeped, bottle','bottle',12500,1),
 (9,3,'PRD-BK-001','Sourdough Loaf','Baked this morning','each',8900,1),
 (10,3,'PRD-BK-002','Croissant x4','Butter croissants','pack',13900,1),
 (11,3,'PRD-BK-003','Whole Wheat Bread','Sliced, 500g','each',5500,1),
 (12,4,'PRD-BV-001','Sparkling Water 6x330ml','Lightly carbonated','pack',11900,1),
 (13,4,'PRD-BV-002','Cold Brew Coffee 1L','Unsweetened','bottle',15900,1),
 (14,4,'PRD-BV-003','Orange Juice 1L','100% squeezed','bottle',8900,1),
 (15,4,'PRD-BV-004','Thai Milk Tea 4-pack','Ready to drink','pack',9900,1),
 (16,5,'PRD-SN-001','Dark Chocolate 70%','100g bar','each',7500,1),
 (17,5,'PRD-SN-002','Mixed Nuts 200g','Roasted, lightly salted','pack',13900,1),
 (18,5,'PRD-SN-003','Seaweed Snack x5','Crispy roasted','pack',4900,1),
 (19,5,'PRD-SN-004','Potato Chips 150g','Sea salt','each',5900,1),
 (20,6,'PRD-HH-001','Dish Soap 500ml','Lemon scent','bottle',6900,1),
 (21,6,'PRD-HH-002','Paper Towels x4','2-ply','pack',9900,1),
 (22,6,'PRD-HH-003','Trash Bags 30L x30','Heavy duty','pack',7900,1),
 (23,6,'PRD-HH-004','Laundry Detergent 2L','Concentrated','bottle',18900,1),
 (24,7,'PRD-FZ-001','Frozen Dumplings 500g','Pork & chive, 25 pcs','pack',14900,1),
 (25,7,'PRD-FZ-002','Vanilla Ice Cream 1L','Premium','each',16900,1),
 (26,7,'PRD-FZ-003','Frozen Berries 400g','Mixed','pack',12900,1),
 (27,8,'PRD-PC-001','Toothpaste 100g','Mint fresh','each',4500,1),
 (28,8,'PRD-PC-002','Hand Soap 250ml','Antibacterial','bottle',5900,1),
 (29,8,'PRD-PC-003','Shampoo 400ml','For all hair types','bottle',15900,1),
 (30,8,'PRD-PC-004','Facial Tissue x3','Soft, 3 boxes','pack',8900,0),
 -- eleven-7 signature items
 (31,1,'PRD-RTE-005','Toasted Ham & Cheese','Grilled in store, hot','each',3900,1),
 (32,1,'PRD-RTE-006','Salmon Onigiri','Seaweed rice ball','each',2500,1),
 (33,1,'PRD-RTE-007','Steamed Pork Bun (Salapao)','Classic, hot','each',2200,1),
 (34,7,'PRD-FZ-004','Slurpee Cola (Large)','Frozen drink, large cup','cup',2900,1),
 (35,2,'PRD-CAFE-005','All Café Matcha Latte (Iced)','Stone-ground matcha','cup',8500,1),
 (36,5,'PRD-SN-005','Banana Milk 200ml','Local favourite','bottle',1800,1);

-- Inventory -------------------------------------------------------------------
INSERT INTO inventory (product_id, qty_on_hand, reorder_level) VALUES
 (1,120,20),(2,40,10),(3,55,15),(4,60,15),(5,80,20),(6,90,20),(7,35,10),(8,25,8),
 (9,18,6),(10,22,8),(11,40,12),(12,70,15),(13,30,10),(14,45,12),(15,50,15),
 (16,65,15),(17,28,10),(18,110,25),(19,75,20),(20,60,15),(21,48,12),(22,52,12),
 (23,20,8),(24,33,10),(25,26,8),(26,30,10),(27,80,20),(28,70,18),(29,24,8),(30,0,10),
 (31,90,25),(32,120,30),(33,140,30),(34,200,40),(35,45,12),(36,160,35);

-- Orders ----------------------------------------------------------------------
-- Money is consistent: subtotal = sum(line_total); total = subtotal + delivery_fee - discount.
-- store_id = nearest branch by district; pickup orders carry a 0 delivery fee.
INSERT INTO orders (id, order_no, customer_id, address_id, store_id, fulfillment_type, status, subtotal_satang, delivery_fee_satang, discount_satang, total_satang, placed_at) VALUES
 (1,'E7-240610-0001',1,1,1,'delivery','delivered',  21700,2900,0,    24600,'2026-06-10 09:14:00'),
 (2,'E7-240610-0002',3,3,2,'pickup','delivered',    42300,0,2000,    40300,'2026-06-10 12:40:00'),
 (3,'E7-240611-0003',5,5,3,'delivery','delivered',  27200,2900,0,    30100,'2026-06-11 08:05:00'),
 (4,'E7-240611-0004',2,2,5,'delivery','delivered',  14400,3500,0,    17900,'2026-06-11 18:22:00'),
 (5,'E7-240612-0005',7,7,1,'delivery','dispatched', 32800,2900,0,    35700,'2026-06-12 10:31:00'),
 (6,'E7-240612-0006',10,10,1,'delivery','preparing',22800,2900,1500, 24200,'2026-06-12 11:02:00'),
 (7,'E7-240612-0007',4,4,3,'delivery','confirmed',  9400,3500,0,     12900,'2026-06-12 11:47:00'),
 (8,'E7-240612-0008',12,12,1,'pickup','pending',    47700,0,0,       47700,'2026-06-12 12:15:00'),
 (9,'E7-240609-0009',8,8,6,'delivery','cancelled',  11900,3500,0,    15400,'2026-06-09 19:05:00'),
 (10,'E7-240612-0010',6,6,4,'delivery','delivered', 9400,3500,0,     12900,'2026-06-12 09:50:00'),
 (11,'E7-240612-0011',9,9,4,'delivery','preparing', 28400,2900,1000, 30300,'2026-06-12 13:20:00'),
 (12,'E7-240612-0012',11,11,1,'delivery','dispatched',21300,2900,0,  24200,'2026-06-12 14:02:00');

-- Order items (snapshots) -----------------------------------------------------
INSERT INTO order_items (order_id, product_id, product_name, qty, unit_price_satang, line_total_satang) VALUES
 -- order 1 (subtotal 21700)
 (1,1,'Pork & Basil Rice Bowl',2,3500,7000),(1,5,'All Café Iced Americano',1,5800,5800),(1,9,'Sourdough Loaf',1,8900,8900),
 -- order 2 (subtotal 42300)
 (2,8,'All Café Cold Brew 500ml',1,12500,12500),(2,10,'Croissant x4',1,13900,13900),(2,13,'Cold Brew Coffee 1L',1,15900,15900),
 -- order 3 (25800)
 (3,6,'All Café Iced Latte',1,7900,7900),(3,7,'All Café Cappuccino (Hot)',1,9900,9900),(3,18,'Seaweed Snack x5',1,4900,4900),(3,27,'Toothpaste 100g',1,4500,4500),
 -- order 4 (15300)
 (4,11,'Whole Wheat Bread',1,5500,5500),(4,14,'Orange Juice 1L',1,8900,8900),
 -- order 5 (33700)
 (5,17,'Mixed Nuts 200g',1,13900,13900),(5,23,'Laundry Detergent 2L',1,18900,18900),
 -- order 6 (22700)
 (6,2,'Chicken Teriyaki Rice Box',2,5900,11800),(6,4,'Stir-fried Noodle Box',2,5500,11000),
 -- order 7 (9400)
 (7,1,'Pork & Basil Rice Bowl',1,3500,3500),(7,19,'Potato Chips 150g',1,5900,5900),
 -- order 8 (47600)
 (8,24,'Frozen Dumplings 500g',1,14900,14900),(8,25,'Vanilla Ice Cream 1L',1,16900,16900),(8,29,'Shampoo 400ml',1,15900,15900),
 -- order 9 (11800) cancelled
 (9,12,'Sparkling Water 6x330ml',1,11900,11900),
 -- order 10 (7400)
 (10,3,'Tuna Spicy Salad Wrap',1,4500,4500),(10,18,'Seaweed Snack x5',1,4900,4900),
 -- order 11 (28800)
 (11,16,'Dark Chocolate 70%',2,7500,15000),(11,15,'Thai Milk Tea 4-pack',1,9900,9900),(11,1,'Pork & Basil Rice Bowl',1,3500,3500),
 -- order 12 (19800)
 (12,21,'Paper Towels x4',1,9900,9900),(12,20,'Dish Soap 500ml',1,6900,6900),(12,27,'Toothpaste 100g',1,4500,4500);

-- Deliveries ------------------------------------------------------------------
INSERT INTO deliveries (id, order_id, courier_id, status, assigned_at, delivered_at, eta_minutes, proof_photo_url) VALUES
 (1,1,1,'delivered','2026-06-10 09:20:00','2026-06-10 09:52:00',32,'https://cdn.eleven7.app/proofs/1.jpg'),
 (2,2,2,'delivered','2026-06-10 12:48:00','2026-06-10 13:25:00',37,'https://cdn.eleven7.app/proofs/2.jpg'),
 (3,3,2,'delivered','2026-06-11 08:12:00','2026-06-11 08:44:00',32,'https://cdn.eleven7.app/proofs/3.jpg'),
 (4,4,1,'delivered','2026-06-11 18:30:00','2026-06-11 19:08:00',38,'https://cdn.eleven7.app/proofs/4.jpg'),
 (5,5,3,'en_route','2026-06-12 10:40:00',NULL,28,NULL),
 (6,6,NULL,'queued',NULL,NULL,NULL,NULL),
 (7,10,4,'delivered','2026-06-12 09:58:00','2026-06-12 10:29:00',31,'https://cdn.eleven7.app/proofs/10.jpg'),
 (8,12,1,'assigned','2026-06-12 14:10:00',NULL,25,NULL),
 (9,11,NULL,'queued',NULL,NULL,NULL,NULL);

-- Payments --------------------------------------------------------------------
INSERT INTO payments (id, order_id, method, status, amount_satang, provider_ref) VALUES
 (1,1,'promptpay','captured',24600,'PP-9F2A11'),
 (2,2,'credit_card','captured',40300,'CC-7731KK'),
 (3,3,'wallet','captured',30100,'WL-552210'),
 (4,4,'promptpay','captured',17900,'PP-8841BC'),
 (5,5,'credit_card','authorized',35700,'CC-9920LM'),
 (6,6,'cash_on_delivery','pending',24200,NULL),
 (7,7,'promptpay','pending',12900,NULL),
 (8,8,'credit_card','pending',47700,NULL),
 (9,9,'promptpay','refunded',15400,'PP-1102ZZ'),
 (10,10,'cash_on_delivery','captured',12900,NULL),
 (11,11,'wallet','authorized',30300,'WL-779001'),
 (12,12,'promptpay','captured',24200,'PP-6650QR');

-- Notifications outbox --------------------------------------------------------
INSERT INTO notifications (id, customer_id, order_id, channel, template, destination, body, status, provider_message_id) VALUES
 (1,1,1,'sms','order_confirmed','+66811112201','eleven-7: Order E7-240610-0001 confirmed. Total THB 246.00.','sent','sns-msg-0001'),
 (2,1,1,'sms','out_for_delivery','+66811112201','eleven-7: Your order is on the way! Courier Boonmee, ETA 32 min.','sent','sns-msg-0002'),
 (3,1,1,'sms','delivered','+66811112201','eleven-7: Order E7-240610-0001 delivered. Enjoy!','sent','sns-msg-0003'),
 (4,3,2,'sms','order_confirmed','+66811112203','eleven-7: Order E7-240610-0002 confirmed. Total THB 403.00.','sent','sns-msg-0004'),
 (5,5,3,'sms','delivered','+66811112205','eleven-7: Order E7-240611-0003 delivered. Enjoy!','sent','sns-msg-0005'),
 (6,7,5,'sms','out_for_delivery','+66811112207','eleven-7: Your order is on the way! Courier Decha, ETA 28 min.','sent','sns-msg-0006'),
 (7,4,7,'sms','order_confirmed','+66811112204','eleven-7: Order E7-240612-0007 confirmed. Total THB 129.00.','sent','sns-msg-0007'),
 (8,6,10,'sms','delivered','+66811112206','eleven-7: Order E7-240612-0010 delivered. Enjoy!','sent','sns-msg-0008'),
 (9,8,9,'sms','order_cancelled','+66811112208','eleven-7: Order E7-240609-0009 was cancelled and refunded.','sent','sns-msg-0009'),
 (10,11,12,'sms','out_for_delivery','+66811112211','eleven-7: Your order is on the way! Courier Boonmee, ETA 25 min.','queued',NULL);
