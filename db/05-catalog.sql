DROP DATABASE IF EXISTS catalog;
CREATE DATABASE catalog;

CREATE TABLE catalog.domains (
  name VARCHAR(60) PRIMARY KEY,
  title VARCHAR(120) NOT NULL,
  description VARCHAR(255) NOT NULL
);

CREATE TABLE catalog.business_capabilities (
  name VARCHAR(60) PRIMARY KEY,
  title VARCHAR(120) NOT NULL,
  description VARCHAR(255) NOT NULL
);

CREATE TABLE catalog.teams (
  name VARCHAR(60) PRIMARY KEY,
  title VARCHAR(120) NOT NULL,
  description VARCHAR(255) NOT NULL,
  jira_project VARCHAR(20) NOT NULL
);

CREATE TABLE catalog.systems (
  name VARCHAR(60) PRIMARY KEY,
  title VARCHAR(120) NOT NULL,
  domain VARCHAR(60) NOT NULL,
  owner VARCHAR(60) NOT NULL,
  description VARCHAR(255) NOT NULL,
  CONSTRAINT fk_systems_domain
    FOREIGN KEY (domain) REFERENCES catalog.domains (name),
  CONSTRAINT fk_systems_owner
    FOREIGN KEY (owner) REFERENCES catalog.teams (name)
);

CREATE TABLE catalog.products (
  name VARCHAR(60) PRIMARY KEY,
  title VARCHAR(120) NOT NULL,
  system_name VARCHAR(60) NOT NULL,
  capability VARCHAR(60) NOT NULL,
  description VARCHAR(255) NOT NULL,
  CONSTRAINT fk_products_system
    FOREIGN KEY (system_name) REFERENCES catalog.systems (name),
  CONSTRAINT fk_products_capability
    FOREIGN KEY (capability) REFERENCES catalog.business_capabilities (name)
);

CREATE TABLE catalog.components (
  name VARCHAR(60) PRIMARY KEY,
  title VARCHAR(120) NOT NULL,
  type VARCHAR(30) NOT NULL,
  lifecycle VARCHAR(30) NOT NULL,
  system_name VARCHAR(60) NOT NULL,
  owner VARCHAR(60) NOT NULL,
  source VARCHAR(120) NOT NULL,
  description VARCHAR(255) NOT NULL,
  CONSTRAINT fk_components_system
    FOREIGN KEY (system_name) REFERENCES catalog.systems (name),
  CONSTRAINT fk_components_owner
    FOREIGN KEY (owner) REFERENCES catalog.teams (name)
);

CREATE TABLE catalog.apis (
  name VARCHAR(60) PRIMARY KEY,
  title VARCHAR(120) NOT NULL,
  type VARCHAR(30) NOT NULL,
  system_name VARCHAR(60) NOT NULL,
  owner VARCHAR(60) NOT NULL,
  definition VARCHAR(120) NOT NULL,
  description VARCHAR(255) NOT NULL,
  CONSTRAINT fk_apis_system
    FOREIGN KEY (system_name) REFERENCES catalog.systems (name),
  CONSTRAINT fk_apis_owner
    FOREIGN KEY (owner) REFERENCES catalog.teams (name)
);

CREATE TABLE catalog.resources (
  name VARCHAR(60) PRIMARY KEY,
  title VARCHAR(120) NOT NULL,
  type VARCHAR(30) NOT NULL,
  system_name VARCHAR(60) NOT NULL,
  owner VARCHAR(60) NOT NULL,
  database_name VARCHAR(60) NOT NULL,
  description VARCHAR(255) NOT NULL,
  CONSTRAINT fk_resources_system
    FOREIGN KEY (system_name) REFERENCES catalog.systems (name),
  CONSTRAINT fk_resources_owner
    FOREIGN KEY (owner) REFERENCES catalog.teams (name)
);

