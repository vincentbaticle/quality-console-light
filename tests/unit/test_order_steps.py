"""Pure rules of the order workflow: the order of its steps, invoice numbers."""

import pytest

from order_workflow.broker import StepEvent
from order_workflow.steps import STEPS, invoice_number, next_step
from tests.metadata import metadata_test

pytestmark = [
    pytest.mark.unit,
    metadata_test(
        system="orders",
        product="checkout",
        business_capability="sell",
        component="order-worker",
        group="checkout-squad",
        testing_scope="unit",
    ),
]


def test_steps_follow_each_other_then_stop() -> None:
    assert [next_step(step) for step in STEPS] == [
        "issue_invoice",
        "capture_payment",
        None,
    ]


def test_invoice_number_pads_the_order_id() -> None:
    assert invoice_number(42, 2026) == "INV-2026-000042"


def test_events_stay_thin() -> None:
    event = StepEvent("wf-1", "reserve_stock")

    assert StepEvent.from_json(event.to_json()) == event
    assert event.to_json() == b'{"workflow_id": "wf-1", "type": "reserve_stock"}'
