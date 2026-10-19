"""What live experimentation changes, and what stays static.

The storefront products write for real: an order writes the order tables and
the workflow state, an account writes the identity users. Every other table is
loaded once at start-up and only ever read, like the reference data of a real
company's QA cockpit. The same goes for the buckets (the test results grow
with each run, the team buckets are loaded once) and for the Gherkin features
(a scenario of the checkout places real orders, one of the bucket checks only
reads). Pages tag each table, bucket and feature with its kind.
"""

LIVE_TABLES: dict[str, frozenset[str] | None] = {
    "mycompany": frozenset(
        {
            "orders",
            "order_items",
            "stock_levels",
            "invoices",
            "payments",
            "audit_logs",
        }
    ),
    "orchestrator": None,
    "identity": None,
}
"""Tables written by the storefront, per database; ``None`` means all of them."""

LIVE = "live"
"""Kind of a table the storefront writes."""

STATIC = "static"
"""Kind of a table loaded once and only read."""

MIXED = "mixed"
"""Kind of a database holding both."""

LIVE_BUCKETS = frozenset({"test-results"})
"""Buckets every test run writes to; the team buckets are loaded once."""

LIVE_FEATURES = frozenset({"customer-welcome", "checkout", "account-access"})
"""Feature folders whose scenarios write: visits, orders, accounts and emails."""


def bucket_kind(bucket: str) -> str:
    """Tell whether test runs write a bucket.

    Args:
        bucket: Its name.

    Returns:
        ``live`` or ``static``.
    """
    return LIVE if bucket in LIVE_BUCKETS else STATIC


def feature_kind(product: str) -> str:
    """Tell whether the scenarios of a feature folder write.

    Args:
        product: The folder of ``features/``, a product of the catalog.

    Returns:
        ``live`` or ``static``.
    """
    return LIVE if product in LIVE_FEATURES else STATIC


def table_kind(database: str, table: str) -> str:
    """Tell whether the storefront writes a table.

    Args:
        database: Database of the table.
        table: Its name.

    Returns:
        ``live`` or ``static``.
    """
    if database not in LIVE_TABLES:
        return STATIC
    live = LIVE_TABLES[database]
    return LIVE if live is None or table in live else STATIC


def database_kind(database: str) -> str:
    """Tell whether the storefront writes a database.

    Args:
        database: Its name.

    Returns:
        ``live``, ``static`` or ``mixed``.
    """
    if database not in LIVE_TABLES:
        return STATIC
    return LIVE if LIVE_TABLES[database] is None else MIXED
