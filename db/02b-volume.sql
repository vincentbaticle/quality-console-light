INSERT INTO customers (username, first_name, last_name, email, country_code, status, created_at)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 64)
SELECT CONCAT('customer', LPAD(n, 3, '0')), ELT(n % 8 + 1, 'Noor', 'Ines', 'Hugo', 'Lena', 'Elif', 'Yuki', 'Tomas', 'Mia'), ELT(n % 6 + 1, 'Moreau', 'Schmidt', 'Okafor', 'Lindqvist', 'Tanaka', 'Costa'), CONCAT('customer', LPAD(n, 3, '0'), '@example.com'), ELT(n % 10 + 1, 'FR', 'GB', 'US', 'FI', 'DE', 'JP', 'CH', 'SE', 'CA', 'AU'), IF(n % 13 = 0, 'closed', 'active'), TIMESTAMP('2025-01-01 09:00:00') + INTERVAL n DAY
FROM seq;

INSERT INTO customer_addresses (customer_id, line1, city, postal_code, country_code, is_default)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 87)
SELECT (n - 1) % 64 + 1, CONCAT(n, ' Market Street'), ELT(n % 5 + 1, 'Lyon', 'Leeds', 'Austin', 'Turku', 'Hamburg'), LPAD(n * 37 % 99999, 5, '0'), ELT(n % 10 + 1, 'FR', 'GB', 'US', 'FI', 'DE', 'JP', 'CH', 'SE', 'CA', 'AU'), n <= 64
FROM seq;

INSERT INTO customer_preferences (customer_id, language, newsletter_opt_in, theme)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 64)
SELECT n, ELT(n % 4 + 1, 'en', 'fr', 'de', 'ja'), n % 3 = 0, IF(n % 2 = 0, 'dark', 'light')
FROM seq;

INSERT INTO bank_accounts (customer_id, iban, currency_code, balance_cents, is_primary, opened_at)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 58)
SELECT n, CONCAT('FR76', LPAD(n, 23, '0')), 'EUR', n * 12345, TRUE, DATE('2025-02-01') + INTERVAL n DAY
FROM seq;

INSERT INTO bank_transactions (account_id, amount_cents, label, booked_at)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 113)
SELECT (n - 1) % 58 + 1, IF(n % 3 = 0, -1, 1) * n * 731, ELT(n % 4 + 1, 'Salary', 'Groceries', 'Rent', 'Refund'), TIMESTAMP('2026-06-01 08:00:00') + INTERVAL n HOUR
FROM seq;

INSERT INTO suppliers (name, country_code, contact_email)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 23)
SELECT CONCAT('Supplier ', n), ELT(n % 10 + 1, 'FR', 'GB', 'US', 'FI', 'DE', 'JP', 'CH', 'SE', 'CA', 'AU'), CONCAT('sales', n, '@supplier.test')
FROM seq;

INSERT INTO products (sku, name, category_id, supplier_id, price_cents, currency_code)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 47)
SELECT CONCAT('GN-', LPAD(n, 4, '0')), CONCAT(ELT(n % 5 + 1, 'Notebook', 'Desk Lamp', 'Backpack', 'Mug', 'Cable'), ' ', n), n % 10 + 1, n % 23 + 1, 500 + n * 137, 'EUR'
FROM seq;

INSERT INTO stock_levels (product_id, warehouse_id, quantity)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 94)
SELECT 11 + (n - 11) % 37, 2 + (n - 11) DIV 37, n * 7 % 90 + 10
FROM seq;

INSERT INTO orders (customer_id, status, ordered_at, currency_code, total_cents)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 76)
SELECT (n - 1) % 64 + 1, ELT(n % 5 + 1, 'pending', 'paid', 'shipped', 'delivered', 'cancelled'), TIMESTAMP('2026-05-01 10:00:00') + INTERVAL n * 9 HOUR, 'EUR', 1000 + n * 211
FROM seq;

INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 113)
SELECT (n - 1) % 76 + 1, n % 47 + 1, n % 3 + 1, 500 + n * 41
FROM seq;

INSERT INTO invoices (order_id, number, issued_at, total_cents)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 70)
SELECT n, CONCAT('INV-2025-', LPAD(n, 6, '0')), TIMESTAMP('2026-05-02 10:00:00') + INTERVAL n * 9 HOUR, 1000 + n * 211
FROM seq;

