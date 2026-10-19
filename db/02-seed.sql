INSERT INTO currencies (code, name, symbol, decimals) VALUES
  ('EUR', 'Euro', '€', 2),
  ('USD', 'US Dollar', '$', 2),
  ('GBP', 'Pound Sterling', '£', 2),
  ('JPY', 'Yen', '¥', 0),
  ('CHF', 'Swiss Franc', 'CHF', 2),
  ('SEK', 'Swedish Krona', 'kr', 2),
  ('NOK', 'Norwegian Krone', 'kr', 2),
  ('DKK', 'Danish Krone', 'kr', 2),
  ('CAD', 'Canadian Dollar', '$', 2),
  ('AUD', 'Australian Dollar', '$', 2);

INSERT INTO countries (code, name, currency_code) VALUES
  ('FR', 'France', 'EUR'),
  ('GB', 'United Kingdom', 'GBP'),
  ('US', 'United States', 'USD'),
  ('FI', 'Finland', 'EUR'),
  ('DE', 'Germany', 'EUR'),
  ('JP', 'Japan', 'JPY'),
  ('CH', 'Switzerland', 'CHF'),
  ('SE', 'Sweden', 'SEK'),
  ('CA', 'Canada', 'CAD'),
  ('AU', 'Australia', 'AUD');

INSERT INTO customers (username, first_name, last_name, email, country_code, status, created_at) VALUES
  ('ada', 'Ada', 'Lovelace', 'ada@example.com', 'GB', 'active', '2024-01-10 09:30:00'),
  ('grace', 'Grace', 'Hopper', 'grace@example.com', 'US', 'active', '2024-02-11 09:30:00'),
  ('linus', 'Linus', 'Torvalds', 'linus@example.com', 'FI', 'active', '2024-03-12 09:30:00'),
  ('alan', 'Alan', 'Turing', 'alan@example.com', 'GB', 'active', '2024-04-13 09:30:00'),
  ('margaret', 'Margaret', 'Hamilton', 'margaret@example.com', 'US', 'active', '2024-05-14 09:30:00'),
  ('dennis', 'Dennis', 'Ritchie', 'dennis@example.com', 'US', 'closed', '2024-06-15 09:30:00'),
  ('barbara', 'Barbara', 'Liskov', 'barbara@example.com', 'US', 'active', '2024-07-16 09:30:00'),
  ('ken', 'Ken', 'Thompson', 'ken@example.com', 'US', 'active', '2024-08-17 09:30:00'),
  ('katherine', 'Katherine', 'Johnson', 'katherine@example.com', 'US', 'active', '2024-09-18 09:30:00'),
  ('zoe', 'Zoe', 'Martin', 'zoe@example.com', 'FR', 'active', '2024-01-19 09:30:00');

INSERT INTO customer_addresses (customer_id, line1, city, postal_code, country_code, is_default) VALUES
  (1, '10 Main Street', 'London', 'SW1A 1AA', 'GB', TRUE),
  (2, '11 Main Street', 'Arlington', '22201', 'US', TRUE),
  (3, '12 Main Street', 'Helsinki', '00100', 'FI', TRUE),
  (4, '13 Main Street', 'London', 'SW1A 1AA', 'GB', TRUE),
  (5, '14 Main Street', 'Arlington', '22201', 'US', TRUE),
  (6, '15 Main Street', 'Arlington', '22201', 'US', TRUE),
  (7, '16 Main Street', 'Arlington', '22201', 'US', TRUE),
  (8, '17 Main Street', 'Arlington', '22201', 'US', TRUE),
  (9, '18 Main Street', 'Arlington', '22201', 'US', TRUE),
  (10, '19 Main Street', 'Paris', '75011', 'FR', TRUE);

INSERT INTO customer_preferences (customer_id, language, newsletter_opt_in, theme) VALUES
  (1, 'en', TRUE, 'dark'),
  (2, 'en', FALSE, 'light'),
  (3, 'en', TRUE, 'light'),
  (4, 'en', FALSE, 'dark'),
  (5, 'en', TRUE, 'light'),
  (6, 'en', FALSE, 'light'),
  (7, 'en', TRUE, 'dark'),
  (8, 'en', FALSE, 'light'),
  (9, 'en', TRUE, 'light'),
  (10, 'fr', FALSE, 'dark');

