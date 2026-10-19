# The order workflow: an event-driven POST

The second form of the product page places an order. Unlike the greeting, the API does not do the work while you wait: it writes the order, answers `202 Accepted` at once, and hands the work over to a worker through a message broker, one event per step. It is the shape of an event-driven orchestrator: a thin HTTP surface on top of a queue, the state of each workflow kept in its own database, every step triggered by the completion of the previous one.

> **TL;DR**
>
> - `mise run up`, then on <http://localhost:8080> click **ada buys Foundation**: the timeline shows the three steps run one after the other, then the order `paid`. **grace buys an Ultrabook** fails on stock and cancels the order.
> - `POST /api/orders` writes the order `pending` and a workflow in the `orchestrator` database, publishes `{workflow_id, type: "reserve_stock"}` to RabbitMQ, and answers `202`. The `worker` service runs each step and publishes the next one.
> - Watch it from every side: the RabbitMQ UI (<http://localhost:15672>, `guest` / `guest`), the `orchestrator` and `mycompany` databases in the Quality Console, and one trace crossing the API, the queue and the worker in Grafana.

## The demo event: placing an order

An order is a good event to demo because it is obviously not instant in a real company: stock has to be reserved in a warehouse, an invoice issued, a payment captured, and any of them can fail. Each is one step, in this order:

1. **`reserve_stock`**: takes the quantity from a warehouse holding enough of the product (`stock_levels`). None does: the step fails with `Out of stock: <sku> needs <n>`, the next steps are skipped, the order is `cancelled`.
2. **`issue_invoice`**: writes the invoice (`invoices`, number `INV-<year>-<order id>`).
3. **`capture_payment`**: captures the payment of that invoice by card (`payments`), then the workflow is `completed` and the order `paid`.

Every step also leaves a line in `audit_logs`, signed `order-workflow`. The worker waits 1.5 seconds per step (`WORKFLOW_STEP_DELAY_SECONDS` in `docker-compose.yml`), so a person sees the workflow move; the tests set it to 0.

## Who does what

- **The API** (`src/hello_api/orders.py`): `POST /api/orders` checks the customer is active and the product exists, writes the order (`orders`, `order_items`, status `pending`) and the workflow (`orchestrator.workflows`, `orchestrator.workflow_steps`, all `pending`), publishes the first event, answers `202 {workflow_id, order_id, status}`. `GET /api/orders/workflows/{id}` tells where it stands, step by step. `GET /api/products` lists the products with their stock, for the form.
- **The broker**: RabbitMQ, one durable queue, `order-workflow`. Events are thin, `{"workflow_id": "...", "type": "issue_invoice"}`: what a step needs is read from the databases, never carried in the message.
- **The worker** (`src/order_workflow/worker.py`, service `worker`): takes one event at a time, marks the step `running`, does it, marks it `done` with what it did, publishes the next step's event, or closes the workflow after the last. An event is acknowledged only once handled, so a worker that dies mid-step gets it again on restart.
- **Two databases**: `mycompany` holds the business facts (orders, stock, invoices, payments), `orchestrator` holds the workflows (`db/04-orchestrator.sql`). The Quality Console reads both.
- **The page** (`frontend/app.js`): posts the form, then asks `GET /api/orders/workflows/{id}` every half second and draws the timeline until the workflow is over.

## Seeing it work

- **The page**: the timeline under the form, each step with its detail (`2 x BK-0003 from warehouse 3`, `INV-2026-000011`, `25.00 EUR by card`).
- **The queue**: <http://localhost:15672>, `guest` / `guest`, **Queues and Streams**, `order-workflow`: the message rates move when an order is placed.
- **The databases**: the Quality Console, <http://localhost:8081>, `orchestrator` then `workflows` and `workflow_steps`; `mycompany` then `orders`, `invoices`, `payments`, `audit_logs`, `stock_levels`.
- **The trace**: `mise run traces`, then search the service `hello-api` for `POST /api/orders`. One trace holds the API's `INSERT`s, its `order-workflow send`, then in the service `order-worker` each `order-workflow receive` and the step's `SELECT`, `UPDATE` and `INSERT`: the trace context travels in the message headers.

Each `mise run up` starts the company database from `db/` again, so orders and stock reset; `mise run down && mise run up` gives a fresh demo.

## How it is tested

- **Unit** (`tests/unit/test_order_steps.py`): the order of the steps, the invoice number, the shape of an event.
- **Integration** (`tests/integration/test_orders_rabbitmq.py`): against a real RabbitMQ and a real MySQL started by testcontainers (sidecars in CI). A test posts an order, then runs the worker's own `handle` on every waiting event (`drain`) until the queue is empty, and checks the workflow, the order status, the stock taken and the payment written. The out of stock case, the refusals (unknown or closed customer, unknown product, quantity out of 1 to 5) and the products list each have theirs. The `order_store` fixture puts the company data back after each test, so the other tests still find the row counts of the seed.

The events themselves are recorded on the running stack (`mise run capture:events`, then `mise run capture:events-merge`) into `contracts/order-workflow-recorded.yaml`, and a test checks that the code publishes the recorded events, in the recorded order, with the recorded fields: see [Recordings](recordings.md).
- **Browser** (`tests/integration/test_hello_page_browser.py`): the whole stack, worker included, and Chromium clicking **ada buys Foundation** until the timeline says `paid`.

---

See also: [README.md](../README.md), the [observability demo](demos/observability.md) for the trace across the queue.