CREATE TABLE catalog.component_apis (
  component VARCHAR(60) NOT NULL,
  api VARCHAR(60) NOT NULL,
  relation ENUM('provides', 'consumes', 'publishes', 'subscribes')
    NOT NULL,
  PRIMARY KEY (component, api, relation),
  CONSTRAINT fk_component_apis_component
    FOREIGN KEY (component) REFERENCES catalog.components (name),
  CONSTRAINT fk_component_apis_api
    FOREIGN KEY (api) REFERENCES catalog.apis (name)
);

CREATE TABLE catalog.component_resources (
  component VARCHAR(60) NOT NULL,
  resource VARCHAR(60) NOT NULL,
  PRIMARY KEY (component, resource),
  CONSTRAINT fk_component_resources_component
    FOREIGN KEY (component) REFERENCES catalog.components (name),
  CONSTRAINT fk_component_resources_resource
    FOREIGN KEY (resource) REFERENCES catalog.resources (name)
);

INSERT INTO catalog.domains (name, title, description) VALUES
  ('retail', 'Retail', 'Everything a customer touches, from the welcome page to the paid order.'),
  ('identity', 'Identity', 'Who a customer is, how they sign in, and the emails that come with it.'),
  ('banking', 'Banking', 'Money held for the customers by a partner bank the company does not own.'),
  ('engineering', 'Engineering productivity', 'The tools the teams use to build, test and watch the product.');

INSERT INTO catalog.business_capabilities (name, title, description) VALUES
  ('engage', 'Engage', 'Recognise a customer and make them come back.'),
  ('sell', 'Sell', 'Turn a basket into a paid order.'),
  ('protect', 'Protect', 'Keep accounts and data safe.'),
  ('operate', 'Operate', 'Run, observe and test the platform.');

INSERT INTO catalog.teams (name, title, description, jira_project) VALUES
  ('storefront-squad', 'Storefront squad', 'Builds the storefront and the customer welcome.', 'STORE'),
  ('checkout-squad', 'Checkout squad', 'Owns orders, stock, invoices and payments.', 'CHK'),
  ('identity-squad', 'Identity squad', 'Owns sign-in, accounts and the identity emails.', 'IDN'),
  ('partners-squad', 'Partners squad', 'Owns the integrations with third parties, the bank first.', 'PTN'),
  ('data-squad', 'Data squad', 'Owns the files the company exchanges through buckets.', 'DATA'),
  ('qa-core', 'QA core', 'Owns the quality platform, its console and its test tooling.', 'QAC'),
  ('qa-web', 'QA web', 'Owns the end-to-end and acceptance tests of the storefront.', 'QWEB');

INSERT INTO catalog.systems (name, title, domain, owner, description) VALUES
  ('storefront', 'Storefront', 'retail', 'storefront-squad', 'The customer-facing web application and the API behind it.'),
  ('orders', 'Orders', 'retail', 'checkout-squad', 'The event-driven workflow that takes an order from placed to paid.'),
  ('identity', 'Identity', 'identity', 'identity-squad', 'A simulated Auth0 tenant, its users and the emails it sends.'),
  ('bank', 'Bank', 'banking', 'partners-squad', 'The partner bank and our client of its core banking API.'),
  ('data-exchange', 'Data exchange', 'engineering', 'data-squad', 'The files teams drop in buckets for finance and partners, and their contracts.'),
  ('quality', 'Quality platform', 'engineering', 'qa-core', 'The Quality Console, the test results bucket and the test tooling.');