INSERT INTO bank_accounts (customer_id, iban, currency_code, balance_cents, is_primary, opened_at) VALUES
  (1, 'FR763000600000112345678000', 'EUR', 125075, TRUE, '2023-01-01'),
  (2, 'FR763000600000212345678001', 'EUR', 980040, TRUE, '2023-02-01'),
  (3, 'FR763000600000312345678002', 'EUR', 43210, TRUE, '2023-03-01'),
  (4, 'FR763000600000412345678003', 'EUR', 7700, TRUE, '2023-04-01'),
  (5, 'FR763000600000512345678004', 'EUR', 1500000, TRUE, '2023-05-01'),
  (6, 'FR763000600000612345678005', 'EUR', 0, TRUE, '2023-06-01'),
  (7, 'FR763000600000712345678006', 'EUR', 268999, TRUE, '2023-07-01'),
  (8, 'FR763000600000812345678007', 'EUR', 51234, TRUE, '2023-08-01'),
  (9, 'FR763000600000912345678008', 'EUR', 77777, TRUE, '2023-09-01'),
  (1, 'FR7630006000099123456789999', 'EUR', 4200000, FALSE, '2025-01-15');

INSERT INTO bank_transactions (account_id, amount_cents, label, booked_at) VALUES
  (1, 320000, 'Salary', '2026-09-10 12:00:00'),
  (2, -2231, 'Rent', '2026-09-11 12:00:00'),
  (3, -2962, 'Groceries', '2026-09-12 12:00:00'),
  (4, -3693, 'Train ticket', '2026-09-13 12:00:00'),
  (5, -4424, 'Bookshop', '2026-09-14 12:00:00'),
  (6, -5155, 'Refund', '2026-09-15 12:00:00'),
  (7, -5886, 'Electricity', '2026-09-16 12:00:00'),
  (8, -6617, 'Restaurant', '2026-09-17 12:00:00'),
  (9, -7348, 'Gym', '2026-09-18 12:00:00'),
  (1, -8079, 'Transfer to savings', '2026-09-19 12:00:00');

INSERT INTO product_categories (name, parent_id) VALUES
  ('Books', NULL),
  ('Electronics', NULL),
  ('Home', NULL),
  ('Science fiction', 1),
  ('Programming', 1),
  ('Laptops', 2),
  ('Headphones', 2),
  ('Kitchen', 3),
  ('Garden', 3),
  ('History', 1);

INSERT INTO suppliers (name, country_code, contact_email) VALUES
  ('Paper & Ink', 'FR', 'sales@paperink.example'),
  ('Bytes Ltd', 'GB', 'hello@bytes.example'),
  ('Nordic Sound', 'SE', 'contact@nordicsound.example'),
  ('Casa Bella', 'DE', 'info@casabella.example'),
  ('Green Thumb', 'FR', 'shop@greenthumb.example'),
  ('Pacific Tech', 'JP', 'b2b@pacifictech.example'),
  ('Alpine Goods', 'CH', 'orders@alpine.example'),
  ('Maple Books', 'CA', 'team@maplebooks.example'),
  ('Outback Home', 'AU', 'sales@outback.example'),
  ('Liberty Supply', 'US', 'ops@liberty.example');

INSERT INTO products (sku, name, category_id, supplier_id, price_cents, currency_code) VALUES
  ('BK-0001', 'Notes on the Analytical Engine', 5, 1, 1990, 'EUR'),
  ('BK-0002', 'The Art of Compiling', 5, 8, 4500, 'EUR'),
  ('BK-0003', 'Foundation', 4, 8, 1250, 'EUR'),
  ('EL-0001', 'Ultrabook 14', 6, 6, 129900, 'EUR'),
  ('EL-0002', 'Studio Headphones', 7, 3, 19900, 'EUR'),
  ('EL-0003', 'Noise Cancelling Buds', 7, 3, 14900, 'EUR'),
  ('HM-0001', 'Chef Knife', 8, 4, 8900, 'EUR'),
  ('HM-0002', 'Espresso Maker', 8, 7, 24900, 'EUR'),
  ('HM-0003', 'Garden Hose 20m', 9, 5, 3490, 'EUR'),
  ('BK-0004', 'A Short History of Computing', 10, 1, 2290, 'EUR');

