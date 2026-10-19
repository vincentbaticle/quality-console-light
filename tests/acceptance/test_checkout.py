"""Checkout: an order is accepted at once, then paid or cancelled step by step."""

import time

import httpx
from playwright.sync_api import Page, expect
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from tests.acceptance.conftest import Context, Stack
from tests.metadata import metadata_test

pytestmark = [
    pytest.mark.acceptance,
    metadata_test(
        system="orders",
        product="checkout",
        business_capability="sell",
        component="order-worker",
        group="qa-web",
        testing_scope="acceptance",
    ),
]

scenarios("checkout")

WORKFLOW_TIMEOUT_SECONDS = 30
"""Budget for the worker to run every step, one and a half seconds each locally."""

POLL_SECONDS = 0.5
"""Delay between two looks at the workflow, as the storefront page does."""


@when(parsers.parse('"{username}" orders {quantity:d} "{sku}"'))
def place_order(
    stack: Stack, context: Context, username: str, quantity: int, sku: str
) -> None:
    context.response = httpx.post(
        f"{stack.storefront}/api/orders",
        json={"username": username, "sku": sku, "quantity": quantity},
    )


@then("the order is accepted at once")
def accepted(context: Context) -> None:
    assert context.response is not None
    assert context.response.status_code == 202, context.response.text


@then(parsers.parse('the workflow ends "{status}" with the order "{order_status}"'))
def workflow_ends(
    stack: Stack, context: Context, status: str, order_status: str
) -> None:
    assert context.response is not None
    workflow_id = context.response.json()["workflow_id"]
    deadline = time.monotonic() + WORKFLOW_TIMEOUT_SECONDS
    workflow: dict = {"status": "running"}
    while workflow["status"] == "running" and time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
        workflow = httpx.get(
            f"{stack.storefront}/api/orders/workflows/{workflow_id}"
        ).json()
    context.values["workflow"] = workflow
    assert (workflow["status"], workflow["order_status"]) == (status, order_status)


@then(parsers.parse('the step "{step}" is "{status}"'))
def step_is(context: Context, step: str, status: str) -> None:
    steps = {s["name"]: s["status"] for s in context.values["workflow"]["steps"]}
    assert steps[step] == status


@given(parsers.parse('the stock of "{sku}" holds at least {quantity:d} item'))
def stock_holds(stack: Stack, sku: str, quantity: int) -> None:
    products = httpx.get(f"{stack.storefront}/api/products").json()
    stock = next(p["stock"] for p in products if p["sku"] == sku)
    assert stock >= quantity, f"{sku} holds {stock}: mise run down && mise run up"


@when(parsers.parse('"{username}" orders {quantity:d} "{sku}" on the storefront page'))
def order_on_page(
    stack: Stack, page: Page, username: str, quantity: int, sku: str
) -> None:
    page.goto(f"{stack.storefront}/#checkout")
    checkout = page.get_by_role("region", name="Checkout")
    checkout.get_by_label("Customer username").fill(username)
    checkout.get_by_label("Product").select_option(sku)
    checkout.get_by_label("Quantity").fill(str(quantity))
    checkout.get_by_role("button", name="Place order").click()


@then("the page shows every step done and the order paid")
def page_shows_paid(page: Page) -> None:
    checkout = page.get_by_role("region", name="Checkout")
    timeout = WORKFLOW_TIMEOUT_SECONDS * 1000
    status = checkout.get_by_role("status")
    expect(status).to_contain_text("workflow completed", timeout=timeout)
    expect(status).to_contain_text("paid")
    steps = checkout.get_by_role("list", name="Workflow steps")
    for step in ("Reserve stock", "Issue invoice", "Capture payment"):
        expect(steps).to_contain_text(f"{step} · done")