INSERT INTO catalog.products (name, title, system_name, capability, description) VALUES
  ('customer-welcome', 'Customer welcome', 'storefront', 'engage', 'Greets a returning customer by first name, counts the visits and shows the bank balance.'),
  ('checkout', 'Checkout', 'orders', 'sell', 'Places an order and follows it while stock is reserved, the invoice issued and the payment captured.'),
  ('account-access', 'Account access', 'identity', 'protect', 'Creates an account, signs in, resets a password, with every email landing in the QA mailbox.'),
  ('partner-contracts', 'Partner contracts', 'bank', 'engage', 'Checks that a third party still answers what the contract we copied promises, with requests generated from that contract.'),
  ('bucket-checks', 'Bucket checks', 'data-exchange', 'operate', 'The same generic checks on every team bucket, each bucket bringing its own contract (names, format, freshness, manifest).'),
  ('quality-console', 'Quality Console', 'quality', 'operate', 'The back office of the quality platform, its tools and the company data, read-only.'),
  ('test-results', 'Test results', 'quality', 'operate', 'Every CI test run, uploaded to a bucket, indexed and shown with its trends.');

INSERT INTO catalog.components (name, title, type, lifecycle, system_name, owner, source, description) VALUES
  ('front', 'Storefront web', 'website', 'production', 'storefront', 'storefront-squad', 'frontend/', 'The static page customers use, served by nginx.'),
  ('hello-api', 'Storefront API', 'service', 'production', 'storefront', 'storefront-squad', 'src/hello_api/', 'Greets customers, counts visits and places orders.'),
  ('order-worker', 'Order worker', 'worker', 'production', 'orders', 'checkout-squad', 'src/order_workflow/', 'Runs the order workflow one step per event.'),
  ('identity-service', 'Identity service', 'service', 'experimental', 'identity', 'identity-squad', 'src/identity/', 'A simulated Auth0, sign-up, sign-in, password reset and management tickets.'),
  ('bank-partner', 'Bank Partner', 'external', 'production', 'bank', 'partners-squad', 'partner/', 'The third-party core banking API, played locally by a fake and in tests by Microcks.'),
  ('finance-export-job', 'Finance export job', 'worker', 'production', 'data-exchange', 'data-squad', 'buckets/finance-exports/', 'Drops the invoices of the day as a CSV file, simulated by the files of buckets/.'),
  ('catalog-feed-job', 'Catalog feed job', 'worker', 'production', 'data-exchange', 'data-squad', 'buckets/catalog-feeds/', 'Publishes the product and stock feeds as JSON with a manifest, simulated by the files of buckets/.'),
  ('bucket-checks', 'Bucket checks', 'test-suite', 'experimental', 'quality', 'qa-core', 'features/bucket-checks/', 'Generic Gherkin checks run on every team bucket, one row of examples per bucket.'),
  ('quality-console', 'Quality Console', 'website', 'production', 'quality', 'qa-core', 'src/quality_console/', 'Back office pages and tools of the quality platform.'),
  ('test-results-uploader', 'Test results uploader', 'library', 'production', 'quality', 'qa-core', 'src/test_results/', 'Uploads a run to the results bucket and indexes it.'),
  ('gherkin-runner', 'Gherkin runner', 'service', 'experimental', 'quality', 'qa-web', 'src/gherkin_runner/', 'Runs the acceptance scenarios on demand against the running stack.');

INSERT INTO catalog.apis (name, title, type, system_name, owner, definition, description) VALUES
  ('storefront-api', 'Storefront API', 'openapi', 'storefront', 'storefront-squad', 'contracts/storefront-openapi.yaml', 'Greeting, products and orders, generated by FastAPI.'),
  ('bank-partner-api', 'Bank Partner API', 'openapi', 'bank', 'partners-squad', 'contracts/bank-partner-openapi.yaml', 'The balance of an account, as the partner publishes it.'),
  ('order-workflow-events', 'Order workflow events', 'asyncapi', 'orders', 'checkout-squad', 'contracts/order-workflow-asyncapi.yaml', 'The thin events that drive an order from one step to the next.'),
  ('identity-api', 'Identity API', 'openapi', 'identity', 'identity-squad', 'contracts/identity-openapi.yaml', 'Sign-up, sign-in, password reset and management tickets.'),
  ('gherkin-runner-api', 'Gherkin runner API', 'openapi', 'quality', 'qa-web', 'contracts/gherkin-runner-openapi.yaml', 'Runs a feature or a scenario and reports its verdict.');

