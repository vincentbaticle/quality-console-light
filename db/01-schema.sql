CREATE TABLE currencies (
  code CHAR(3) PRIMARY KEY,
  name VARCHAR(50) NOT NULL,
  symbol VARCHAR(5) NOT NULL,
  decimals TINYINT NOT NULL DEFAULT 2
);

CREATE TABLE countries (
  code CHAR(2) PRIMARY KEY,
  name VARCHAR(80) NOT NULL,
  currency_code CHAR(3) NOT NULL,
  CONSTRAINT fk_countries_currency FOREIGN KEY (currency_code) REFERENCES currencies (code)
);

CREATE TABLE customers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(50) NOT NULL UNIQUE,
  first_name VARCHAR(50) NOT NULL,
  last_name VARCHAR(50) NOT NULL,
  email VARCHAR(120) NOT NULL UNIQUE,
  country_code CHAR(2) NOT NULL,
  status ENUM('active', 'closed') NOT NULL DEFAULT 'active',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_customers_country FOREIGN KEY (country_code) REFERENCES countries (code)
);

CREATE TABLE customer_addresses (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  line1 VARCHAR(120) NOT NULL,
  city VARCHAR(80) NOT NULL,
  postal_code VARCHAR(20) NOT NULL,
  country_code CHAR(2) NOT NULL,
  is_default BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT fk_addresses_customer FOREIGN KEY (customer_id) REFERENCES customers (id),
  CONSTRAINT fk_addresses_country FOREIGN KEY (country_code) REFERENCES countries (code)
);

CREATE TABLE customer_preferences (
  customer_id INT PRIMARY KEY,
  language CHAR(2) NOT NULL DEFAULT 'en',
  newsletter_opt_in BOOLEAN NOT NULL DEFAULT FALSE,
  theme ENUM('light', 'dark') NOT NULL DEFAULT 'light',
  CONSTRAINT fk_preferences_customer FOREIGN KEY (customer_id) REFERENCES customers (id)
);

CREATE TABLE bank_accounts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  iban VARCHAR(34) NOT NULL UNIQUE,
  currency_code CHAR(3) NOT NULL,
  balance_cents BIGINT NOT NULL,
  is_primary BOOLEAN NOT NULL DEFAULT TRUE,
  opened_at DATE NOT NULL,
  CONSTRAINT fk_accounts_customer FOREIGN KEY (customer_id) REFERENCES customers (id),
  CONSTRAINT fk_accounts_currency FOREIGN KEY (currency_code) REFERENCES currencies (code)
);

CREATE TABLE bank_transactions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  account_id INT NOT NULL,
  amount_cents BIGINT NOT NULL,
  label VARCHAR(120) NOT NULL,
  booked_at DATETIME NOT NULL,
  CONSTRAINT fk_transactions_account FOREIGN KEY (account_id) REFERENCES bank_accounts (id)
);

CREATE TABLE product_categories (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(80) NOT NULL,
  parent_id INT NULL,
  CONSTRAINT fk_categories_parent FOREIGN KEY (parent_id) REFERENCES product_categories (id)
);

CREATE TABLE suppliers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(80) NOT NULL,
  country_code CHAR(2) NOT NULL,
  contact_email VARCHAR(120) NOT NULL,
  CONSTRAINT fk_suppliers_country FOREIGN KEY (country_code) REFERENCES countries (code)
);

CREATE TABLE products (
  id INT AUTO_INCREMENT PRIMARY KEY,
  sku VARCHAR(30) NOT NULL UNIQUE,
  name VARCHAR(120) NOT NULL,
  category_id INT NOT NULL,
  supplier_id INT NOT NULL,
  price_cents INT NOT NULL,
  currency_code CHAR(3) NOT NULL,
  CONSTRAINT fk_products_category FOREIGN KEY (category_id) REFERENCES product_categories (id),
  CONSTRAINT fk_products_supplier FOREIGN KEY (supplier_id) REFERENCES suppliers (id),
  CONSTRAINT fk_products_currency FOREIGN KEY (currency_code) REFERENCES currencies (code)
);

CREATE TABLE warehouses (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(80) NOT NULL,
  city VARCHAR(80) NOT NULL,
  country_code CHAR(2) NOT NULL,
  CONSTRAINT fk_warehouses_country FOREIGN KEY (country_code) REFERENCES countries (code)
);

CREATE TABLE stock_levels (
  product_id INT NOT NULL,
  warehouse_id INT NOT NULL,
  quantity INT NOT NULL,
  PRIMARY KEY (product_id, warehouse_id),
  CONSTRAINT fk_stock_product FOREIGN KEY (product_id) REFERENCES products (id),
  CONSTRAINT fk_stock_warehouse FOREIGN KEY (warehouse_id) REFERENCES warehouses (id)
);

CREATE TABLE payment_methods (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(30) NOT NULL UNIQUE,
  label VARCHAR(80) NOT NULL
);

CREATE TABLE orders (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  status ENUM('pending', 'paid', 'shipped', 'delivered', 'cancelled') NOT NULL,
  ordered_at DATETIME NOT NULL,
  currency_code CHAR(3) NOT NULL,
  total_cents INT NOT NULL,
  CONSTRAINT fk_orders_customer FOREIGN KEY (customer_id) REFERENCES customers (id),
  CONSTRAINT fk_orders_currency FOREIGN KEY (currency_code) REFERENCES currencies (code)
);

CREATE TABLE order_items (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  product_id INT NOT NULL,
  quantity INT NOT NULL,
  unit_price_cents INT NOT NULL,
  CONSTRAINT fk_items_order FOREIGN KEY (order_id) REFERENCES orders (id),
  CONSTRAINT fk_items_product FOREIGN KEY (product_id) REFERENCES products (id)
);

