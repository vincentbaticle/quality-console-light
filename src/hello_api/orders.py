"""Order routes: place an order as a workflow, follow it, list the products.

Placing answers ``202 Accepted`` at once with the workflow id: the work itself
happens later, step by step, in the worker. The page then follows the
workflow until it is completed or failed.
"""

from collections.abc import Callable
from dataclasses import asdict
from http import HTTPStatus
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from order_workflow.broker import StepEvent
from order_workflow.steps import MAX_QUANTITY, STEPS
from order_workflow.store import OrderStore, UnknownCustomerError, UnknownProductError

USERNAME_MAX_LENGTH = 50
"""Longest username an order accepts, as the greeting does."""


class OrderRequest(BaseModel):
    """What the order form sends."""

    username: str = Field(min_length=1, max_length=USERNAME_MAX_LENGTH)
    sku: str = Field(min_length=1, max_length=30)
    quantity: int = Field(ge=1, le=MAX_QUANTITY)


class OrderAccepted(BaseModel):
    """Answer to a placed order: where to follow it."""

    workflow_id: str
    order_id: int
    status: str


def orders_router(store: OrderStore, publish: Callable[[StepEvent], None]) -> APIRouter:
    """Build the order routes.

    Args:
        store: Reads and writes orders and workflows.
        publish: Publishes a workflow event to the broker.

    Returns:
        The router to include in the API.
    """
    router = APIRouter(prefix="/api")

    @router.get("/products")
    def products() -> list[dict[str, Any]]:
        """The products an order may hold, with their stock."""
        return [asdict(product) for product in store.products()]

    @router.post("/orders", status_code=HTTPStatus.ACCEPTED)
    def place_order(order: OrderRequest) -> OrderAccepted:
        """Write the order as pending and start its workflow."""
        try:
            placed = store.place(order.username, order.sku, order.quantity)
        except UnknownCustomerError as exc:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Unknown customer") from exc
        except UnknownProductError as exc:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Unknown product") from exc
        publish(StepEvent(placed.workflow_id, STEPS[0]))
        return OrderAccepted(
            workflow_id=placed.workflow_id, order_id=placed.order_id, status="running"
        )

    @router.get("/orders/workflows/{workflow_id}")
    def workflow(workflow_id: str) -> dict[str, Any]:
        """Where a workflow stands, step by step, and its order's status."""
        view = store.workflow(workflow_id)
        if view is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, "Unknown workflow")
        return asdict(view)

    return router