INSERT INTO warehouses (name, city, country_code) VALUES
  ('Paris North', 'Saint-Denis', 'FR'),
  ('Lyon', 'Lyon', 'FR'),
  ('London East', 'London', 'GB'),
  ('Berlin', 'Berlin', 'DE'),
  ('Stockholm', 'Stockholm', 'SE'),
  ('Zurich', 'Zurich', 'CH'),
  ('Toronto', 'Toronto', 'CA'),
  ('Sydney', 'Sydney', 'AU'),
  ('Osaka', 'Osaka', 'JP'),
  ('Newark', 'Newark', 'US');

INSERT INTO stock_levels (product_id, warehouse_id, quantity) VALUES
  (1, 1, 5),
  (2, 2, 12),
  (3, 3, 19),
  (4, 4, 0),
  (5, 1, 33),
  (6, 2, 40),
  (7, 3, 47),
  (8, 4, 54),
  (9, 1, 61),
  (10, 2, 68);

INSERT INTO payment_methods (code, label) VALUES
  ('card', 'Credit card'),
  ('sepa', 'SEPA direct debit'),
  ('paypal', 'PayPal'),
  ('apple_pay', 'Apple Pay'),
  ('google_pay', 'Google Pay'),
  ('transfer', 'Bank transfer'),
  ('gift_card', 'Gift card'),
  ('voucher', 'Voucher'),
  ('klarna', 'Pay later'),
  ('cash', 'Cash on delivery');

INSERT INTO orders (customer_id, status, ordered_at, currency_code, total_cents) VALUES
  (1, 'delivered', '2026-08-10 14:10:00', 'EUR', 1990),
  (2, 'delivered', '2026-08-11 14:11:00', 'EUR', 129900),
  (3, 'shipped', '2026-08-12 14:12:00', 'EUR', 19900),
  (4, 'paid', '2026-08-13 14:13:00', 'EUR', 4500),
  (5, 'pending', '2026-08-14 14:14:00', 'EUR', 8900),
  (6, 'cancelled', '2026-08-15 14:15:00', 'EUR', 3490),
  (7, 'delivered', '2026-08-16 14:16:00', 'EUR', 24900),
  (8, 'shipped', '2026-08-17 14:17:00', 'EUR', 2290),
  (9, 'paid', '2026-08-18 14:18:00', 'EUR', 14900),
  (1, 'delivered', '2026-08-19 14:19:00', 'EUR', 1250);

INSERT INTO order_items (order_id, product_id, quantity, unit_price_cents) VALUES
  (1, 1, 1, 1990),
  (2, 4, 1, 129900),
  (3, 5, 1, 19900),
  (4, 2, 1, 4500),
  (5, 7, 1, 8900),
  (6, 9, 1, 3490),
  (7, 8, 1, 24900),
  (8, 10, 1, 2290),
  (9, 6, 1, 14900),
  (10, 3, 1, 1250);

INSERT INTO invoices (order_id, number, issued_at, total_cents) VALUES
  (1, 'INV-2026-1000', '2026-08-10 15:00:00', 1990),
  (2, 'INV-2026-1001', '2026-08-11 15:00:00', 129900),
  (3, 'INV-2026-1002', '2026-08-12 15:00:00', 19900),
  (4, 'INV-2026-1003', '2026-08-13 15:00:00', 4500),
  (5, 'INV-2026-1004', '2026-08-14 15:00:00', 8900),
  (6, 'INV-2026-1005', '2026-08-15 15:00:00', 3490),
  (7, 'INV-2026-1006', '2026-08-16 15:00:00', 24900),
  (8, 'INV-2026-1007', '2026-08-17 15:00:00', 2290),
  (9, 'INV-2026-1008', '2026-08-18 15:00:00', 14900),
  (10, 'INV-2026-1009', '2026-08-19 15:00:00', 1250);

