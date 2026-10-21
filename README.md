# quality-console-light

> **Disclaimer**: this is a personal demo project, not a source of truth or a reference implementation. It reflects my own understanding and choices: its content remains subjective, despite the quotes and references it contains. It may be incomplete, simplified, inaccurate or outdated, and it is not meant for production use. Always check the official documentation before applying anything from it. Provided as is, without any warranty: you use it at your own risk.

A simulated company, **MyCompany**, and the tests that run it for real. Its storefront offers three products (a customer welcome, a checkout, an account access), backed by real services: an API, a MySQL company database, Redis, a third-party bank replayed by Microcks, an order workflow through RabbitMQ, a simulated Auth0 tenant and a QA mailbox. Each test starts its own throwaway containers with [testcontainers](https://testcontainers-python.readthedocs.io/); run by hand, every call shows up as a trace, and the **Quality Console** gathers the catalog, the test results and the QA tools.

> **TL;DR**
>
> - **See it without installing anything**: [the demo online](https://vincentbaticle.github.io/quality-console-light/), a static snapshot of the Quality Console (every page, the buttons that call an API need the live stack). Or open the repository in a GitHub Codespace for the live stack.
> - `mise install && mise run install` once, then `mise run test`.
> - Three demos, each a step-by-step script: [testcontainers](docs/demos/testcontainers.md) (tests against real neighbours), [observability](docs/demos/observability.md) (every API call as a trace), [Quality Console](docs/demos/quality-console.md) (catalog, databases, test results and the QA tools in one back office).
> - How each product is tested, and how to test a testcontainers test: [Testing with testcontainers](docs/testing-with-testcontainers.md), also in the console's **Documentation** tool.
> - One vocabulary: a software catalog as code, which every test's metadata must name: [The software catalog and the test metadata](docs/catalog-and-metadata.md).
> - The products: [The order workflow](docs/order-workflow.md), [Account access: a simulated Auth0 and the QA mailbox](docs/account-access.md).
> - The tools: [Gherkin scenarios run from the console](docs/gherkin.md) (each with its goal and its tool: pytest, Playwright on the storefront page, schemathesis on the Bank Partner, a k6 load baseline), [Recorded scenarios](docs/recorded-scenarios.md) (a journey clicked on the storefront, cleaned, written in a template, turned into a Playwright scenario), [the MCP server](docs/mcp.md) (DevX), [Vault](docs/vault.md) (DevX: short-lived credentials for the services, a long-lived key for the bank), [Scenario design](docs/scenario-design.md), [Recordings of real calls and events](docs/recordings.md), [retro-footprint](docs/retro-footprint.md) (DevX), [Audio asset generator](docs/audio-assets.md) (Utility tools), [API contracts](docs/api-contracts.md), [Test results in a bucket](docs/test-results.md).
> - A guide: [Leaving SonarQube (sonar-decom)](docs/sonar-decom.md), a quality gate on new code without a server.
> - Every service, its URL and its credentials: [Services and credentials](#services-and-credentials).
> - Docker (Rancher Desktop) must be running. Without it, integration tests skip and say why, they never fail.
> - Nothing to start by hand before the tests: no `docker compose up`, no shared environment, nothing left behind.

## Try it by hand in five minutes

1. Rancher Desktop running, then once: `mise trust && mise install && mise run install`.
2. `mise run up`: builds and starts everything, returns when it is ready (about a minute the first time).
3. `mise run results:seed`: fills the results bucket with four weeks of CI history (once; the bucket survives restarts).
4. Open:
    - the storefront: <http://localhost:8080>, three products, each opened alone from the product list (or straight from the console), with **← All products** and **← Quality Console** to come back. **Customer welcome**: try `ada`, `grace` or `zoe` (`dennis` is a closed customer, refused). **Checkout**: click **ada buys Foundation** (paid) or **grace buys an Ultrabook** (out of stock) and watch the steps run. **Account access**: sign in as `ada`, `grace` (blocked) or `zoe` (no password yet), or create an account;
    - the QA mailbox: <http://localhost:8025> (Mailpit), where every email of the account access lands;
    - the order queue: <http://localhost:15672> (RabbitMQ, `guest` / `guest`);
    - the Quality Console: <http://localhost:8081>, four zones: the **Static Cockpit QA** (catalog, test results, jobs, Gherkin scenarios, scenario design, recordings, API docs, bucket browser, databases, the sonar-decom guide), **Live experimentation** (the storefront products and the services beside them: real reads, writes and deletes in the dockerised tables, queue and mailbox) **DevX** (retro-footprint, Vault, the MCP server) and **Utility tools** (the audio asset generator, writing tracks into `audio-assets/`). Only the actions that call an API or a database wait behind a loader, every tool says in a blue box what its buttons do, and every tool, database, table, bucket and Gherkin product carries its label: `live`, `static`, `mixed` or `mock`;
    - the traces: `mise run traces` opens Grafana straight on the `hello-api` traces of the last 15 minutes (or the Observability card of the console). A call shows up 10 seconds to a minute after it is made: click the blue refresh button (top right) if yours is not listed yet.
5. In the console, **Tools**, **Gherkin scenarios**, click **Run** on a scenario: it runs against the stack and its run lands in **Test results**.
6. `mise run test:unit`, then **Refresh** on the test results page: your own run shows up under env `local`.
7. `mise run down` when done.

## The demo online

<https://vincentbaticle.github.io/quality-console-light/> is the Quality Console frozen into static pages, rebuilt on every push to `main` by `.github/workflows/pages.yml`: the runner starts the whole stack (`mise run up`), seeds four weeks of CI history (`mise run results:seed`), then `mise run demo:freeze` reads the console page by page (GET only, every GET of the console is a read) and writes it to `site/`, which GitHub Pages serves.

- Every page reads as it was at the build: catalog, test results and their runs, Gherkin scenarios, scenario designs, API docs, documentation, databases, DevX and utility pages.
- A banner on top says it is a snapshot. Anything that calls an API (**Run** a scenario, retro-footprint, the audio generator, searches) and the services beside the console (storefront, Grafana, mailbox, RabbitMQ, Vault) lead to a page explaining how to run the live stack.
- To keep it small, the snapshot keeps at most 40 pages of each kind (`PAGES_PER_SHAPE` of `src/quality_console/snapshot.py`), the newest runs first, and no search or paging.
- The live stack in the browser: **Code**, **Codespaces**, **Create codespace on main** (4 cores, 16 GB). `.devcontainer/devcontainer.json` installs mise, starts the stack and seeds it; the console opens on the forwarded port 8081.

### Publishing it, once

1. Push `main` to GitHub.
2. Make the repository public (**Settings**, **General**, **Danger Zone**, **Change visibility**): GitHub Pages on a private repository needs a paid plan.
3. **Settings**, **Pages**, **Build and deployment**, **Source**: pick **GitHub Actions**. Nothing else to fill in, no branch to pick.
4. **Actions**, **Demo on GitHub Pages**, **Run workflow** on `main` (or push a commit). The `freeze` job takes 10 to 15 minutes (it builds the images and starts the whole stack), then `deploy` publishes.
5. The address shows in the summary of the run and in **Settings**, **Pages**: `https://vincentbaticle.github.io/quality-console-light/`. Put it on the repository's home: the gear next to **About**, tick **Use your GitHub Pages website**.

After that, every push to `main` rebuilds the demo. **Run workflow** again now and then: the seeded history is dated from the day of the build, so a rerun keeps the dates recent.

| What you see | Why, and what to do |
| --- | --- |
| `deploy` fails on *Get Pages site failed* or *Not Found* | Step 3 is missing: the Pages source is not **GitHub Actions**. |
| `deploy` refused on the `github-pages` environment | The run is not on `main`: the environment only accepts the default branch. |
| `freeze` fails | Open the step **Stack logs on failure**: a service that did not start says why there. |
| The page is a 404 for a minute | Normal after a first deployment, GitHub needs a moment. |

Preview the snapshot on a laptop before pushing:

```
mise run up && mise run results:seed
mise run demo:freeze
python3 -m http.server -d site 8765    # then http://localhost:8765
```

## Services and credentials

| Service | URL | Login |
| --- | --- | --- |
| Storefront | <http://localhost:8080> | none (accounts of the page: `qa-mailbox+ada@mycompany.test` / `Foundation-2026`, see [Account access](docs/account-access.md)) |
| Quality Console | <http://localhost:8081> | none, read-only |
| QA mailbox (Mailpit) | <http://localhost:8025> | none |
| RabbitMQ management | <http://localhost:15672> | `guest` / `guest` |
| RabbitMQ AMQP | `localhost:5672` | `guest` / `guest`, vhost `/` |
| Grafana | <http://localhost:3000> | anonymous; `admin` / `admin` if a login page shows |
| MySQL | `localhost:3307` | `root` / `root` (everything), `console_reader` / `reader` (read-only) |
| Cloud Storage emulator | <http://localhost:4443> | none (`STORAGE_EMULATOR_HOST`) |
| Bank Partner (fake) | <http://localhost:8090/docs> | `X-Api-Key`, the long-lived key in Vault (`secret/bank-partner`) |
| Vault (dev mode) | <http://localhost:8200> | token `root`; the services get short-lived MySQL and RabbitMQ users from it, see [Vault](docs/vault.md) |
| Contract mocks (Prism) | <http://localhost:4010> | none; `/<name>/…` serves `contracts/<name>-openapi.yaml`, see [API contracts](docs/api-contracts.md) |
| Identity Management API | `POST /api/identity/management/tickets/password-change` | `Authorization: Bearer local-management-token` |

## The products

MyCompany is made up, its services are real. The storefront page shows three products, each a section with its purpose and the services behind it.

- **Customer welcome** (engage): a customer types a username, the page says `Hello Ada! You are visitor number 1. Your balance is 1250.75 EUR.`: the first name comes from the company database, the number grows on each visit, and the balance comes from a bank we do not own. An unknown or closed customer gets a `404`.
- **Checkout** (sell): the API answers `202 Accepted` at once and a worker processes the order in three steps (reserve the stock, issue the invoice, capture the payment), one RabbitMQ event per step, while the page follows it live (see [The order workflow](docs/order-workflow.md)).
- **Account access** (protect): sign-in, account creation and password reset through a simulated Auth0 tenant, every email landing in the QA mailbox (see [Account access](docs/account-access.md)).

Each card also says, under **What this card teaches a tester**, what its form really calls, what is recorded and how, which test proves it with which containers, and how to write such a test by hand or with a Claude Code skill. The cards produce traffic; recording it is the job of the capture commands (see [Recordings](docs/recordings.md)).

Where the code lives:

- `frontend/`: the storefront page served by nginx, which forwards `/api/identity/` to the identity service and `/api/` to the API.
- `src/hello_api/main.py`: the storefront API, `GET /api/hello?username=` and `GET /api/health`, counting visits in Redis.
- `src/hello_api/customers.py`: reads the first name of an active customer from the `customers` table.
- `src/hello_api/bank_partner.py`: the client of the **Bank Partner**, a third-party core banking API giving the balance of an account, in cents. A `404` from it means "no account for this username", and the greeting then says nothing about money.
- `src/hello_api/greeting.py`: the pure rules of the greeting (the sentence, the amount format, the Redis key name).
- `src/hello_api/orders.py` and `src/order_workflow/`: the order routes, and the workflow behind them (steps, broker, store, worker).
- `src/identity/`: the simulated Auth0 tenant (rules, users store, emails, routes).
- `partner/`: a fake Bank Partner, playing the third party a real product would depend on. It reads the `bank_accounts` table of the same database, the way services share a legacy database. The tests never call it, they call Microcks replaying what it answered (see "Recording what the partner answers").
- `db/`: the company database (30 tables, from 10 to 113 rows each), the console's read-only account, the workflow state store, the catalog and the identity users (see "The company database").
- `catalog/catalog.yaml` and `src/catalog/`: the software catalog as code, and its MySQL rendering (see [The software catalog](docs/catalog-and-metadata.md)).
- `contracts/`: every API contract, OpenAPI and AsyncAPI (see [API contracts](docs/api-contracts.md)).
- `features/`: the Gherkin scenarios, one folder per product (see [Gherkin scenarios](docs/gherkin.md)); `designs/`: the journeys they walk (see [Scenario design](docs/scenario-design.md)).
- `buckets/`: the files of the team buckets the bucket checks test, loaded into the storage emulator at start.
- `capture/`: the journals of the recordings, not committed (see [Recordings](docs/recordings.md)).
- `audio-assets/`: the tracks of the audio asset generator, the folder committed, the files not (see [Audio asset generator](docs/audio-assets.md)).
- `src/company_db/`: where the database is and how a service connects, shared by every service.
- `src/quality_console/`: the Quality Console, back office pages and tools (see "The Quality Console").
- `src/gherkin_runner/`: runs the scenarios on demand for the console.
- `src/test_results/`: the contract of the results bucket (where a run goes, what it holds), shared by the uploader, the indexer, the runner and the console.
- `scripts/`: the partner capture, the results upload, index and seed, the catalog and contracts export.
- `docker-compose.yml`: every piece, to try it all by hand with `mise run up`: the storefront on <http://localhost:8080>, the console on <http://localhost:8081>, the mailbox on <http://localhost:8025>, the traces on <http://localhost:3000>, the bucket on <http://localhost:4443>.
- `docs/`: the three demo scripts (`docs/demos/`) and one page per product or tool.

## The levels of tests

Each level answers a different question, and only the first one runs without Docker.

1. `tests/unit/`, marker `unit`: are the pure rules right (the greeting sentence, the identity rules, the results layout), do the contracts match the code, does every test name catalog entries? Pure Python, no I/O, milliseconds.
2. `tests/integration/test_hello_redis.py`, marker `integration`: does the API really count in Redis? The real app, in process, against a real Redis container.
3. `tests/integration/test_hello_customers_mysql.py`, marker `integration`: does the API read the right customer, and refuse a closed one? The real app against a real MySQL loaded with the 30 tables.
4. `tests/integration/test_hello_balance_microcks.py`, marker `integration`: does the API use what the partner answers, including its `404`? The real app and its real HTTP client, against Microcks replaying the partner from its contract and captured answers.
5. `tests/integration/test_identity_mailpit.py`, marker `integration`: does the tenant store lowercase emails, send the password emails, keep links single use, block at ten wrong passwords? The real service against a real MySQL and a real mailbox (Mailpit).
6. `tests/integration/test_orders_rabbitmq.py`, marker `integration`: is an order accepted at once, then paid (or cancelled) by the workflow, step by step? The real API and the worker's own handler, against a real RabbitMQ and a real MySQL.
7. `tests/integration/test_console_*.py` and `test_results_bucket_gcs.py`, marker `integration`: does the console show the databases read-only, the catalog, the results, every tool, and does a click on a scenario run it through the real runner and file the run? Against MySQL and a real Cloud Storage emulator.
8. `tests/integration/test_hello_page_browser.py`, marker `integration`: does a user see the greeting, an order followed until paid, a sign-in? A real Chromium on the real front, which calls the real APIs, which use MySQL, Redis, RabbitMQ (with the worker), Microcks and Mailpit. Every piece is a container.
9. `tests/acceptance/`, marker `acceptance`: does each product do what its Gherkin scenarios promise, and does every team bucket keep its file contract? Against the stack `mise run up` started, from `mise run test:acceptance` or the console (see [Gherkin scenarios](docs/gherkin.md)). They skip when the stack is down.
10. `perf/customer-welcome-baseline.js`, k6: does the greeting keep its service level with ten customers at once? `mise run test:perf` against the running stack, filed in Test results as a `performance` run; the same load runs as a Gherkin scenario.

The file name says which neighbour a test needs (`_redis`, `_mysql`, `_rabbitmq`, `_microcks`, `_gcs`, `_mailpit`, `_browser`), the marker says whether it needs one at all. Each module also declares who it belongs to with `metadata_test(...)`, values from the catalog, which ends up in the JUnit report and in the console's filters (see [The software catalog and the test metadata](docs/catalog-and-metadata.md)).

## How testcontainers works here

Everything lives in four files: `tests/neighbours.py` (constants, the Docker check), `tests/database.py` (loading `db/` into MySQL), `tests/microcks.py` (loading the partner into Microcks) and `tests/integration/conftest.py` (the fixtures).

1. A session fixture starts the container: `with RedisContainer("redis:7.4-alpine") as redis:`.
2. Docker maps the container port to a **random** free port on the host, so two runs never collide. The test asks for it: `redis.get_exposed_port(6379)`.
3. The fixture `yield`s the URL, the tests use it.
4. At the end of the session, leaving the `with` stops and deletes the container.

Redis uses a ready-made module (`RedisContainer`). MySQL deliberately does not: `DockerContainer("mysql:8.4").with_env(...).with_exposed_ports(3306)` is all a module does under the hood, and `tests/database.py` then waits for a login and runs the two scripts of `db/`.

For the full stack, the fixture builds the two images from the repository, creates a private network, and starts MySQL, Redis, Microcks, the API and the front on it. Inside that network they reach each other by alias (`mysql`, `redis`, `microcks`, `api`), as in `docker-compose.yml`. Only the front (for the browser), MySQL and Microcks (to load their data) are exposed to the host. Telemetry is off there (`OTEL_SDK_DISABLED=true`): no collector runs in a test.

## The company database

`db/01-schema.sql` creates 30 tables of a small retail and banking company (customers, addresses, bank accounts and transactions, products, stock, orders, invoices, payments, shipments, returns, promotions, reviews, employees, support tickets, newsletters, audit logs), with their foreign keys. `db/02-seed.sql` puts ten hand-written rows in each, the ones tests name (ada, grace, dennis...); `db/02b-volume.sql` then generates more rows in 23 of them, up to 113, so the tables look like a real company's rather than all alike (lookups such as currencies or carriers keep their 10).

The API reads one table (`customers`), the bank another (`bank_accounts`); the other 28 are there on purpose, so the database looks like the shared database of a real company rather than a fixture made to measure.

- Seen by hand: `mise run up` loads both scripts on the first start (they are mounted into the MySQL init directory). Connect with any client on `localhost:3307`, user `root`, password `root`, database `mycompany`, or `docker compose exec mysql mysql -uroot -proot mycompany`.
- Seen by the tests: the `database` fixture loads the same scripts into its own container, or into the CI sidecar. `test_company_database_is_loaded_in_full` checks the 30 tables and their rows.
- Changing the data: edit `db/02-seed.sql`, then `mise run down && mise run up` (a new container replays the scripts). A customer used by a test is named in `tests/story.py`.

## Seeing the API calls

In production, services send their traces, metrics and logs with OpenTelemetry (OTLP) to an observability platform such as Tsuga. Locally, `mise run up` starts a free all-in-one stand-in, [Grafana's `otel-lgtm`](https://github.com/grafana/docker-otel-lgtm) (an OpenTelemetry collector, Tempo for traces, Prometheus for metrics, Loki for logs, Grafana to look at them), in one container named `observability`.

Nothing in the code knows about it. Every service starts through `opentelemetry-instrument` (see the two `Dockerfile`s and the `console` command), which instruments FastAPI, httpx, Redis and PyMySQL automatically, and reads the standard `OTEL_*` variables of `docker-compose.yml`: OTLP over HTTP on port 4318, a `service.name` each (`hello-api`, `order-worker`, `identity-service`, `bank-partner`, `quality-console`). Pointing them at a real platform only changes the endpoint.

To see a call:

1. `mise run up`: it returns once every service is up (about a minute the first time, to build the images and load the database).
2. Make some calls: use the page on <http://localhost:8080>, or `mise run traffic` (ada, grace, zoe, a closed customer, an unknown one).
3. Open Grafana on <http://localhost:3000> (no account needed: the stack opens Grafana to anonymous visitors and hides its login form; a login page anyway means an old cookie of another app on `localhost:3000`, so use a private window, or `admin` / `admin`).
4. **Explore** (left menu), pick the **Tempo** data source, query type **Search**, Service Name `hello-api`, **Run query**. Traces become searchable 10 seconds to a minute after the call.
5. Click a trace: one line per span, with its duration. A greeting of ada reads `GET /api/hello`, then `SELECT` (the customer in MySQL), then `GET` (the call to the bank), which continues in `bank-partner` with its own `GET /balance` and `SELECT`, then `INCRBY` (the visit in Redis). Open a span to see its attributes: the SQL statement, the URL, the status code.
6. A `404` (dennis, nobody) stops after the `SELECT`: no bank call, no visit counted.

Why it matters, and a full walk through a healthy call, a refusal and an incident: [observability demo](docs/demos/observability.md).

Metrics (request counts and durations per route) are in **Explore > Prometheus**, for example `http_server_duration_milliseconds_count`. Logs are not exported (`OTEL_LOGS_EXPORTER=none`): the access log stays on `docker compose logs api`.

<details>
<summary>Switching telemetry off, or using another backend</summary>

- `OTEL_SDK_DISABLED=true` turns the SDK into a no-op while keeping the `opentelemetry-instrument` entrypoint; the full-stack test does exactly that.
- SigNoz is a heavier open-source alternative with an APM-style UI closer to a commercial platform. It listens on the same OTLP port: start it from its own `docker compose`, then point `OTEL_EXPORTER_OTLP_ENDPOINT` at it. Mind its UI port, 8080 like our front.

</details>

## The Quality Console

`mise run up` also starts the back office of the quality platform on <http://localhost:8081>. Four zones, and a **Documentation** tool that gathers every page of `docs/` (each tool links to its own page, top right, and keeps its blue box for the page itself):

- **Static Cockpit QA**: the pages below, the QA cockpit of a real company. Each tool carries its own label: `static` (loaded once: catalog, designs, recordings, API docs, release announcements, the sonar-decom guide), `live` (grows as the stack is used: test results, jobs) or `mixed` (Gherkin scenarios, buckets, databases). **Release announcements** shows the Slack drafts of the team skill `/announce-release`, one short message per system from the changelogs of its components, and where its next run starts ([Release announcements](docs/release-announcements.md)).
- **Live experimentation**: the storefront products (each opens alone on the storefront) and the services beside the console. They read, write and delete for real in the dockerised tables, queue and mailbox.
- **DevX** (top menu): **Tips**, one tab per topic (GitLab, Git, SQL, Docker, QA, front design: a snow button, an SVG bullet hole, also as a static image on a transparent background, an entry card with its orange **Beta** ribbon), **retro-footprint**, which plays a test (pages of a front, API calls, SQL of its own) five times, pauses 20 seconds, five times again, for real, draws its path of fronts, APIs and tables and checks it against the trace in Tempo ([retro-footprint](docs/retro-footprint.md)), **Vault** ([Vault](docs/vault.md)) and **Quality Console MCP**, the page of the MCP server that lets Claude Code run scenarios, read test runs, measure a footprint and check a recorded scenario on the local stack ([the MCP server](docs/mcp.md)).
- **Utility tools** (top menu): the **Audio asset generator**, a form (duration, WAV or FLAC, bit depth, rate, channels, number of files) writing placeholder tracks into `audio-assets/` of the repository, a folder committed empty, its files never; the page plays, downloads and deletes them ([Audio asset generator](docs/audio-assets.md)).

Every table is tagged (and every bucket: `test-results` live, the team buckets static; every Gherkin product: the storefront ones live, `partner-contracts`, `bucket-checks` and `quality-console` static): `live` when the storefront writes it (`orders`, `order_items`, `stock_levels`, `invoices`, `payments`, `audit_logs`, the `orchestrator` and `identity` databases), `static` otherwise (`src/quality_console/table_kinds.py`). Only the buttons and links that call an API or a database show a loader (`data-loading`); moving between pages does not.

| Page | What it answers |
| --- | --- |
| **Catalog** | What does the company run, who owns it, which APIs and databases, how is it tested? ([The software catalog](docs/catalog-and-metadata.md)) |
| **Test results**, **Jobs** | What did CI say, since when does a job fail? ([Test results in a bucket](docs/test-results.md)) |
| **Tools**, Gherkin scenarios | Does each product keep its promises? One click runs a scenario on the stack. ([Gherkin scenarios](docs/gherkin.md)) |
| **Tools**, Leaving SonarQube (sonar-decom) | How to keep a quality gate on new code once SonarQube is switched off: which analyser per language, the diff scope, two gates, the rules learnt on real merge requests. ([Leaving SonarQube](docs/sonar-decom.md)) |
| **Tools**, API docs | What does each API accept and answer, which events does the order workflow send? ([API contracts](docs/api-contracts.md)) |
| **Tools**, Bucket browser | What is in the buckets, folder by folder, file by file? |
| **Databases** | What does the data say: every database the account reads, every table, a search on one column. |

The home and **Tools** pages also link the services running beside the console: the QA mailbox, Grafana and RabbitMQ.

- It reads as `console_reader`, an account with `SELECT` only (`db/03-console-reader.sql`): MySQL itself refuses any write. It may also read the table counters of `performance_schema`, for retro-footprint. For the identity users it is granted two views only, without password hashes nor link secrets.
- Table and column names are checked against what MySQL lists before they reach a statement; values are bound. A crafted name gets a `404`. An HTML report or a bucket file is served sandboxed.
- Code in `src/quality_console/`, tests in `tests/integration/test_console_*.py` (the `console` fixture wires every tool for real), traces under `quality-console`.

Walkthrough: [Quality Console demo](docs/demos/quality-console.md).

## Recording what the partner answers

A hand-written example of what a third party answers is a guess. Here, the examples Microcks replays are **recorded** from the partner, then reviewed in a diff like any code.

1. **The contract**: `contracts/bank-partner-openapi.yaml`, a copy of what the partner publishes. Microcks reads it as the primary artifact.
2. **The capture**: `mise run partner:up` starts the partner and its database on <http://localhost:8090>, then `mise run capture:examples` asks it about every username of `tests/story.py` and writes each request and answer to `capture/journal.json`. The journal is a transcript, it is not committed.
3. **The merge**: `mise run capture:merge` rewrites the captured examples of `contracts/bank-partner-examples.yaml` (the secondary artifact) from the journal. It touches nothing else: the `404` example `unknown-account` (zoe, a customer without an account) is written by hand, because a capture only records the success stories, and the merge never overwrites it.
4. **The review**: `git diff contracts/`. If the bank now answers another balance, update `ADA_BALANCE_CENTS` and `ADA_BALANCE_TEXT` in `tests/story.py` in the same commit: it is data the bank owns, not a value a test picks.
5. **The replay**: in the tests, Microcks loads both files and answers the API's real HTTP calls with the example whose `username` matches. The partner itself is never called by a test.

Adding a captured username: add it to `CAPTURED_USERNAMES` in `tests/story.py`, then capture and merge again. Adding an error case: write the example by hand in the examples file, with the same example name on the parameter and on the response.

<details>
<summary>Why no mock</summary>

A mocked Redis answers what the author of the test expected, so it can never catch the author's mistake. A real Redis started in two seconds says what Redis really does. Unit tests stay, but only for pure rules like `build_greeting`.

</details>

<details>
<summary>What happens in CI</summary>

GitLab runners have no Docker daemon, so testcontainers cannot start anything there. The `integration-tests` job declares MySQL, Redis, RabbitMQ, Microcks, Mailpit and the Cloud Storage emulator as sidecars (`services:`) and sets `INTEGRATION_EXTERNAL_SERVICES=true`. The `database`, `redis_url`, `microcks_url`, `mail_server` and the other fixtures then attach to the sidecars instead of starting containers, and load the database and the partner into them the same way: same tests, other provisioning.

The browser test needs to build and start images, which a sidecar cannot do, so it skips in CI with that reason. It runs on every laptop.

The `sonarqube` job is a mock (`gitlab-ci/mocks.yml`): it checks that both coverage reports exist and prints what it would send, without calling any SonarQube server. The same goes for `.prek:run`, a local stand-in for the shared pre-commit block. How to replace it for real, with a gate on new code and no server: [Leaving SonarQube](docs/sonar-decom.md).

The acceptance scenarios do not run in CI: they need the assembled stack, which a sidecar cannot build.

</details>

<details>
<summary>Troubleshooting</summary>

- `Docker unavailable` in the skip reason: start Rancher Desktop. `.mise.toml` points `DOCKER_HOST` at `~/.rd/docker.sock` and disables Ryuk, which Rancher Desktop does not support.
- The integration tasks set `DOCKER_CONFIG=.docker`, an empty config of this repo: the images are public, and without it the Docker SDK would call every credential helper of your own `~/.docker/config.json` (gcloud included) before each build. Run the tests through `mise run`, not a bare `pytest`, to keep it.
- Microcks and MySQL take ten to fifteen seconds each to boot, once per session: that is most of the integration run.
- Running the integration tests while `mise run up` runs too needs memory: give Docker 8 GB (and switch off the Kubernetes of Rancher Desktop if unused), or `mise run down` first. Under pressure containers start too slowly and the browser test times out.
- Port already in use on `mise run up` (3000, 3307, 4318, 4443, 8025, 8080, 8081, 8090, 15672): stop what listens there, or change the left side of the port in `docker-compose.yml`.
- See the browser: `mise run test:headed`.

</details>

## Daily commands

- `mise run test:unit`, `mise run test:integration`, `mise run test` for both. Extra pytest arguments go after `--`, for example `mise run test:integration -- -k redis`.
- `mise run test:acceptance`: the Gherkin scenarios against the running stack (`mise run up` first).
- `mise run catalog:sql` after editing `catalog/catalog.yaml`, `mise run contracts:export` after changing a route.
- `mise run capture:events` then `mise run capture:events-merge`: record the events of the order workflow again (needs `mise run up`).
- `mise run results:seed`, `mise run results:index`: fill the local results bucket with made-up history, rebuild its index now.
- `mise run hooks:run`: pre-commit hooks on the whole tree (ruff, ruff format, mypy, YAML/TOML checks). Commit messages follow conventional commits.
- `mise run release:check`, then `mise run release`: tags `main` with the next version, which cocogitto picks from the commit types since the last tag (`fix` patch, `feat` minor, a breaking change major; a `chore`, `docs`, `refactor` or `test` commit alone gives no tag). Git tags only, no version in `pyproject.toml`, no changelog.

## Adding an API endpoint and its tests

Worked example: `GET /api/visits?username=ada` says how many times ada was greeted, without counting a new visit. Four steps, about twenty lines, no fixture and no CI to touch, because Redis is already provisioned.

**Which test do I write?**

- A rule you can check with only Python values (a format, a computation, a key name): a unit test.
- Anything an HTTP call can show (status code, body, what lands in Redis): an API test. This is the default for a new endpoint.
- A user journey through the page: a browser test, only when the front changes. It builds the images, so keep these few.

**1. The response model**, next to the others in `src/hello_api/main.py`:

```python
class Visits(BaseModel):
    """Body of a visit count."""

    visits: int
```

**2. The route**, inside `create_app`, below `hello`. Reuse `Username` for the same validation, and `visits_key` so both routes read the same Redis key:

```python
    @app.get("/api/visits")
    def visits(username: Username) -> Visits:
        """Say how many times a username was greeted, without counting a visit."""
        return Visits(visits=int(redis.get(visits_key(username)) or 0))
```

**3. A pure rule, if any**, goes in `src/hello_api/greeting.py` with its unit test in `tests/unit/test_greeting.py`. This endpoint has none: `visits_key` is already tested.

**4. The API test**, in a new file `tests/integration/test_visits_redis.py`. The `api` fixture is the real app wired to the real Redis, `redis_client` reads Redis directly, and Redis is emptied before each test:

```python
"""Visit count against a real Redis: reading must not count a visit."""

from fastapi.testclient import TestClient
import pytest
from redis import Redis

pytestmark = pytest.mark.integration


def test_unknown_username_has_no_visit(api: TestClient) -> None:
    response = api.get("/api/visits", params={"username": "ada"})

    assert response.status_code == 200
    assert response.json() == {"visits": 0}


def test_reading_does_not_count_a_visit(api: TestClient, redis_client: Redis) -> None:
    api.get("/api/hello", params={"username": "ada"})

    api.get("/api/visits", params={"username": "ada"})
    response = api.get("/api/visits", params={"username": "ada"})

    assert response.json() == {"visits": 1}
    assert redis_client.get("visits:ada") == "1"
```

**Check it:** `mise run test:integration -- -k visits`, then `mise run test` and `mise run hooks:run`.

<details>
<summary>When the endpoint needs a new neighbour (Postgres, RabbitMQ, ...)</summary>

That is the only case where fixtures and CI change, in four places:

1. `tests/neighbours.py`: the image and its internal port, as documented constants.
2. `tests/integration/conftest.py`: a session fixture, a copy of `redis_url`. It calls `require_docker()`, starts the container with `with`, yields connection data built from `get_container_host_ip()` and `get_exposed_port()`, and in CI (`uses_external_services()`) attaches to the sidecar instead.
3. `pyproject.toml`: the testcontainers extra in the `dev` group, for example `testcontainers[postgres]`, then `pdm install`.
4. `gitlab-ci/tests_stage.yml`: the sidecar under `services:` of `integration-tests`, and its host variable.

The test file is then named after it, for example `test_orders_postgres.py`.

</details>

<details>
<summary>When the endpoint calls another partner API</summary>

No new container: Microcks plays every partner. Add the partner's contract and an examples file under `contracts/`, upload them in `tests/microcks.py` beside the Bank Partner, give its client a `*_URL` built from `MOCK_PATH` the same way, and record its examples with a capture like `scripts/capture_partner.py`. The test file is named `test_<feature>_microcks.py`.

</details>

<details>
<summary>When the front changes too</summary>

Edit `frontend/index.html` and `frontend/app.js`, then add a test to `tests/integration/test_hello_page_browser.py` or a new `test_<feature>_browser.py` using the `stack_url` and `page` fixtures. Find elements by role or label (`page.get_by_role("button", name="...")`) and assert with `expect(...)`, never with a sleep. `mise run test:headed` shows it running.

</details>

With Claude Code, `/new-api-test` follows these same steps; the conventions it reads are in `CLAUDE.md`.

## License

[MIT](LICENSE), provided as is, without any warranty.
