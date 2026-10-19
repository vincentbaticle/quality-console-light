# Observability demo: see what the product does

Step-by-step script to show an audience what observability brings, with the same product as the [testcontainers demo](testcontainers.md): every call to the API leaves a trace, and a trace tells what happened behind the page, across services, without opening a debugger or reproducing anything. In production the traces go to a platform such as Tsuga; here a free all-in-one container plays that platform on the laptop. About 15 minutes.

> **TL;DR**
>
> - `mise run up`, `mise run traffic`, then Grafana on <http://localhost:3000>: **Explore**, **Tempo**, Service Name `hello-api`.
> - Read one healthy trace, one refusal, then break the bank (`docker compose stop partner`) and find the failure in the traces.
> - No telemetry code in the product: `opentelemetry-instrument` and a few `OTEL_*` variables do it all, and sending to a real platform only changes the endpoint.

## What observability is for

A test says whether something works, before it ships. Observability says what the system actually did, once it runs, on the requests nobody wrote a test for. It is the ability to answer a question about a running system ("why was this call slow?", "which service refused this customer?", "since when do we answer 502?") from what the system already emits, without adding code and without reproducing the problem.

Three kinds of signals carry that information:

- **Traces**: the path of one request through every service it crosses, as a tree of timed steps called spans. The best tool to answer "what happened to this call".
- **Metrics**: numbers aggregated over time (calls per route, error rate, durations). The best tool to answer "how much, how often, since when", and to alert.
- **Logs**: the lines a service writes. Most useful when each line carries the trace it belongs to.

OpenTelemetry (OTel) is the open standard to produce and ship these signals: an SDK in each service, the OTLP protocol on the wire, and any backend at the end. Because the standard sits between the code and the backend, the same service can send to Tsuga in production and to a local stack on a laptop.

For a QA engineer, it changes three things: a failing end-to-end test points to a trace that says which service broke; behaviour in production can be checked against what the tests assumed; and instrumentation itself can be verified before it ships, as this demo does.

## How the project is wired

