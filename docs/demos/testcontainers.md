# Run the testcontainers demo

Step-by-step script to present testcontainers to an audience with this project: a simulated company storefront (three products on one page, an API, a MySQL company database, Redis, a third-party "Bank Partner", a simulated Auth0 and a QA mailbox) whose tests start their own throwaway containers. Follow it once the day before to rehearse, then on stage. About 20 minutes.

Two other demos use the same project: [observability](observability.md) (what the product does, seen through its traces) and the [Quality Console](quality-console.md) (the catalog, the test results and the QA tools in one back office).

> **TL;DR**
>
> - The day before: `mise trust && mise install && mise run install`, pre-pull the images, `mise run test` all green.
> - On stage: the product, then one level of tests at a time (unit, Redis, MySQL, bank replayed by Microcks, capture, browser), with `docker ps` running in a second terminal.
> - Everything runs on the laptop: no shared environment, no credentials, nothing left behind.

## Before the talk

Rancher Desktop (or any Docker daemon) must be running, with at least 4 GB of memory. Every command below runs from the root of this repository, cloned with `git clone https://github.com/vincentbaticle/quality-console.git`.

1. Install the tools and the dependencies: `mise trust && mise install && mise run install`
2. Pre-pull the images, so the demo never waits on the network: `for image in mysql:8.4 redis:7.4-alpine nginx:1.27-alpine python:3.14-slim quay.io/microcks/microcks-uber:1.13.2 grafana/otel-lgtm:0.35.0 fsouza/fake-gcs-server:1.55.1 curlimages/curl:8.16.0 rabbitmq:3.13-management axllent/mailpit:v1.31.4; do docker pull -q "$image"; done`
3. Rehearse the whole suite with the hand-run stack stopped: `mise run test`. Expect `112 passed` for the unit run and `77 passed` for the integration run. The first run builds the API and front images and takes one to two minutes, the next ones about 30 seconds.
4. Build the hand-run stack once: `mise run up`, then `mise run down`.
5. Open in your editor, as tabs ready to show: `tests/integration/conftest.py`, `tests/database.py`, `contracts/bank-partner-examples.yaml`, `gitlab-ci/tests_stage.yml`.

<details>
<summary>A second terminal that shows containers living and dying</summary>

Run this in a terminal next to the main one, and leave it visible during the whole demo:

`while true; do clear; docker ps --format 'table {{.Image}}\t{{.Ports}}\t{{.Status}}'; sleep 1; done`

During each integration step, the audience sees MySQL, Redis, Microcks, the API and the front appear on random ports, then disappear when the tests end.

</details>

## On stage

### 1. The product

1. `mise run up`. It returns once everything runs.
2. Open <http://localhost:8080>: three products, each with what it is for. In **Customer welcome**, type `ada` (or click one of the examples under the field: `ada`, `grace`, `zoe`, `dennis`), click "Say hello" twice: `Hello Ada! You are visitor number 2. Your balance is 1250.75 EUR.` Then `dennis` (a closed customer): `Error 404`.
3. In the second card, click **ada buys Foundation**: the API answers at once, then the three steps of the order run one after the other (reserve stock, issue invoice, capture payment) until `paid`. **grace buys an Ultrabook** stops at the stock: `cancelled`.
4. `mise run down`.

Message to pass: six neighbours behind one page (MySQL, Redis, RabbitMQ and its worker, a bank we do not own, the API, the front), and a real test needs them all, without a shared environment.

### 2. Unit tests: no Docker