CREATE TABLE invoices (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL UNIQUE,
  number VARCHAR(30) NOT NULL UNIQUE,
  issued_at DATETIME NOT NULL,
  total_cents INT NOT NULL,
  CONSTRAINT fk_invoices_order FOREIGN KEY (order_id) REFERENCES orders (id)
);

CREATE TABLE payments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  invoice_id INT NOT NULL,
  payment_method_id INT NOT NULL,
  amount_cents INT NOT NULL,
  status ENUM('authorized', 'captured', 'refunded', 'failed') NOT NULL,
  paid_at DATETIME NOT NULL,
  CONSTRAINT fk_payments_invoice FOREIGN KEY (invoice_id) REFERENCES invoices (id),
  CONSTRAINT fk_payments_method FOREIGN KEY (payment_method_id) REFERENCES payment_methods (id)
);

CREATE TABLE carriers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(80) NOT NULL,
  tracking_url VARCHAR(200) NOT NULL
);

CREATE TABLE shipments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_id INT NOT NULL,
  carrier_id INT NOT NULL,
  tracking_number VARCHAR(40) NOT NULL,
  shipped_at DATETIME NOT NULL,
  delivered_at DATETIME NULL,
  CONSTRAINT fk_shipments_order FOREIGN KEY (order_id) REFERENCES orders (id),
  CONSTRAINT fk_shipments_carrier FOREIGN KEY (carrier_id) REFERENCES carriers (id)
);

CREATE TABLE returns (
  id INT AUTO_INCREMENT PRIMARY KEY,
  order_item_id INT NOT NULL,
  reason VARCHAR(120) NOT NULL,
  status ENUM('requested', 'accepted', 'refused', 'refunded') NOT NULL,
  requested_at DATETIME NOT NULL,
  CONSTRAINT fk_returns_item FOREIGN KEY (order_item_id) REFERENCES order_items (id)
);

CREATE TABLE promotions (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(80) NOT NULL,
  percent_off TINYINT NOT NULL,
  starts_on DATE NOT NULL,
  ends_on DATE NOT NULL
);

CREATE TABLE coupons (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(30) NOT NULL UNIQUE,
  promotion_id INT NOT NULL,
  max_uses INT NOT NULL,
  used_count INT NOT NULL DEFAULT 0,
  CONSTRAINT fk_coupons_promotion FOREIGN KEY (promotion_id) REFERENCES promotions (id)
);

CREATE TABLE reviews (
  id INT AUTO_INCREMENT PRIMARY KEY,
  product_id INT NOT NULL,
  customer_id INT NOT NULL,
  rating TINYINT NOT NULL,
  comment VARCHAR(255) NOT NULL,
  created_at DATETIME NOT NULL,
  CONSTRAINT fk_reviews_product FOREIGN KEY (product_id) REFERENCES products (id),
  CONSTRAINT fk_reviews_customer FOREIGN KEY (customer_id) REFERENCES customers (id)
);

CREATE TABLE departments (
  id INT AUTO_INCREMENT PRIMARY KEY,
  name VARCHAR(80) NOT NULL UNIQUE
);

CREATE TABLE employees (
  id INT AUTO_INCREMENT PRIMARY KEY,
  department_id INT NOT NULL,
  first_name VARCHAR(50) NOT NULL,
  last_name VARCHAR(50) NOT NULL,
  email VARCHAR(120) NOT NULL UNIQUE,
  hired_on DATE NOT NULL,
  manager_id INT NULL,
  CONSTRAINT fk_employees_department FOREIGN KEY (department_id) REFERENCES departments (id),
  CONSTRAINT fk_employees_manager FOREIGN KEY (manager_id) REFERENCES employees (id)
);

CREATE TABLE support_tickets (
  id INT AUTO_INCREMENT PRIMARY KEY,
  customer_id INT NOT NULL,
  assignee_id INT NOT NULL,
  subject VARCHAR(120) NOT NULL,
  status ENUM('open', 'pending', 'solved') NOT NULL,
  opened_at DATETIME NOT NULL,
  CONSTRAINT fk_tickets_customer FOREIGN KEY (customer_id) REFERENCES customers (id),
  CONSTRAINT fk_tickets_assignee FOREIGN KEY (assignee_id) REFERENCES employees (id)
);

CREATE TABLE ticket_messages (
  id INT AUTO_INCREMENT PRIMARY KEY,
  ticket_id INT NOT NULL,
  author_type ENUM('customer', 'employee') NOT NULL,
  body VARCHAR(255) NOT NULL,
  sent_at DATETIME NOT NULL,
  CONSTRAINT fk_messages_ticket FOREIGN KEY (ticket_id) REFERENCES support_tickets (id)
);

CREATE TABLE newsletters (
  id INT AUTO_INCREMENT PRIMARY KEY,
  title VARCHAR(120) NOT NULL,
  sent_on DATE NOT NULL
);

CREATE TABLE newsletter_subscriptions (
  customer_id INT NOT NULL,
  newsletter_id INT NOT NULL,
  subscribed_at DATETIME NOT NULL,
  PRIMARY KEY (customer_id, newsletter_id),
  CONSTRAINT fk_subscriptions_customer FOREIGN KEY (customer_id) REFERENCES customers (id),
  CONSTRAINT fk_subscriptions_newsletter FOREIGN KEY (newsletter_id) REFERENCES newsletters (id)
);

CREATE TABLE audit_logs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  actor VARCHAR(80) NOT NULL,
  action VARCHAR(40) NOT NULL,
  entity VARCHAR(40) NOT NULL,
  entity_id INT NOT NULL,
  logged_at DATETIME NOT NULL
);