- The services (`hello-api`, `bank-partner`, `order-worker`, `identity-service`) and the Quality Console start with `opentelemetry-instrument` in their image. It instruments FastAPI, httpx, Redis, PyMySQL and the RabbitMQ client automatically: there is no telemetry line in `src/` or `partner/`.
- `docker-compose.yml` gives them the standard variables: `OTEL_EXPORTER_OTLP_ENDPOINT` (OTLP over HTTP, port 4318), `OTEL_SERVICE_NAME`, and which signals to export (traces and metrics; logs stay on `docker compose logs`).
- The `observability` service is [`grafana/otel-lgtm`](https://github.com/grafana/docker-otel-lgtm): an OpenTelemetry collector, Tempo (traces), Prometheus (metrics), Loki (logs) and Grafana (the UI), in one container. It plays the role Tsuga plays in production.
- In the tests, `OTEL_SDK_DISABLED=true` turns the SDK off: no collector runs in a test.
- Grafana is only the screen. The services know nothing about it: they speak OpenTelemetry (OTLP) to the collector inside `observability`, which stores the traces in Tempo and the metrics in Prometheus. Swap the container for Tsuga's endpoint and the same data lands there; Grafana's login is switched off in `docker-compose.yml` because nobody needs an account on a laptop.

## Before the talk

1. Install and pre-pull as in the [testcontainers demo](testcontainers.md#before-the-talk).
2. `mise run up` once to build the images, open <http://localhost:3000> to check Grafana answers, then `mise run down`.

## On stage

### 1. Start the product and use it

1. `mise run up`. It returns once MySQL, Redis, the bank, the API, the front, the Quality Console and the observability stack all run.
2. Open <http://localhost:8080>, type `ada` (or click one of the examples under the field: `ada`, `grace`, `zoe`, `dennis`), click "Say hello".
3. `mise run traffic` sends five more greetings: ada, grace, zoe (no bank account), dennis (closed customer), nobody (unknown).

### 2. Find a trace

1. `mise run traces`: Grafana opens straight on the `hello-api` traces of the last 15 minutes (the same link is the Observability card of the console). No account needed: the stack opens Grafana to anonymous visitors and hides its login form; the "Sign in" button top right can be ignored. A login page anyway means an old cookie of another app on `localhost:3000`: use a private window, or `admin` / `admin`.
2. Traces show up 10 seconds to a minute after the calls: the collector and Tempo batch before they make them searchable. If your call is not listed yet, click the blue refresh button (top right).
3. Each line is one request: its route, its start time, its duration. Click the trace id to open it.

<details>
<summary>Getting there by hand, without the link</summary>

**Explore** in the left menu, data source **Tempo** (the dropdown at the top), query type **Search**, Service Name `hello-api`, then **Run query** (blue button, top right). Explore opens on another data source by default, which is why the link is easier.

</details>

### 3. Read a healthy trace

Click a trace of ada and read the waterfall top to bottom:

1. `GET /api/hello`: the request as the API received it, the whole duration.
2. `SELECT`: the customer read in MySQL. Open the span: `db.statement` holds the SQL, the username is a bound parameter.
3. `GET`: the call to the bank. It continues inside `bank-partner`, another service: `GET /balance`, then its own `SELECT` on `bank_accounts`. One trace crosses two services because the trace context travels in an HTTP header (`traceparent`).
4. `INCRBY`: the visit counted in Redis.

Message to pass: one page view, five steps, two services, and every step timed. Nobody wrote a line of code for it.

### 4. Read a refusal

Run a search again and click a trace of dennis: `GET /api/hello` then `SELECT`, and nothing else. The trace proves the refusal happened in the API, before the bank was called and before any visit was counted.

### 5. A trace across a queue

1. On <http://localhost:8080>, click **ada buys Foundation** in the order card.
2. In Explore, search the service `hello-api` again: the newest trace is `POST /api/orders`. Open it.
3. It does not stop at the API. After its `INSERT`s and its `order-workflow send` (the event published to RabbitMQ), the same trace continues in another service, `order-worker`: each `order-workflow receive`, then the step's `SELECT`, `UPDATE` and `INSERT`, three times, one per step, seconds apart.
4. The trace context travels in the message headers: the API answered `202` long before the work was done, and the trace still shows the whole story.

Message to pass: asynchronous work is exactly where logs alone lose the thread; a trace follows the request through the broker. More in [The order workflow](../order-workflow.md).

### 6. An incident, found in the traces

1. Break the bank: `docker compose stop partner`.
2. `mise run traffic`: ada and grace now get `{"detail":"Bank Partner unreachable: ..."}`, a `502`.
3. In Explore, switch the query type to **TraceQL** and run `{ resource.service.name = "hello-api" && status = error }`.
4. Open one: the request ended in `502`, the `GET` span to the bank is in error with the exception attached, and the `INCRBY` never happened.
5. Repair: `docker compose start partner`, then `mise run traffic` again. Back to healthy traces.

Message to pass: without traces, a `502` on the page is a guess between three neighbours. With them, the failing step, its error and its duration are one click away.

### 7. Metrics: the same calls, counted

1. In Explore, switch the data source to **Prometheus**, then the editor to **Code**.
2. Run `sum by (http_status_code) (http_server_duration_milliseconds_count{service_name="hello-api"})`: how many calls ended in `200`, `404` and `502`.
3. Traces explain one call, metrics show the trend: this is what an alert watches.

### 8. And in production

Nothing in the product changes. In a cluster, the platform injects `OTEL_EXPORTER_OTLP_ENDPOINT` pointing at its collector, and the traces land in Tsuga instead of this local Grafana. To try it from the laptop, point that one variable at another OTLP backend: the code and the images stay the same.

## After the talk

`mise run down`. It deletes every container, the traces included.

<details>
<summary>If something goes wrong on stage</summary>

- No trace after a minute: check the time range (top right, "Last 15 minutes") and that `docker compose ps` shows `observability` running.
- Service Name list empty: no call reached a service yet, run `mise run traffic`.
- Port 3000 or 4318 already in use: stop what listens there, or change the left side of the port in `docker-compose.yml`.
- Another backend wanted (an APM-style UI like SigNoz): start it from its own `docker compose`, then point `OTEL_EXPORTER_OTLP_ENDPOINT` at it. Mind its UI port, often 8080 like the front.

</details>

---

See also: [README.md](../../README.md), section "Seeing the API calls".
