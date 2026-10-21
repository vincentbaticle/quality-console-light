# Testing with testcontainers: how each product is tested, and how to test a test

> **Disclaimer**: this is a personal demo project, not a source of truth or a reference implementation. It reflects my own understanding and choices: its content remains subjective, despite the quotes and references it contains. It may be incomplete, simplified, inaccurate or outdated, and it is not meant for production use. Always check the official documentation before applying anything from it. Provided as is, without any warranty: you use it at your own risk.

The general guide of the project: what a test with real neighbours looks like, which test proves which product, and how to check that such a test really tests something.

> **TL;DR**
>
> - Three levels, three markers: `unit` (pure rules, no I/O), `integration` (the real code against real neighbours started by testcontainers), `acceptance` (the Gherkin scenarios against the running stack).
> - An integration test never starts a container itself: a session fixture of `tests/integration/conftest.py` does, on a random port, and removes it at the end.
> - A test of a test: Docker stopped, it skips and says why; run twice, it stays green; break the code, it turns red; break the neighbour, it fails with a clear message.

## The three levels

| Level | Marker | What it proves | Runs with |
| --- | --- | --- | --- |
| Unit | `unit` | A pure rule: the greeting sentence, a password policy, a percentile | `mise run test:unit`, no Docker |
| Integration | `integration` | The real code with a real neighbour: MySQL, Redis, RabbitMQ, Microcks, Mailpit, the storage emulator, a browser | `mise run test:integration`, Docker |
| Acceptance | `acceptance` | A product keeps the promise a Gherkin scenario writes | `mise run test:acceptance` on the stack of `mise run up`, or **Run** in the console |

Unit tests stay for what no call can show. Everything a request can show is tested with a request, against a real neighbour: no mock across a boundary, because a mock answers what its author expected and teaches nothing.

## What a testcontainers test is

Four moves, all in a session fixture:

1. Start the container: `with RedisContainer("redis:7.4-alpine") as redis:`.
2. Ask for the port Docker chose: `redis.get_exposed_port(6379)`. Never the default port: two runs never collide.
3. `yield` the connection data; every test of the session uses the same container.
4. Leaving the `with` stops and removes the container.

```python
@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    if uses_external_services():
        yield f"redis://{os.environ[REDIS_HOST_VARIABLE]}:{REDIS_PORT}/0"
        return
    require_docker()
    with RedisContainer(REDIS_IMAGE) as redis:
        host = redis.get_container_host_ip()
        yield f"redis://{host}:{redis.get_exposed_port(REDIS_PORT)}/0"
```

- `require_docker()` skips the test, with the reason, when no Docker daemon answers: a missing daemon is a machine problem, not a product bug.
- `uses_external_services()` (variable `INTEGRATION_EXTERNAL_SERVICES`) attaches to the CI sidecars instead: the same test code runs locally and in CI.
- A test that writes shared data writes its own (a new plus address of the QA mailbox) or restores what it changed (`order_store`), so the next run starts clean.

## Which test proves which product

### Customer welcome

- **By hand**: the storefront, **Customer welcome**: `ada` (greeted with a balance), `zoe` (no bank account: no balance), `dennis` (closed: refused). Say hello twice: the visit number grows.
- **Integration**: `test_hello_redis.py` (a Redis container: the visit counted under `visits:ada`), `test_hello_customers_mysql.py` (a MySQL container loaded from `db/`: the first name, the closed customer refused), `test_hello_balance_microcks.py` (Microcks replaying the bank's recorded answers, its `404` included).
- **Gherkin**: `features/customer-welcome/greeting.feature`, four scenarios: a known customer greeted with the balance, every visit counted, no bank account, a closed customer refused. Console: **Gherkin scenarios**, section Customer welcome.

### Checkout

- **By hand**: **Checkout**, **ada buys Foundation** (paid, three steps green), **grace buys an Ultrabook** (out of stock: cancelled before any payment), **dennis** (refused at once). Watch the queue in RabbitMQ and the rows in **Databases**, `mycompany`, live tables.
- **Integration**: `test_orders_rabbitmq.py`, a RabbitMQ and a MySQL container: the API answers `202`, then the worker's handler, run through `drain`, takes each event; the events are compared with the recorded ones.
- **Gherkin**: `features/checkout/place-order.feature`: an order in stock paid step by step, an order out of stock cancelled, a closed customer refused.

### Account access

- **By hand**: **Account access**, sign in as `ada` (signed in), `grace` (blocked: the email says why), `zoe` (no password yet), `lin` (asked for an authenticator code, **compute the code** fills it); create an account with a new plus address, open its email in the QA mailbox, follow the link.
- **Integration**: `test_identity_mailpit.py`, a MySQL and a Mailpit container: emails stored in lower case, the welcome and reset emails, links that work once, ten wrong passwords that block, and the second factor: enrolment, the code asked after the password, a code that works once, an old code refused.
- **Gherkin**: `features/account-access/sign-in.feature` and `account-emails.feature`, ten scenarios; their map in **Scenario design**, "Account access".

### Every product together

`test_hello_page_browser.py` starts the whole stack in containers (MySQL, Redis, RabbitMQ with the worker, Microcks, Mailpit, the API, the identity service, the front) on a private network, and drives a real Chromium on it: a greeting, an order followed until paid, a sign-in, the way back to the product list.

## How to test a testcontainers test

A green test proves nothing until it has been seen red for the right reason. Five checks, in this order:

1. **Docker stopped**: stop Rancher Desktop, `mise run test:integration`. Every integration test skips with `Docker unavailable, start Rancher Desktop or Docker`, none fails. A failure here means a fixture starts a container without `require_docker()`.
2. **Twice in a row**: `mise run test` then `mise run test` again, no cleanup in between. Still green: no leftover row, queue message or email changes the second run. A red second run means a test does not restore what it wrote.
3. **Break the code**: change the rule the test is about (the greeting sentence, the `INCR` of a visit, the status of a cancelled order) and run only that test, `mise run test:integration -- -k visit`. It must turn red, with an assertion that names the difference. Still green means the test does not look at what it claims.
4. **Break the neighbour**: point the fixture at a wrong image tag, or remove a table from `db/01-schema.sql`. The failure must say which neighbour and why, not time out silently.
5. **Look at the containers**: `docker ps` while the suite runs shows the throwaway containers on random ports; they are gone when it ends. A container left behind means a fixture yields outside its `with`.

The same checks hold in CI with the sidecars (`INTEGRATION_EXTERNAL_SERVICES=true`): the test code does not change, only where the neighbours come from.

## Writing a new one

The worked example of the README, "Adding an API endpoint and its tests", in four steps; a new neighbour adds a constant in `tests/neighbours.py`, a session fixture in `tests/integration/conftest.py`, the `testcontainers[<extra>]` dependency and a CI sidecar. With Claude Code, `/new-api-test` follows the same steps, and `/new-gherkin-scenario` writes a scenario. See also [Gherkin scenarios](gherkin.md), [Recordings](recordings.md), [the testcontainers demo](demos/testcontainers.md).
