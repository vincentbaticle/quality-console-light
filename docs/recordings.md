# Recorded examples: real calls and real events, replayed by the tests

> **Disclaimer**: this is a personal demo project, not a source of truth or a reference implementation. It reflects my own understanding and choices: its content remains subjective, despite the quotes and references it contains. It may be incomplete, simplified, inaccurate or outdated, and it is not meant for production use. Always check the official documentation before applying anything from it. Provided as is, without any warranty: you use it at your own risk.

A test that replays a hand-written example only proves the code agrees with its author. This project records what the neighbours really say, keeps the transcript, and turns it into the examples the tests replay against throwaway containers. The Quality Console lists every recording in **Tools**, **Recorded examples**, right after **API docs**.

> **TL;DR**
>
> - Two recordings: the **Bank Partner answers** (HTTP, a third party) and the **order workflow events** (RabbitMQ, our own services).
> - Each has a **journal** in `capture/` (the raw transcript, not committed) and **examples** in `contracts/` (merged from the journal, committed, reviewed in a diff).
> - Partner: `mise run partner:up`, `mise run capture:examples`, `mise run capture:merge`. Events: `mise run up`, `mise run capture:events`, `mise run capture:events-merge`.
> - The storefront itself records nothing: its cards produce the traffic, the capture commands record it.

## Prism or Microcks?

Not rivals, two jobs on the same `contracts/`:

| | Contract mocks (Prism) | Microcks |
|---|---|---|
| For | anyone trying an API by hand, a team waiting on another | the integration tests |
| Answers from | the contract alone: one example per operation | the recorded examples: the answer picked by request |
| Runs | `mise run up`, <http://localhost:4010> | testcontainers or a CI sidecar, never in the console |
| In the console | the 🎭 links of **API docs**, the **Contract mocks (Prism)** card | **Recorded examples** |

## What a recording is for

Three steps, the same for both recordings:

1. **Record** against the real thing: the partner as it answers today, the broker as our services use it.
2. **Merge** the transcript into examples: only that file changes, so a reviewer reads the difference ("the bank now answers another balance") before it is committed.
3. **Replay** in the tests, against containers: Microcks serves the partner's recorded answers to the real HTTP client; the order workflow test compares the events the code publishes with the recorded ones.

Writing a test that uses a recording: by hand, follow the README ("Recording what the partner answers", then "Adding an API endpoint and its tests"); with Claude Code, `/new-api-test` reads the same conventions.

## The Bank Partner answers (HTTP)

- Recorded from the fake partner on <http://localhost:8090> (`mise run partner:up`), `GET /balance` for every username of `tests/story.py`.
- Journal `capture/journal.json`, one record per username: request, status, body.
- Examples `contracts/bank-partner-examples.yaml`: the `200` examples come from the journal, the `404` (`unknown-account`) is written by hand, since a capture only records success stories, and the merge never touches it.
- Replayed by Microcks in `test_hello_balance_microcks.py` and in the browser test.

## The order workflow events (RabbitMQ)

- Recorded from the broker of `mise run up` through its **firehose**: `rabbitmqctl trace_on` copies every published message to `amq.rabbitmq.trace`; the capture binds a queue to it, places one order per story through the storefront, and keeps the events of that order with the milliseconds since it was placed. The task switches tracing off at the end.
- Stories: `paid-order` (ada buys `BK-0004`) and `out-of-stock-order` (grace buys `EL-0001`).
- Journal `capture/events-journal.json`; examples `contracts/order-workflow-recorded.yaml`, the workflow id replaced by `<workflow_id>` since it changes at every capture.
- Replayed by `test_orders_rabbitmq.py`: for each story, the same order is placed against a RabbitMQ container and the events the code publishes must have the recorded types, in the recorded order, with the recorded fields.

The broker port 5672 is published by `docker-compose.yml` for the capture; the account is `guest` / `guest`.
