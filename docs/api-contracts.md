# API contracts

> **Disclaimer**: this is a personal demo project, not a source of truth or a reference implementation. It reflects my own understanding and choices: its content remains subjective, despite the quotes and references it contains. It may be incomplete, simplified, inaccurate or outdated, and it is not meant for production use. Always check the official documentation before applying anything from it. Provided as is, without any warranty: you use it at your own risk.

Every API of the catalog has its contract in `contracts/`, and the Quality Console shows them: Swagger UI for the HTTP APIs, a page of its own for the events of the order workflow.

> **TL;DR**
>
> - <http://localhost:8081/tools/apis>, also linked from the catalog page.
> - HTTP (OpenAPI): the Bank Partner (a copy of what the partner publishes, replayed by Microcks), and our own services, written by `mise run contracts:export` from the code: storefront API, identity API, Gherkin runner.
> - Events (AsyncAPI 3): `contracts/order-workflow-asyncapi.yaml`, the RabbitMQ events of the order workflow, who sends them, who receives them, and their payload.
> - Unit tests keep them honest: an exported contract must be the one the service generates now, and the event contract must list exactly the steps of the workflow.
> - Every OpenAPI contract is also a mock, served by Prism on <http://localhost:4010>: a contract published in `contracts/` is a mock, with nothing else written.

## Contract mocks: Prism on every contract

`mise run up` starts `mocks`: Stoplight Prism (`@stoplight/prism-cli` 5.15.10 on node, built from `mocks/Dockerfile` for the machine's own platform; the official image is amd64 only, and five emulated copies starve the stack) serving each `contracts/<name>-openapi.yaml` under `/<name>/`, behind one port, through `mocks/router.mjs`; `/` lists the mocks and says when every one answers. The API docs page links each OpenAPI contract to its mock.

```sh
curl -s localhost:4010/ | jq .
curl -s -H 'X-Api-Key: any' 'localhost:4010/bank-partner/balance?username=ada'   # 200, the shape of the contract
curl -s 'localhost:4010/bank-partner/balance?username=ada'                       # 401: the contract asks for a key
curl -s -H 'X-Api-Key: any' 'localhost:4010/bank-partner/balance'                # 422: username is required
```

Prism answers from the contract alone: an example when the contract holds one, otherwise a value of the right type for each field, and it checks each request against the contract (parameters, body, security) before answering. That is what makes it worth having for every API: a team publishes a contract, the others get a mock at once.

What Prism does not do is pick an answer by request: `?username=ada` and `?username=grace` get the same example, unless the caller sends `Prefer: example=ada`. The Bank Partner's captured answers, one per customer, and its hand-written `404` therefore stay in **Microcks**, which matches each request against the examples of `bank-partner-examples.yaml`; the tests of the API use Microcks, the mocks are for everyone else.

`tests/integration/test_contract_mocks_prism.py` starts the same container with testcontainers: every OpenAPI contract of the catalog is listed, the Bank Partner answers its contract's shape, and refuses a request without its key (401) or its `username` (422). It has no CI sidecar: a GitLab service starts before the checkout, so it has no `contracts/` to serve; in sidecar mode the tests skip and say so.

## The event contract

The order workflow speaks in thin events, `{workflow_id, type}`, on the durable queue `order-workflow`. The contract says:

- **send**, by the storefront API: `reserve_stock`, when an order is placed;
- **send**, by the order worker: `issue_invoice` then `capture_payment`, once the previous step succeeded;
- **receive**, by the order worker: any of the three, run, then acknowledged.

Swagger UI only renders OpenAPI, so the console builds this page itself from the document (`src/quality_console/asyncapi.py`): servers, channel, operations, and each message with its fields and an example.

The events the stack really publishes are recorded too, see [Recordings](recordings.md): the contract says what may be sent, the recording what was sent.

The Bank Partner is no exception: its contract sits in `contracts/` with the others and opens in the same Swagger UI. The fake partner also serves its own live documentation on <http://localhost:8090/docs>, the page a real partner would publish.

## Changing a route

1. Change the route.
2. `mise run contracts:export`.
3. Review the diff of `contracts/` with the code: the contract is what a consumer reads.
