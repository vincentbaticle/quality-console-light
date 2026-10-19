"""Ordering as an event-driven workflow, against a real RabbitMQ and a real MySQL."""

import json

from fastapi.testclient import TestClient
import pytest
import yaml

from company_db import DatabaseSettings, connect
from order_workflow.broker import StepEvent, drain, publisher
from order_workflow.steps import STEPS
from order_workflow.store import OrderStore
from order_workflow.worker import handle
from tests.metadata import metadata_test
from tests.neighbours import PROJECT_ROOT

pytestmark = [
    pytest.mark.integration,
    metadata_test(
        system="orders",
        product="checkout",
        business_capability="sell",
        component="order-worker",
        group="checkout-squad",
        testing_scope="integration",
        tags="rabbitmq, mysql",
    ),
]


IN_STOCK_SKU = "BK-0003"
"""Foundation, 19 copies in stock in the seed."""

OUT_OF_STOCK_SKU = "EL-0001"
"""Ultrabook 14, none left in any warehouse in the seed."""


def run_worker(broker: str, store: OrderStore) -> list[StepEvent]:
    """Handle every waiting event like the worker does, and return them."""
    seen: list[StepEvent] = []

    def record_and_handle(event: StepEvent) -> None:
        seen.append(event)
        handle(store, publisher(broker), event)

    drain(broker, record_and_handle)
    return seen


def scalar(database: DatabaseSettings, sql: str, *params: object) -> int:
    """Read one number from the company database."""
    with connect(database) as connection, connection.cursor() as cursor:
        cursor.execute(sql, params)
        row = cursor.fetchone()
    assert row is not None
    return int(row[0])


def test_order_is_accepted_at_once_and_paid_by_the_workflow(
    api: TestClient, broker: str, order_store: OrderStore, database: DatabaseSettings
) -> None:
    stock_before = scalar(
        database, "SELECT quantity FROM stock_levels WHERE product_id = 3"
    )

    accepted = api.post(
        "/api/orders", json={"username": "ada", "sku": IN_STOCK_SKU, "quantity": 2}
    )
    workflow_id = accepted.json()["workflow_id"]
    pending = api.get(f"/api/orders/workflows/{workflow_id}").json()
    events = run_worker(broker, order_store)
    done = api.get(f"/api/orders/workflows/{workflow_id}").json()

    assert accepted.status_code == 202
    assert pending["order_status"] == "pending"
    assert [event.type for event in events] == list(STEPS)
    assert done["status"] == "completed"
    assert done["order_status"] == "paid"
    assert [step["status"] for step in done["steps"]] == ["done", "done", "done"]
    order_id = done["order_id"]
    assert (
        scalar(database, "SELECT quantity FROM stock_levels WHERE product_id = 3")
        == stock_before - 2
    )
    assert (
        scalar(
            database,
            "SELECT COUNT(*) FROM payments p JOIN invoices i"
            " ON i.id = p.invoice_id WHERE i.order_id = %s",
            order_id,
        )
        == 1
    )


def test_out_of_stock_fails_the_workflow_and_cancels_the_order(
    api: TestClient, broker: str, order_store: OrderStore
) -> None:
    accepted = api.post(
        "/api/orders",
        json={"username": "grace", "sku": OUT_OF_STOCK_SKU, "quantity": 1},
    )
    run_worker(broker, order_store)
    done = api.get(f"/api/orders/workflows/{accepted.json()['workflow_id']}").json()

    assert done["status"] == "failed"
    assert done["order_status"] == "cancelled"
    assert [step["status"] for step in done["steps"]] == [
        "failed",
        "skipped",
        "skipped",
    ]
    assert done["steps"][0]["detail"] == "Out of stock: EL-0001 needs 1"


@pytest.mark.parametrize(
    ("order", "status"),
    [
        ({"username": "nobody", "sku": IN_STOCK_SKU, "quantity": 1}, 404),
        ({"username": "dennis", "sku": IN_STOCK_SKU, "quantity": 1}, 404),
        ({"username": "ada", "sku": "XX-0000", "quantity": 1}, 404),
        ({"username": "ada", "sku": IN_STOCK_SKU, "quantity": 0}, 422),
        ({"username": "ada", "sku": IN_STOCK_SKU, "quantity": 6}, 422),
    ],
)
def test_refused_orders_never_start_a_workflow(
    api: TestClient,
    broker: str,
    order_store: OrderStore,
    order: dict[str, object],
    status: int,
) -> None:
    response = api.post("/api/orders", json=order)

    assert response.status_code == status
    assert run_worker(broker, order_store) == []


def test_products_carry_their_stock(api: TestClient, order_store: OrderStore) -> None:
    products = {p["sku"]: p for p in api.get("/api/products").json()}

    assert products[OUT_OF_STOCK_SKU]["stock"] == 0
    assert products[IN_STOCK_SKU]["price_cents"] == 1250


RECORDED = yaml.safe_load(
    (PROJECT_ROOT / "contracts" / "order-workflow-recorded.yaml").read_text()
)
"""Events recorded on the running stack by mise run capture:events."""


@pytest.mark.parametrize("story", sorted(RECORDED["stories"]))
def test_the_workflow_publishes_the_events_recorded_for_the_same_order(
    story: str, api: TestClient, broker: str, order_store: OrderStore
) -> None:
    recorded = RECORDED["stories"][story]

    api.post("/api/orders", json=recorded["order"])
    events = run_worker(broker, order_store)

    expected = [event["body"] for event in recorded["events"]]
    assert [event.type for event in events] == [body["type"] for body in expected]
    assert [set(json.loads(event.to_json())) for event in events] == [
        set(body) for body in expected
    ]
