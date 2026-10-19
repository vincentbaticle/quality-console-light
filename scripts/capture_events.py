"""Record the events the order workflow really publishes, into a journal.

The capture of the Bank Partner records what a third party answers over HTTP;
this one records what our own services say over RabbitMQ. It switches on the
broker's firehose (every message published is copied to ``amq.rabbitmq.trace``),
places one order per story through the running storefront, and writes every
event the API and the worker published, in order, with the milliseconds since
the order was placed. The merge step turns the journal into the recorded
examples the tests and the API docs read.

Usage::

    mise run capture:events

Exit codes: 0 when every story was recorded, 1 when the stack could not be reached.
"""

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

import httpx
import pika
from pika.exceptions import AMQPError

from order_workflow.broker import QUEUE

BROKER_URL_VARIABLE = "CAPTURE_BROKER_URL"
"""Environment variable naming the broker to tap, set by the mise task."""

STOREFRONT_URL_VARIABLE = "CAPTURE_STOREFRONT_URL"
"""Environment variable naming the storefront orders are placed through."""

JOURNAL_PATH = Path("capture/events-journal.json")
"""Where the transcript is written, and where the merge reads it from."""

TRACE_EXCHANGE = "amq.rabbitmq.trace"
"""The firehose: a copy of every message published, once tracing is on."""

PUBLISH_BINDING = "publish.#"
"""Routing key of the copies of published messages, whatever the exchange."""

STORIES = {
    "paid-order": {"username": "ada", "sku": "BK-0004", "quantity": 1},
    "out-of-stock-order": {"username": "grace", "sku": "EL-0001", "quantity": 1},
}
"""The orders recorded, one per way a workflow ends."""

WORKFLOW_TIMEOUT_SECONDS = 30
"""Budget for a workflow to end, the worker pausing between steps."""

POLL_SECONDS = 0.3
"""Delay between two looks at the workflow and at the trace queue."""


def _workflow_over(client: httpx.Client, workflow_id: str) -> bool:
    """Say whether the workflow left the running state."""
    status = client.get(f"/api/orders/workflows/{workflow_id}").json()["status"]
    return status != "running"


def record_story(
    channel: Any, trace_queue: str, client: httpx.Client, order: dict[str, Any]
) -> dict[str, Any]:
    """Place one order and collect the events published for it.

    Returns:
        The order, its answer and its events with their offsets.
    """
    started = time.monotonic()
    answer = client.post("/api/orders", json=order)
    answer.raise_for_status()
    workflow_id = answer.json()["workflow_id"]
    events: list[dict[str, Any]] = []
    deadline = started + WORKFLOW_TIMEOUT_SECONDS
    over = False
    while time.monotonic() < deadline:
        method, properties, body = channel.basic_get(trace_queue, auto_ack=True)
        if method is not None:
            payload = json.loads(body)
            if payload.get("workflow_id") == workflow_id:
                headers = properties.headers or {}
                events.append(
                    {
                        "offset_ms": round((time.monotonic() - started) * 1000),
                        "queue": headers.get("routing_keys", [QUEUE])[0],
                        "body": payload,
                    }
                )
            continue
        if over:
            break
        over = _workflow_over(client, workflow_id)
        time.sleep(POLL_SECONDS)
    return {"order": order, "status": answer.status_code, "events": events}


def main() -> int:
    """Tap the broker, record every story, write the journal.

    Returns:
        The process exit code.
    """
    broker_url = os.environ[BROKER_URL_VARIABLE]
    storefront_url = os.environ[STOREFRONT_URL_VARIABLE]
    try:
        connection = pika.BlockingConnection(pika.URLParameters(broker_url))
        channel = connection.channel()
        trace_queue = channel.queue_declare(queue="", exclusive=True).method.queue
        channel.queue_bind(trace_queue, TRACE_EXCHANGE, PUBLISH_BINDING)
        with httpx.Client(base_url=storefront_url, timeout=10) as client:
            records = {
                story: record_story(channel, trace_queue, client, order)
                for story, order in STORIES.items()
            }
        connection.close()
    except (AMQPError, httpx.HTTPError) as exc:
        print(f"[capture] the stack could not be recorded, mise run up first: {exc}")
        return 1
    journal = {
        "broker_url": broker_url,
        "captured_at": datetime.now(UTC).isoformat(),
        "stories": records,
    }
    JOURNAL_PATH.parent.mkdir(exist_ok=True)
    JOURNAL_PATH.write_text(json.dumps(journal, indent=2) + "\n")
    for story, record in records.items():
        print(f"[capture] {story}: {len(record['events'])} events")
    print(f"[capture] written to {JOURNAL_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
