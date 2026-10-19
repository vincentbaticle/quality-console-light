"""The steps of the order workflow, in order, and the rules they apply."""

STEPS = ("reserve_stock", "issue_invoice", "capture_payment")
"""What happens to an order once placed, one event each, in this order."""

WORKFLOW_KIND = "place_order"
"""Kind of workflow recorded in the orchestrator, for any later kind."""

MAX_QUANTITY = 5
"""Most items of one product an order may hold."""

ORCHESTRATOR_DATABASE = "orchestrator"
"""Database holding the workflows and their steps, beside the company one."""


def next_step(step: str) -> str | None:
    """Name the step after a given one, None after the last.

    Args:
        step: A step of ``STEPS``.

    Returns:
        The following step, or None when the workflow is over.
    """
    position = STEPS.index(step)
    return STEPS[position + 1] if position + 1 < len(STEPS) else None


def invoice_number(order_id: int, year: int) -> str:
    """Number an invoice the way the company does: ``INV-<year>-<order id>``.

    Args:
        order_id: Order the invoice bills.
        year: Year of issue.

    Returns:
        The invoice number, the order id zero-padded to six digits.
    """
    return f"INV-{year}-{order_id:06d}"