INSERT INTO payments (invoice_id, payment_method_id, amount_cents, status, paid_at)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 68)
SELECT n, n % 10 + 1, 1000 + n * 211, ELT(n % 4 + 1, 'authorized', 'captured', 'refunded', 'failed'), TIMESTAMP('2026-05-02 12:00:00') + INTERVAL n * 9 HOUR
FROM seq;

INSERT INTO shipments (order_id, carrier_id, tracking_number, shipped_at, delivered_at)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 71)
SELECT n, n % 10 + 1, CONCAT('TRK', LPAD(n, 9, '0')), TIMESTAMP('2026-05-03 10:00:00') + INTERVAL n * 9 HOUR, IF(n % 4 = 0, NULL, TIMESTAMP('2026-05-05 10:00:00') + INTERVAL n * 9 HOUR)
FROM seq;

INSERT INTO returns (order_item_id, reason, status, requested_at)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 19)
SELECT n, ELT(n % 3 + 1, 'Damaged', 'Wrong size', 'Changed mind'), ELT(n % 4 + 1, 'requested', 'accepted', 'refused', 'refunded'), TIMESTAMP('2026-06-10 10:00:00') + INTERVAL n DAY
FROM seq;

INSERT INTO promotions (name, percent_off, starts_on, ends_on)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 15)
SELECT CONCAT('Season sale ', n), 5 + n % 30, DATE('2026-01-01') + INTERVAL n * 10 DAY, DATE('2026-01-15') + INTERVAL n * 10 DAY
FROM seq;

INSERT INTO coupons (code, promotion_id, max_uses, used_count)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 42)
SELECT CONCAT('SAVE', LPAD(n, 4, '0')), (n - 1) % 15 + 1, 100, n % 37
FROM seq;

INSERT INTO reviews (product_id, customer_id, rating, comment, created_at)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 101)
SELECT (n - 1) % 47 + 1, (n - 1) % 64 + 1, n % 5 + 1, ELT(n % 4 + 1, 'Does the job', 'Great value', 'Arrived late', 'Would buy again'), TIMESTAMP('2026-04-01 18:00:00') + INTERVAL n * 13 HOUR
FROM seq;

INSERT INTO employees (department_id, first_name, last_name, email, hired_on, manager_id)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 33)
SELECT n % 10 + 1, ELT(n % 6 + 1, 'Sam', 'Lou', 'Eden', 'Kai', 'Noa', 'Rin'), CONCAT('Staff', n), CONCAT('employee', n, '@mycompany.test'), DATE('2023-01-01') + INTERVAL n * 17 DAY, 1
FROM seq;

INSERT INTO support_tickets (customer_id, assignee_id, subject, status, opened_at)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 52)
SELECT (n - 1) % 64 + 1, (n - 1) % 33 + 1, ELT(n % 4 + 1, 'Where is my parcel', 'Refund request', 'Cannot sign in', 'Invoice copy'), ELT(n % 3 + 1, 'open', 'pending', 'solved'), TIMESTAMP('2026-07-01 09:00:00') + INTERVAL n * 7 HOUR
FROM seq;

INSERT INTO ticket_messages (ticket_id, author_type, body, sent_at)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 113)
SELECT (n - 1) % 52 + 1, IF(n % 2 = 0, 'customer', 'employee'), CONCAT('Message ', n, ' of the conversation'), TIMESTAMP('2026-07-01 10:00:00') + INTERVAL n * 3 HOUR
FROM seq;

INSERT INTO newsletters (title, sent_on)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 12)
SELECT CONCAT('Monthly news ', n), DATE('2026-01-01') + INTERVAL n * 7 DAY
FROM seq;

INSERT INTO newsletter_subscriptions (customer_id, newsletter_id, subscribed_at)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 88)
SELECT 11 + (n - 11) % 54, 1 + (n - 11) DIV 54, TIMESTAMP('2026-02-01 08:00:00') + INTERVAL n DAY
FROM seq;

INSERT INTO audit_logs (actor, action, entity, entity_id, logged_at)
WITH RECURSIVE seq (n) AS (SELECT 11 UNION ALL SELECT n + 1 FROM seq WHERE n < 113)
SELECT ELT(n % 4 + 1, 'system', 'order-worker', 'support', 'finance'), ELT(n % 3 + 1, 'create', 'update', 'delete'), ELT(n % 4 + 1, 'order', 'invoice', 'customer', 'payment'), n, TIMESTAMP('2026-06-01 00:00:00') + INTERVAL n * 5 HOUR
FROM seq;