INSERT INTO payments (invoice_id, payment_method_id, amount_cents, status, paid_at) VALUES
  (1, 1, 1990, 'captured', '2026-08-10 15:05:00'),
  (2, 2, 129900, 'captured', '2026-08-11 15:05:00'),
  (3, 3, 19900, 'captured', '2026-08-12 15:05:00'),
  (4, 4, 4500, 'captured', '2026-08-13 15:05:00'),
  (5, 5, 8900, 'authorized', '2026-08-14 15:05:00'),
  (6, 1, 3490, 'refunded', '2026-08-15 15:05:00'),
  (7, 2, 24900, 'captured', '2026-08-16 15:05:00'),
  (8, 3, 2290, 'captured', '2026-08-17 15:05:00'),
  (9, 4, 14900, 'captured', '2026-08-18 15:05:00'),
  (10, 5, 1250, 'captured', '2026-08-19 15:05:00');

INSERT INTO carriers (name, tracking_url) VALUES
  ('Swift Post', 'https://track.swiftpost.example/{number}'),
  ('Blue Truck', 'https://track.bluetruck.example/{number}'),
  ('Rail Cargo', 'https://track.railcargo.example/{number}'),
  ('Air Parcel', 'https://track.airparcel.example/{number}'),
  ('City Bike', 'https://track.citybike.example/{number}'),
  ('Euro Freight', 'https://track.eurofreight.example/{number}'),
  ('North Courier', 'https://track.northcourier.example/{number}'),
  ('Pacific Ship', 'https://track.pacificship.example/{number}'),
  ('Mountain Mail', 'https://track.mountainmail.example/{number}'),
  ('Last Mile', 'https://track.lastmile.example/{number}');

INSERT INTO shipments (order_id, carrier_id, tracking_number, shipped_at, delivered_at) VALUES
  (1, 1, 'TRK900000', '2026-08-11 08:00:00', '2026-08-13 17:00:00'),
  (2, 2, 'TRK900037', '2026-08-12 08:00:00', '2026-08-14 17:00:00'),
  (3, 3, 'TRK900074', '2026-08-13 08:00:00', NULL),
  (4, 4, 'TRK900111', '2026-08-14 08:00:00', NULL),
  (5, 5, 'TRK900148', '2026-08-15 08:00:00', NULL),
  (6, 6, 'TRK900185', '2026-08-16 08:00:00', NULL),
  (7, 7, 'TRK900222', '2026-08-17 08:00:00', '2026-08-19 17:00:00'),
  (8, 8, 'TRK900259', '2026-08-18 08:00:00', NULL),
  (9, 9, 'TRK900296', '2026-08-19 08:00:00', NULL),
  (10, 10, 'TRK900333', '2026-08-20 08:00:00', '2026-08-22 17:00:00');

INSERT INTO returns (order_item_id, reason, status, requested_at) VALUES
  (1, 'Damaged on arrival', 'refunded', '2026-08-20 10:00:00'),
  (2, 'Wrong size', 'accepted', '2026-08-21 10:00:00'),
  (3, 'Changed my mind', 'refused', '2026-08-22 10:00:00'),
  (4, 'Late delivery', 'requested', '2026-08-23 10:00:00'),
  (5, 'Missing part', 'accepted', '2026-08-24 10:00:00'),
  (6, 'Duplicate order', 'refunded', '2026-08-25 10:00:00'),
  (7, 'Not as described', 'requested', '2026-08-26 10:00:00'),
  (8, 'Gift not wanted', 'refused', '2026-08-27 10:00:00'),
  (9, 'Defective', 'accepted', '2026-08-28 10:00:00'),
  (10, 'Better price elsewhere', 'refused', '2026-08-29 10:00:00');

