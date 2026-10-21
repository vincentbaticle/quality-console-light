# Quality Console demo: the quality platform in one place

> **Disclaimer**: this is a personal demo project, not a source of truth or a reference implementation. It reflects my own understanding and choices: its content remains subjective, despite the quotes and references it contains. It may be incomplete, simplified, inaccurate or outdated, and it is not meant for production use. Always check the official documentation before applying anything from it. Provided as is, without any warranty: you use it at your own risk.

Step-by-step script to show the back office of the project, the **Quality Console**: the software catalog of the company, its databases read-only, the CI test results, and the tools of the QA team (Gherkin scenarios run with a click, API docs, a bucket browser), each wired to real services. Same product as the [testcontainers demo](testcontainers.md). About 25 minutes, or pick sections.

> **TL;DR**
>
> - `mise run up`, `mise run results:seed`, then <http://localhost:8081>: the quality tools, then the services running beside the console (storefront, QA mailbox, Grafana, RabbitMQ, the Bank Partner).
> - The databases are read-only: the console's MySQL account has `SELECT` only. Only retro-footprint (real calls to the storefront), the Run buttons (the scenarios) and the audio asset generator (files in `audio-assets/`) change anything.
> - Each tool reads the catalog (`catalog/catalog.yaml`, loaded into MySQL): one vocabulary for tests, teams, scenarios and APIs.
> - Tested like the API, against a real MySQL, a real bucket emulator and a real Gherkin runner; traced like the API (`quality-console` in Grafana).

## What it is for

Real companies grow a back office next to their product: a place where support, QA or a product owner checks what the database says, what CI said last night, which bugs are late, without asking a developer and without write access. This console is the smallest version of it, built around one idea: every tool speaks the names of the software catalog.

## How the project is wired

- Code: `src/quality_console/` (`main.py` assembles, `databases.py` and `database_pages.py` the database browser, `results.py` the test results, `catalog_pages.py` the catalog, `tools/` one module per tool, `templates/` renders). It reads the catalog through `src/catalog/`, the results through `src/test_results/`.
- Services: `console` in `docker-compose.yml` (port 8081, read-only account, `contracts/`, `features/` and `.claude/skills/` mounted read-only) and `runner`, the Gherkin runner the Run buttons call. The console mounts `audio-assets/` read-write; the runner carries Chromium and k6 and is published on port 8082 for the MCP server.
- Tests: the `console` fixture drives it in process with every tool wired for real (`tests/integration/test_console_*`).

## Before the talk