INSERT INTO catalog.resources (name, title, type, system_name, owner, database_name, description) VALUES
  ('mycompany-db', 'Company database', 'database', 'storefront', 'storefront-squad', 'mycompany', 'The shared MySQL database, 30 tables of a retail and banking company.'),
  ('orchestrator-db', 'Workflow state store', 'database', 'orders', 'checkout-squad', 'orchestrator', 'The workflows and their steps.'),
  ('identity-db', 'Identity users', 'database', 'identity', 'identity-squad', 'identity', 'The users of the simulated tenant and their password tickets.'),
  ('catalog-db', 'Software catalog', 'database', 'quality', 'qa-core', 'catalog', 'This catalog, loaded into MySQL for the tools to read.'),
  ('visits-cache', 'Visit counters', 'cache', 'storefront', 'storefront-squad', '', 'Redis keys counting the visits of each customer.'),
  ('order-workflow-queue', 'Order workflow queue', 'queue', 'orders', 'checkout-squad', '', 'The RabbitMQ queue every step event goes through.'),
  ('results-bucket', 'Test results bucket', 'bucket', 'quality', 'qa-core', '', 'The Cloud Storage bucket CI uploads its reports to.'),
  ('qa-mailbox', 'QA mailbox', 'mailbox', 'identity', 'qa-web', '', 'The mailbox every test account writes to, one plus tag per account.'),
  ('finance-exports-bucket', 'Finance exports', 'bucket', 'data-exchange', 'data-squad', '', 'gs://finance-exports, one CSV of invoices per day under daily/, and a manifest.'),
  ('catalog-feeds-bucket', 'Catalog feeds', 'bucket', 'data-exchange', 'data-squad', '', 'gs://catalog-feeds, the JSON feeds of products and stock under feeds/, and a manifest.');

INSERT INTO catalog.component_apis (component, api, relation) VALUES
  ('front', 'storefront-api', 'consumes'),
  ('front', 'identity-api', 'consumes'),
  ('hello-api', 'storefront-api', 'provides'),
  ('hello-api', 'bank-partner-api', 'consumes'),
  ('hello-api', 'order-workflow-events', 'publishes'),
  ('order-worker', 'order-workflow-events', 'publishes'),
  ('order-worker', 'order-workflow-events', 'subscribes'),
  ('identity-service', 'identity-api', 'provides'),
  ('bank-partner', 'bank-partner-api', 'provides'),
  ('quality-console', 'gherkin-runner-api', 'consumes'),
  ('gherkin-runner', 'gherkin-runner-api', 'provides');

INSERT INTO catalog.component_resources (component, resource) VALUES
  ('hello-api', 'mycompany-db'),
  ('hello-api', 'orchestrator-db'),
  ('hello-api', 'visits-cache'),
  ('hello-api', 'order-workflow-queue'),
  ('order-worker', 'mycompany-db'),
  ('order-worker', 'orchestrator-db'),
  ('order-worker', 'order-workflow-queue'),
  ('identity-service', 'identity-db'),
  ('identity-service', 'qa-mailbox'),
  ('finance-export-job', 'finance-exports-bucket'),
  ('catalog-feed-job', 'catalog-feeds-bucket'),
  ('bucket-checks', 'finance-exports-bucket'),
  ('bucket-checks', 'catalog-feeds-bucket'),
  ('quality-console', 'catalog-db'),
  ('quality-console', 'mycompany-db'),
  ('quality-console', 'orchestrator-db'),
  ('quality-console', 'identity-db'),
  ('quality-console', 'results-bucket'),
  ('test-results-uploader', 'results-bucket'),
  ('gherkin-runner', 'results-bucket');

GRANT SELECT, SHOW VIEW ON catalog.* TO 'console_reader'@'%';