INSERT INTO promotions (name, percent_off, starts_on, ends_on) VALUES
  ('Winter sale', 30, '2026-01-01', '2026-01-28'),
  ('Back to school', 15, '2026-09-01', '2026-09-28'),
  ('Spring clean', 20, '2026-03-01', '2026-03-28'),
  ('Summer books', 10, '2026-07-01', '2026-07-28'),
  ('Black Friday', 40, '2026-11-01', '2026-11-28'),
  ('New year', 25, '2026-01-01', '2026-01-28'),
  ('Gardening week', 12, '2026-04-01', '2026-04-28'),
  ('Tech days', 18, '2026-10-01', '2026-10-28'),
  ('Loyalty', 5, '2026-06-01', '2026-06-28'),
  ('Flash sale', 50, '2026-12-01', '2026-12-28');

INSERT INTO coupons (code, promotion_id, max_uses, used_count) VALUES
  ('SAVE10', 1, 100, 0),
  ('SAVE11', 2, 200, 7),
  ('SAVE12', 3, 300, 14),
  ('SAVE13', 4, 400, 21),
  ('SAVE14', 5, 500, 28),
  ('SAVE15', 6, 600, 35),
  ('SAVE16', 7, 700, 42),
  ('SAVE17', 8, 800, 49),
  ('SAVE18', 9, 900, 56),
  ('SAVE19', 10, 1000, 63);

INSERT INTO reviews (product_id, customer_id, rating, comment, created_at) VALUES
  (1, 1, 5, 'Brilliant', '2026-09-01 18:00:00'),
  (2, 2, 4, 'Does the job', '2026-09-02 18:00:00'),
  (3, 3, 2, 'Too expensive', '2026-09-03 18:00:00'),
  (4, 4, 5, 'Fast delivery', '2026-09-04 18:00:00'),
  (5, 5, 5, 'Would buy again', '2026-09-05 18:00:00'),
  (6, 6, 3, 'Average', '2026-09-06 18:00:00'),
  (7, 7, 1, 'Broke after a week', '2026-09-07 18:00:00'),
  (8, 8, 5, 'Perfect gift', '2026-09-08 18:00:00'),
  (9, 9, 4, 'Great sound', '2026-09-09 18:00:00'),
  (10, 1, 5, 'Sharp and solid', '2026-09-01 18:00:00');

INSERT INTO departments (name) VALUES
  ('Engineering'),
  ('Quality Assurance'),
  ('Customer Support'),
  ('Finance'),
  ('Logistics'),
  ('Marketing'),
  ('Sales'),
  ('Legal'),
  ('People'),
  ('Data');

INSERT INTO employees (department_id, first_name, last_name, email, hired_on, manager_id) VALUES
  (1, 'Marc', 'Duval', 'marc.duval@mycompany.example', '2015-01-01', NULL),
  (2, 'Thomas', 'Bernard', 'thomas.bernard@mycompany.example', '2016-02-01', 1),
  (2, 'Elena', 'Volkova', 'elena.volkova@mycompany.example', '2017-03-01', 2),
  (3, 'Paul', 'Moreau', 'paul.moreau@mycompany.example', '2018-04-01', 1),
  (3, 'Nora', 'Benali', 'nora.benali@mycompany.example', '2019-05-01', 4),
  (4, 'Laura', 'Rossi', 'laura.rossi@mycompany.example', '2020-06-01', NULL),
  (5, 'Hugo', 'Pereira', 'hugo.pereira@mycompany.example', '2021-07-01', NULL),
  (6, 'Claire', 'Fontaine', 'claire.fontaine@mycompany.example', '2022-08-01', NULL),
  (7, 'Louis', 'Garnier', 'louis.garnier@mycompany.example', '2023-09-01', NULL),
  (10, 'Lina', 'Marchand', 'lina.marchand@mycompany.example', '2024-01-01', 1);