`mise run test:unit`, about a second. The last lines show the run uploaded to the results bucket, the way a CI job ends (or skipped, with the reason, when the stack is not up): see the [Quality Console demo](quality-console.md#6-the-test-results-page). Show `tests/unit/test_greeting.py`: only pure rules (the sentence, the amount in cents written with two decimals, the Redis key name) are unit-tested. No mock anywhere.

### 3. Integration with a real Redis

`mise run test:integration -- tests/integration/test_hello_redis.py`

In `conftest.py`, show the `redis_url` fixture and its four moves:

1. `with RedisContainer(...)` starts a container for the session.
2. `get_exposed_port(6379)` gives the random host port Docker picked, so two runs never collide.
3. `yield` hands the URL to the tests.
4. Leaving the `with` stops and deletes the container.

Then show `test_second_visit_is_counted_in_redis`: the test reads Redis directly to prove the counter is really there.

### 4. Integration with a real MySQL

`mise run test:integration -- tests/integration/test_hello_customers_mysql.py`

Show `mysql_container()` in `conftest.py`: no MySQL module, a generic `DockerContainer` with one variable and one port, which is all a module does under the hood. Then `tests/database.py`: wait for a real login (an open port is not a ready server), then run the two scripts of `db/`, the same ones `docker-compose.yml` uses.

Then `test_closed_customer_is_refused_and_not_counted`: a `WHERE status = 'active'` that only a real database can prove, and Redis checked to show nothing was counted.

### 5. The bank, replayed by Microcks

`mise run test:integration -- tests/integration/test_hello_balance_microcks.py`

Show `contracts/`: the bank's OpenAPI contract and its examples. Microcks reads both and answers the API's real HTTP calls with the example whose `username` matches. The API does not know it talks to a simulator.

Point at the `unknown-account` example (zoe, a customer without an account): a `404` written by hand, because a capture only records the success stories. `test_customer_without_account_is_greeted_without_balance` proves the API handles it.

### 6. An event-driven workflow, with a real RabbitMQ

`mise run test:integration -- tests/integration/test_orders_rabbitmq.py`

Show `test_order_is_accepted_at_once_and_paid_by_the_workflow`: the test posts an order (`202`, still `pending`), then runs the worker's own `handle` on every event waiting in a real RabbitMQ (`drain`), and checks the steps in their order, the order `paid`, the stock taken in MySQL and the payment written. No mock of the queue: the events really go through the broker. The `order_store` fixture puts the company data back afterwards. More in [The order workflow](../order-workflow.md).

### 7. Recording real answers

The examples are not invented, they are recorded from the bank.

1. `mise run partner:up` starts the bank and its database on <http://localhost:8090>.
2. Add `"linus"` to `CAPTURED_USERNAMES` in `tests/story.py`.
3. `mise run capture:examples` asks the bank about every username and writes `capture/journal.json`. Show it: one request, one answer per username.
4. `mise run capture:merge` writes the answers into the examples file.
5. `git diff contracts/`: the new `linus` example appears with the balance of the database, the hand-written `404` is untouched.
6. Put things back: `git restore tests/story.py contracts/ && mise run down`.

Message to pass: the test data is what the bank really said, and a refresh is a reviewed diff.

### 8. The full product in a browser

`mise run test:headed`. A visible Chromium, slowed down, types `ada` and checks the greeting and the balance twice, then places an order and waits until its timeline says `paid`. In the second terminal, the audience sees the whole product on a private Docker network: MySQL, Redis, RabbitMQ, the worker, Microcks, the API and the front, built from the repository.

### 9. No Docker, no failure

`DOCKER_HOST=unix:///nowhere.sock mise run test:integration`. Every integration test is skipped with the reason "Docker unavailable": a missing daemon is a machine problem, never a red test.

### 10. And in CI

Show `gitlab-ci/tests_stage.yml`. GitLab runners have no Docker daemon, so the `integration-tests` job declares MySQL, Redis, RabbitMQ, Microcks and the bucket emulator as sidecars and sets `INTEGRATION_EXTERNAL_SERVICES=true`. The fixtures attach to the sidecars instead of starting containers, and load the same scripts and contracts into them: same tests, other provisioning. The browser test skips there with its reason. The `sonarqube` job is a mock that never calls a real server (`gitlab-ci/mocks.yml`).

## After the talk

`mise run down`, then `git status` must show nothing modified. The containers the tests started are already gone.

<details>
<summary>If something goes wrong on stage</summary>

- "Docker unavailable" when Rancher Desktop is running: check `docker ps` answers in the same terminal. `.mise.toml` sets `DOCKER_HOST` to `~/.rd/docker.sock` when it is not already set.
- `docker-credential-gcloud` in an error: run the tests through `mise run`, which points Docker at the empty config of the repo. A bare `pytest` uses your own `~/.docker/config.json`.
- The browser test hangs on the first run: it is building the images. Rehearse the day before so the build cache is warm.
- `mise run up` fails on a port (3000, 3307, 4318, 8080, 8081, 8090): something else listens there, stop it or change the left side of the port in `docker-compose.yml`.
- A `config files are not trusted` error from mise: run `mise trust` in the project directory.

</details>

---

See also: [README.md](../../README.md) for how the project works and how to add an endpoint with its tests.
