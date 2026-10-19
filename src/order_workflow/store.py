"""What the order workflow reads and writes, in both databases.

The company database holds the business facts (orders, stock, invoices,
payments, audit log). The orchestrator database holds the workflow itself:
its status and the status of each step, which is what the API answers when
asked how an order is going.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace
import datetime
from typing import Any
import uuid

from pymysql.connections import Connection
from pymysql.cursors import Cursor

from company_db import DatabaseSettings, connect
from order_workflow.steps import (
    ORCHESTRATOR_DATABASE,
    STEPS,
    WORKFLOW_KIND,
    invoice_number,
)

ACTOR = "order-workflow"
"""Name the workflow signs its audit log lines with."""

PAYMENT_METHOD = "card"
"""Payment method the demo captures every payment with."""


class UnknownCustomerError(LookupError):
    """No active customer has that username."""


class UnknownProductError(LookupError):
    """No product has that SKU."""


class OutOfStockError(RuntimeError):
    """No warehouse holds enough of the product."""


@dataclass(frozen=True)
class Product:
    """A product the order form offers, with what all warehouses hold."""

    sku: str
    name: str
    price_cents: int
    currency: str
    stock: int


@dataclass(frozen=True)
class PlacedOrder:
    """What the API answers once an order is placed."""

    workflow_id: str
    order_id: int


@dataclass(frozen=True)
class StepView:
    """One step of a workflow, as the API shows it."""

    name: str
    status: str
    detail: str | None
    finished_at: str | None


@dataclass(frozen=True)
class WorkflowView:
    """A workflow and its steps, as the API shows it."""

    id: str
    order_id: int
    status: str
    order_status: str
    steps: list[StepView]


def _one(cursor: Cursor) -> tuple[Any, ...]:
    """The row a query must have found; a missing one is a broken invariant."""
    row = cursor.fetchone()
    if row is None:
        raise LookupError("expected one row, found none")
    return tuple(row)


def _now() -> datetime.datetime:
    """Current UTC time, naive as MySQL ``DATETIME`` columns hold it."""
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


class OrderStore:
    """Reads and writes orders and their workflows."""

    def __init__(self, company: DatabaseSettings) -> None:
        """Point at the company database; the orchestrator one sits beside it.

        Args:
            company: Settings of the company database, with write rights.
        """
        self._company = company
        self._orchestrator = replace(company, name=ORCHESTRATOR_DATABASE)

    @contextmanager
    def _transaction(self, settings: DatabaseSettings) -> Iterator[Cursor]:
        """A cursor whose writes are committed together, or not at all."""
        connection: Connection[Cursor] = connect(settings)
        try:
            with connection.cursor() as cursor:
                yield cursor
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def products(self) -> list[Product]:
        """List the products with their total stock, for the order form."""
        with self._transaction(self._company) as cursor:
            cursor.execute(
                "SELECT p.sku, p.name, p.price_cents, p.currency_code,"
                " COALESCE(SUM(s.quantity), 0)"
                " FROM products p LEFT JOIN stock_levels s ON s.product_id = p.id"
                " GROUP BY p.id ORDER BY p.sku"
            )
            return [
                Product(r[0], r[1], r[2], r[3], int(r[4])) for r in cursor.fetchall()
            ]

    def place(self, username: str, sku: str, quantity: int) -> PlacedOrder:
        """Write a pending order and the workflow that will process it.

        Raises:
            UnknownCustomerError: No active customer has that username.
            UnknownProductError: No product has that SKU.
        """
        now = _now()
        with self._transaction(self._company) as cursor:
            cursor.execute(
                "SELECT id FROM customers WHERE username = %s AND status = 'active'",
                (username.strip().lower(),),
            )
            customer = cursor.fetchone()
            if customer is None:
                raise UnknownCustomerError(username)
            cursor.execute(
                "SELECT id, price_cents, currency_code FROM products WHERE sku = %s",
                (sku,),
            )
            product = cursor.fetchone()
            if product is None:
                raise UnknownProductError(sku)
            product_id, price, currency = product
            cursor.execute(
                "INSERT INTO orders (customer_id, status, ordered_at, currency_code,"
                " total_cents) VALUES (%s, 'pending', %s, %s, %s)",
                (customer[0], now, currency, price * quantity),
            )
            order_id = int(cursor.lastrowid)
            cursor.execute(
                "INSERT INTO order_items (order_id, product_id, quantity,"
                " unit_price_cents) VALUES (%s, %s, %s, %s)",
                (order_id, product_id, quantity, price),
            )
        workflow_id = str(uuid.uuid4())
        with self._transaction(self._orchestrator) as cursor:
            cursor.execute(
                "INSERT INTO workflows (id, kind, order_id, status, created_at,"
                " updated_at) VALUES (%s, %s, %s, 'running', %s, %s)",
                (workflow_id, WORKFLOW_KIND, order_id, now, now),
            )
            cursor.executemany(
                "INSERT INTO workflow_steps (workflow_id, position, name, status)"
                " VALUES (%s, %s, %s, 'pending')",
                [(workflow_id, i, name) for i, name in enumerate(STEPS)],
            )
        return PlacedOrder(workflow_id, order_id)

    def workflow(self, workflow_id: str) -> WorkflowView | None:
        """Read a workflow, its steps and its order's status."""
        with self._transaction(self._orchestrator) as cursor:
            cursor.execute(
                "SELECT order_id, status FROM workflows WHERE id = %s", (workflow_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            cursor.execute(
                "SELECT name, status, detail, finished_at FROM workflow_steps"
                " WHERE workflow_id = %s ORDER BY position",
                (workflow_id,),
            )
            steps = [
                StepView(r[0], r[1], r[2], r[3].isoformat() if r[3] else None)
                for r in cursor.fetchall()
            ]
        order_id, status = int(row[0]), row[1]
        return WorkflowView(
            workflow_id, order_id, status, self._order_status(order_id), steps
        )

    def _order_status(self, order_id: int) -> str:
        """Read the status of an order."""
        with self._transaction(self._company) as cursor:
            cursor.execute("SELECT status FROM orders WHERE id = %s", (order_id,))
            row = cursor.fetchone()
        return str(row[0]) if row else "unknown"

    def order_of(self, workflow_id: str) -> int:
        """The order a workflow processes."""
        with self._transaction(self._orchestrator) as cursor:
            cursor.execute(
                "SELECT order_id FROM workflows WHERE id = %s", (workflow_id,)
            )
            row = cursor.fetchone()
        if row is None:
            raise LookupError(workflow_id)
        return int(row[0])

    def mark_step(
        self, workflow_id: str, step: str, status: str, detail: str | None = None
    ) -> None:
        """Record where a step stands."""
        finished = _now() if status in ("done", "failed", "skipped") else None
        with self._transaction(self._orchestrator) as cursor:
            cursor.execute(
                "UPDATE workflow_steps SET status = %s, detail = %s, finished_at = %s"
                " WHERE workflow_id = %s AND name = %s",
                (status, detail, finished, workflow_id, step),
            )
            cursor.execute(
                "UPDATE workflows SET updated_at = %s WHERE id = %s",
                (_now(), workflow_id),
            )

    def finish(self, workflow_id: str, *, succeeded: bool, reason: str = "") -> None:
        """Close a workflow and its order: paid, or cancelled, the rest skipped."""
        order_id = self.order_of(workflow_id)
        with self._transaction(self._orchestrator) as cursor:
            cursor.execute(
                "UPDATE workflows SET status = %s, updated_at = %s WHERE id = %s",
                ("completed" if succeeded else "failed", _now(), workflow_id),
            )
            if not succeeded:
                cursor.execute(
                    "UPDATE workflow_steps SET status = 'skipped', finished_at = %s"
                    " WHERE workflow_id = %s AND status = 'pending'",
                    (_now(), workflow_id),
                )
        with self._transaction(self._company) as cursor:
            cursor.execute(
                "UPDATE orders SET status = %s WHERE id = %s",
                ("paid" if succeeded else "cancelled", order_id),
            )
            self._audit(
                cursor, "pay" if succeeded else f"cancel: {reason}"[:40], order_id
            )

    def reserve_stock(self, order_id: int) -> str:
        """Take the ordered quantity from a warehouse holding enough of it.

        Raises:
            OutOfStockError: No warehouse holds enough.
        """
        with self._transaction(self._company) as cursor:
            item = self._item(cursor, order_id)
            cursor.execute(
                "SELECT warehouse_id, quantity FROM stock_levels WHERE product_id = %s"
                " AND quantity >= %s ORDER BY quantity DESC LIMIT 1 FOR UPDATE",
                (item["product_id"], item["quantity"]),
            )
            stock = cursor.fetchone()
            if stock is None:
                raise OutOfStockError(
                    f"Out of stock: {item['sku']} needs {item['quantity']}"
                )
            cursor.execute(
                "UPDATE stock_levels SET quantity = quantity - %s"
                " WHERE product_id = %s AND warehouse_id = %s",
                (item["quantity"], item["product_id"], stock[0]),
            )
            self._audit(cursor, "reserve stock", order_id)
        return f"{item['quantity']} x {item['sku']} from warehouse {stock[0]}"

    def issue_invoice(self, order_id: int) -> str:
        """Bill the order."""
        now = _now()
        number = invoice_number(order_id, now.year)
        with self._transaction(self._company) as cursor:
            cursor.execute(
                "INSERT INTO invoices (order_id, number, issued_at, total_cents)"
                " SELECT id, %s, %s, total_cents FROM orders WHERE id = %s",
                (number, now, order_id),
            )
            self._audit(cursor, "issue invoice", order_id)
        return number

    def capture_payment(self, order_id: int) -> str:
        """Capture the payment of the order's invoice."""
        with self._transaction(self._company) as cursor:
            cursor.execute(
                "INSERT INTO payments (invoice_id, payment_method_id, amount_cents,"
                " status, paid_at) SELECT i.id, m.id, i.total_cents, 'captured', %s"
                " FROM invoices i JOIN payment_methods m ON m.code = %s"
                " WHERE i.order_id = %s",
                (_now(), PAYMENT_METHOD, order_id),
            )
            cursor.execute(
                "SELECT total_cents, currency_code FROM orders WHERE id = %s",
                (order_id,),
            )
            total, currency = _one(cursor)
            self._audit(cursor, "capture payment", order_id)
        return f"{total / 100:.2f} {currency} by {PAYMENT_METHOD}"

    @staticmethod
    def _item(cursor: Cursor, order_id: int) -> dict[str, Any]:
        """The product and quantity of an order's single line."""
        cursor.execute(
            "SELECT oi.product_id, oi.quantity, p.sku FROM order_items oi"
            " JOIN products p ON p.id = oi.product_id WHERE oi.order_id = %s",
            (order_id,),
        )
        product_id, quantity, sku = _one(cursor)
        return {"product_id": product_id, "quantity": quantity, "sku": sku}

    @staticmethod
    def _audit(cursor: Cursor, action: str, order_id: int) -> None:
        """Leave a line in the company's audit log."""
        cursor.execute(
            "INSERT INTO audit_logs (actor, action, entity, entity_id, logged_at)"
            " VALUES (%s, %s, 'orders', %s, %s)",
            (ACTOR, action, order_id, _now()),
        )