INSERT INTO support_tickets (customer_id, assignee_id, subject, status, opened_at) VALUES
  (1, 4, 'Card refused', 'open', '2026-09-10 09:00:00'),
  (2, 5, 'Where is my parcel?', 'pending', '2026-09-11 09:00:00'),
  (3, 4, 'Wrong item received', 'solved', '2026-09-12 09:00:00'),
  (4, 5, 'Invoice copy', 'open', '2026-09-13 09:00:00'),
  (5, 4, 'Change my address', 'pending', '2026-09-14 09:00:00'),
  (6, 5, 'Close my account', 'solved', '2026-09-15 09:00:00'),
  (7, 4, 'Coupon not applied', 'open', '2026-09-16 09:00:00'),
  (8, 5, 'Refund delay', 'pending', '2026-09-17 09:00:00'),
  (9, 4, 'Password reset', 'solved', '2026-09-18 09:00:00'),
  (10, 5, 'Damaged box', 'open', '2026-09-19 09:00:00');

INSERT INTO ticket_messages (ticket_id, author_type, body, sent_at) VALUES
  (1, 'customer', 'Hello, could you help me?', '2026-09-10 09:15:00'),
  (2, 'employee', 'Sure, we are looking into it.', '2026-09-11 09:16:00'),
  (3, 'customer', 'Hello, could you help me?', '2026-09-12 09:17:00'),
  (4, 'employee', 'Sure, we are looking into it.', '2026-09-13 09:18:00'),
  (5, 'customer', 'Hello, could you help me?', '2026-09-14 09:19:00'),
  (6, 'employee', 'Sure, we are looking into it.', '2026-09-15 09:20:00'),
  (7, 'customer', 'Hello, could you help me?', '2026-09-16 09:21:00'),
  (8, 'employee', 'Sure, we are looking into it.', '2026-09-17 09:22:00'),
  (9, 'customer', 'Hello, could you help me?', '2026-09-18 09:23:00'),
  (10, 'employee', 'Sure, we are looking into it.', '2026-09-19 09:24:00');

INSERT INTO newsletters (title, sent_on) VALUES
  ('January picks', '2026-01-05'),
  ('February picks', '2026-02-05'),
  ('Spring arrivals', '2026-03-05'),
  ('Easter deals', '2026-04-05'),
  ('May reads', '2026-05-05'),
  ('Summer gear', '2026-06-05'),
  ('Holiday books', '2026-07-05'),
  ('Back to work', '2026-08-05'),
  ('Autumn tech', '2026-09-05'),
  ('October deals', '2026-10-05');

INSERT INTO newsletter_subscriptions (customer_id, newsletter_id, subscribed_at) VALUES
  (1, 1, '2026-01-02 08:00:00'),
  (2, 2, '2026-02-02 08:00:00'),
  (3, 3, '2026-03-02 08:00:00'),
  (4, 4, '2026-04-02 08:00:00'),
  (5, 5, '2026-05-02 08:00:00'),
  (6, 1, '2026-06-02 08:00:00'),
  (7, 2, '2026-07-02 08:00:00'),
  (8, 3, '2026-08-02 08:00:00'),
  (9, 4, '2026-09-02 08:00:00'),
  (10, 5, '2026-01-02 08:00:00');

INSERT INTO audit_logs (actor, action, entity, entity_id, logged_at) VALUES
  ('system', 'create', 'customers', 1, '2026-09-20 11:00:00'),
  ('thomas.bernard', 'update', 'orders', 3, '2026-09-21 11:00:00'),
  ('system', 'create', 'invoices', 2, '2026-09-22 11:00:00'),
  ('paul.moreau', 'solve', 'support_tickets', 3, '2026-09-23 11:00:00'),
  ('system', 'capture', 'payments', 1, '2026-09-24 11:00:00'),
  ('laura.rossi', 'refund', 'payments', 6, '2026-09-25 11:00:00'),
  ('system', 'close', 'customers', 6, '2026-09-26 11:00:00'),
  ('nora.benali', 'reply', 'ticket_messages', 2, '2026-09-27 11:00:00'),
  ('system', 'ship', 'shipments', 3, '2026-09-28 11:00:00'),
  ('hugo.pereira', 'restock', 'stock_levels', 4, '2026-09-29 11:00:00');
