"""The worker: run the step an event names, then publish the next one.

Run it with ``python -m order_workflow.worker``. Each event is one step of one
order: the worker marks the step running, does its part in the company
database, marks it done with what it did, and publishes the next step's event,
or closes the workflow after the last. A step that cannot be done (no stock)
fails the workflow and cancels the order.
"""

from collections.abc import Callable
import os
import time

from pika.exceptions import AMQPConnectionError, ChannelClosedByBroker

from company_db import settings_from_environment
from order_workflow.broker import (
    StepEvent,
    consume_forever,
    publisher,
    url_from_environment,
)
from order_workflow.steps import next_step
from order_workflow.store import OrderStore, OutOfStockError

RECONNECT_SECONDS = 2
"""Pause before reconnecting when the broker closed the connection."""

STEP_DELAY_VARIABLE = "WORKFLOW_STEP_DELAY_SECONDS"
"""Variable slowing each step down, so a person can watch the workflow move."""


def handle(
    store: OrderStore,
    publish: Callable[[StepEvent], None],
    event: StepEvent,
    step_delay: float = 0.0,
) -> None:
    """Run the step an event names, then hand over to the next one.

    Args:
        store: Reads and writes orders and workflows.
        publish: Publishes the next step's event.
        event: The event to handle.
        step_delay: Seconds each step takes on purpose, 0 in tests.
    """
    actions = {
        "reserve_stock": store.reserve_stock,
        "issue_invoice": store.issue_invoice,
        "capture_payment": store.capture_payment,
    }
    order_id = store.order_of(event.workflow_id)
    store.mark_step(event.workflow_id, event.type, "running")
    time.sleep(step_delay)
    try:
        detail = actions[event.type](order_id)
    except OutOfStockError as exc:
        store.mark_step(event.workflow_id, event.type, "failed", str(exc))
        store.finish(event.workflow_id, succeeded=False, reason=str(exc))
        return
    store.mark_step(event.workflow_id, event.type, "done", detail)
    following = next_step(event.type)
    if following is None:
        store.finish(event.workflow_id, succeeded=True)
    else:
        publish(StepEvent(event.workflow_id, following))


def main() -> None:
    """Consume the workflow events until stopped.

    The broker closes the connection when the worker's short-lived user is
    revoked at the end of its lease: the worker reconnects with the
    credentials the Vault Agent wrote meanwhile.
    """
    url = url_from_environment()
    store = OrderStore(settings_from_environment())
    publish = publisher(url)
    delay = float(os.environ[STEP_DELAY_VARIABLE])
    while True:
        print(f"[order-worker] consuming, {delay}s per step", flush=True)
        try:
            consume_forever(url, lambda event: handle(store, publish, event, delay))
        except (AMQPConnectionError, ChannelClosedByBroker) as exc:
            print(f"[order-worker] connection lost ({exc!r}), reconnecting", flush=True)
            time.sleep(RECONNECT_SECONDS)


if __name__ == "__main__":
    main()