1. Install and pre-pull as in the [testcontainers demo](testcontainers.md#before-the-talk).
2. `mise run up` once to build the images, then `mise run results:seed` to fill the bucket (it stays filled across restarts), then `mise run down`.

## On stage

### 1. The home page

`mise run up`, then open <http://localhost:8081>. Four zones, each with its own purpose: the **Static Cockpit QA** (pages of the console reading static data, as a real company's QA cockpit would), **Live experimentation** (the storefront products, each opening alone on the storefront in this tab with a way back, to produce real calls, events and emails, and the services running beside the console: mailbox, Grafana, RabbitMQ with its `guest` / `guest`, each in a new tab) **DevX** (retro-footprint, Vault, the MCP server) and **Utility tools** (the audio asset generator). Every tool opens with a blue box saying what its buttons do; only the actions calling an API or a database wait behind a loader, as they would against a remote stack.

### 2. The software catalog

**Catalog** (top menu): the five systems of the company by domain, each with its owner, its products, its components (type, lifecycle, owner, the APIs they provide or call, the resources they depend on) and its APIs and resources. Point at three links: a database opens in the database browser, an API opens its contract, **runs** opens the test results of that component. The teams table at the bottom links each team to its test runs. Message to pass: the catalog is the vocabulary every tool shares, see [The software catalog and the test metadata](../catalog-and-metadata.md).

### 3. Gherkin scenarios, run with a click

**Tools**, **Gherkin scenarios**: one section per product, titled and described by the catalog, each feature with its scenarios. Click **Run** on "A blocked customer is told to check their email": a second later the banner says `PASSED`, the pytest output folds under it, and **open the run** jumps to the run filed in Test results. Click **Run feature** on "Account emails reach the QA mailbox", then open the QA mailbox (<http://localhost:8025>): the welcome, reset and blocked emails of the scenarios' own accounts. Then **Run** on "A customer orders and watches the order until paid" (badge `playwright`): a real Chromium in the runner fills the checkout form of the storefront and waits for the three steps; its Given lines say who plays and from which data, the template of a recorded scenario ([Recorded scenarios](../recorded-scenarios.md)). See [Gherkin scenarios](../gherkin.md).

### 4. Leaving SonarQube

**Tools**, **Leaving SonarQube (sonar-decom)**: a guide rather than a dashboard. Read the TL;DR aloud: a linter replaces no quality gate because it knows nothing of the merge request, so what is built is the scope (the lines a branch adds), not the detection. Point at the table of analysers per language, the diagram of the gate, then the rules learnt on real merge requests, the first one above all: a condition the gate could not measure fails. See [Leaving SonarQube](../sonar-decom.md).

### 5. API docs

**Tools**, **API docs**: every API of the catalog. Open the Bank Partner API: Swagger UI on its contract. Open **Order workflow events**: the RabbitMQ events of the order workflow, who sends, who receives, each payload field and an example, from an AsyncAPI contract. See [API contracts](../api-contracts.md).

### 6. Scenario design

**Tools**, **Scenario design**, "Checkout": the order journey as a graph, the transitions walked by a scenario in grey, the gaps dashed red (a refused payment, a worker that dies mid-step). Click "An order out of stock is cancelled before any payment": its path turns blue. **Run** runs it on the stack. Then "Account access": 6 gaps out of 23, among them an account migrated from a legacy login, the question to bring to the product owner. See [Scenario design](../scenario-design.md).

### 7. Recordings, the DevX and utility tools

- **Recorded examples**: what the captures recorded (the Bank Partner's answers, the order workflow's events with their milliseconds), the examples merged from them, the tests replaying them. See [Recorded examples](../recordings.md).
- **DevX**, **retro-footprint**: pick `Front, API, then a redirect to another front`, **Run**: the progress bar moves run by run, the grid lists the fronts, the APIs and only the tables seen so far, about 17 after the first run (colleagues are loud), then fewer; under each table, where it stands (`candidate`, `ruled out`, `confirmed`), `read` or `write`, and in how many runs it was seen (`3/3 runs`). The path draws the test with a dotted line: the storefront, the API call and its tables, then a dotted line marked *redirect* to the Quality Console and the table it reads. After 5 runs, two tables of a looping colleague are still there: the pause of 20 seconds starts (its countdown on the bar), and the first run of the second batch rules them out. The answer comes from the traces: it adds the bank partner behind `/api/hello`; under it, the coverage check says whether the database saw anything the traces do not name, here nothing (open **Run details**: one tab per run, then the **Coverage check** tab). The other tests of the list show the extreme cases: an API reading no table, a test reading the database itself, an API then the test's own SQL. The two *Simulated examples* call nothing: *too many items* fills the grid with 5 fronts, 11 APIs and the 30 tables, the rarest folded into dashed *+N* tiles, a click shows them; *hard to tell for 7 runs* keeps a nightly job's tables beside the test's until run 8. See [retro-footprint](../retro-footprint.md).
- **DevX**, **Tips**: one tab per topic; in **Front design**, click **Let it snow**, shoot the wooden target, show the static bullet hole on its transparent background, point at the orange **Beta** ribbon.
- **Documentation** (Static Cockpit QA): every page of `docs/`, starting with the testing guide; on any tool, **📖 Documentation** top right opens its own page.
- **DevX**, **Vault**: one credential per service, the seconds each has left running down; keep it open six minutes and watch a `hello-api` user replaced while greetings keep working. Then the long-lived key of the bank, its metadata only. See [Vault](../vault.md).
- **DevX**, **Quality Console MCP**: in Claude Code opened in the repository (the server is declared in `.mcp.json`), ask "Which tables does placing an order touch?": it calls `table_footprint("place-order")` and answers from the trace a minute later. Then "Does the Bank Partner still keep its contract?" (`run_scenario`), "What failed in the last runs?" (`recent_runs`). See [the MCP server](../mcp.md).
- **Tools**, **Gherkin scenarios**: each feature has its tool badge (`pytest`, `schemathesis`, `k6`); run **The greeting keeps its service level under load** (`k6`, half a minute), then `mise run test:perf` in a terminal and open the `perf-customer-welcome-baseline` run of env `local` in Test results.
- **Utility tools**, **Audio asset generator**: pick FLAC, then 32-bit is greyed (no such encoding); pick 5 seconds, stereo, 2 files, **Generate**: the two tracks show up highlighted, **▶** plays one, and `ls audio-assets/` in a terminal shows them on disk, while `git status` stays clean. See [Audio asset generator](../audio-assets.md).

### 8. The bucket browser

- **Bucket browser**: the buckets of the emulator (the team buckets `finance-exports` and `catalog-feeds`, and `test-results`), then `test-results`, its folders down to one run, `report.html` opened in place (sandboxed: its scripts do not run) or downloaded.

### 9. Databases, read-only for real

1. **Databases**: every database the account reads: `mycompany` (30 tables), `orchestrator` (the order workflow state), `catalog`, `identity`.
2. Open `identity`: two views, `accounts` and `password_links`, and no `users` table: the account was granted the views only, so it never sees a password hash nor a link secret.
3. Open `mycompany`: 30 tables from 10 to 113 rows, split in two: the 6 **live** ones the storefront writes (orders, order items, stock, invoices, payments, audit), the 24 **static** ones. Open `customers`, search `first_name` contains `ar`: Margaret and Barbara.
4. In a terminal: `docker compose exec mysql mysql -uconsole_reader -preader mycompany -e "DELETE FROM customers"`. MySQL answers `DELETE command denied`.
5. A table that does not exist: <http://localhost:8081/databases/mycompany/tables/salaries>, a `404` page.

Message to pass: the safety lives in the database grants, not in the page.

### 10. The test results page

1. Open <http://localhost:8081/test-results>. Laid out like the results dashboard it imitates: the runs on the left, the selected run on the right. The header says how old the index is; the counters cover the chosen period (`24h`, `7d`, `30d`, `all`).
2. Filter with the pills: status `failed`, then system `storefront`. Each pill applies at once. The filters come from the metadata each test declares (`metadata_test(...)` in every test module, values from the catalog).
3. Click a failed `api-customer-welcome` run: its **Details** tab shows the JUnit breakdown, the failing test first with its message, the facets as badges, the files of the run. Open `report.html`: the HTML report, served from the bucket.
4. Filter job `e2e-checkout-chromium`: its recent runs read `8/10 passed · 2 errors` on their cards. Open one: two tests in **Errors**, not in **Failed**: a timeout before any assertion. A job of ten tests fails as a whole for two; the catalog map shows the checkout red for it ([A job fails as a whole](../test-results.md#a-job-fails-as-a-whole-its-tests-say-how-much)).
5. Open a `perf-customer-welcome-baseline` run: no JUnit, a k6 summary instead (requests per second, p95, p99, broken thresholds).
6. Switch to the run's **Trends** tab: the job's average pass rate, passed runs out of its last 50, its current streak, then a dated chart of the pass rate over three runs, each point colored by its run's status, failed runs shaded, this run ringed. `api-customer-welcome` on `int` has a flaky test: the line dips and recovers. Click a point or a row of the history to jump to that run.
7. **Jobs** (top menu): every job at a glance, its last 20 runs as colored bars, its pass rate, its streak, its latest run.
8. Now a run of your own: `mise run test:unit`. The end of its output shows the upload: `gs://test-results/test-runner/reports/local/backend/.../unit-tests/`. Back on the page, it is not listed yet: the index is older than the upload.
9. Click **Refresh**: the index is rebuilt, and the run shows up under env `local`. In production nobody clicks: a scheduler rebuilds the index every 30 minutes (see [Schedules, kept for later](../test-results.md#schedules-kept-for-later)).

Message to pass: the tests, the uploader, the bucket, the indexer and the page agree on one contract (where a run goes, what `metadata.json` says), and every piece of it runs for real on the laptop.

## After the talk

`mise run down`. It deletes every container, the database included; the next `mise run up` reloads it from `db/`. The results bucket is a Docker volume and survives, like a real bucket.

<details>
<summary>If something goes wrong on stage</summary>

- Running the integration tests while `mise run up` runs too needs memory: give Docker 8 GB, or stop the stack first (`mise run down`). Under pressure, containers start too slowly and the browser test times out.
- The test results page is empty: `mise run results:seed`, then **Refresh**.
- Port 8081 or 4443 already in use: stop what listens there, or change the left side of the port of `console` in `docker-compose.yml`.
- `Access denied for user 'console_reader'`: the database was created before `db/03-console-reader.sql` existed. `mise run down && mise run up` recreates it from scratch.
- A table changed in `db/`: the running MySQL keeps its data until `mise run down`.

</details>

---

See also: [Test results in a bucket](../test-results.md), [The software catalog](../catalog-and-metadata.md), [Gherkin scenarios](../gherkin.md), [Leaving SonarQube](../sonar-decom.md), [API contracts](../api-contracts.md).
