"""The company database, loaded from ``db/`` into whatever MySQL the tests got.

The same two scripts feed ``docker-compose.yml`` and the tests: the schema of the
30 tables, then about ten rows in each. Loading them through a client rather
than mounting them in the container is what lets the same code fill a CI
sidecar, which nothing can mount into.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
import time

import pymysql
from pymysql.constants import CLIENT

from company_db import DatabaseSettings, connect
from tests.neighbours import MYSQL_ROOT_PASSWORD, PROJECT_ROOT

DATABASE_NAME = "mycompany"
"""Name of the company database, as in ``docker-compose.yml``."""

ROOT_USER = "root"
"""Account the tests load the scripts with and hand to the API."""

IDENTITY_DATABASE = "identity"
"""Database of the simulated Auth0 tenant, ``db/06-identity.sql``."""

READER_USER = "console_reader"
"""Read-only account ``db/03-console-reader.sql`` creates for the Quality Console."""

READER_PASSWORD = "reader"
"""Password of that account, on a server that lives and dies with the session."""

SEEDED_ROWS = 10
"""Rows ``db/02-seed.sql`` writes in each table, the ones tests name."""

ROW_COUNTS = {
    "customers": 64,
    "customer_addresses": 87,
    "customer_preferences": 64,
    "bank_accounts": 58,
    "bank_transactions": 113,
    "suppliers": 23,
    "products": 47,
    "stock_levels": 94,
    "orders": 76,
    "order_items": 113,
    "invoices": 70,
    "payments": 68,
    "shipments": 71,
    "returns": 19,
    "promotions": 15,
    "coupons": 42,
    "reviews": 101,
    "employees": 33,
    "support_tickets": 52,
    "ticket_messages": 113,
    "newsletters": 12,
    "newsletter_subscriptions": 88,
    "audit_logs": 113,
}
"""Rows of each table once ``db/02b-volume.sql`` adds its generated ones; every
other table keeps the ``SEEDED_ROWS`` of the seed."""

SCRIPTS = sorted((PROJECT_ROOT / "db").glob("*.sql"))
"""Schema, seed, then the read-only account: the file names carry the order."""

READINESS_TIMEOUT_SECONDS = 120
"""Budget for MySQL to accept a login, generous enough for a cold CI runner."""

READINESS_POLL_SECONDS = 1.0
"""Delay between two login attempts while MySQL initialises."""


def wait_until_ready(host: str, port: int) -> None:
    """Log in until MySQL accepts it: an open port is not a ready server.

    Args:
        host: Host MySQL is reachable on.
        port: Port MySQL is reachable on.

    Raises:
        RuntimeError: When MySQL never accepted a login in time.
    """
    deadline = time.monotonic() + READINESS_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            pymysql.connect(
                host=host, port=port, user=ROOT_USER, password=MYSQL_ROOT_PASSWORD
            ).close()
        except pymysql.err.OperationalError:
            time.sleep(READINESS_POLL_SECONDS)
        else:
            return
    raise RuntimeError(f"MySQL at {host}:{port} not ready")


def load_company_database(host: str, port: int) -> DatabaseSettings:
    """Create the company database from scratch and fill it.

    Args:
        host: Host MySQL is reachable on.
        port: Port MySQL is reachable on.

    Returns:
        The settings the API needs to read that database.
    """
    wait_until_ready(host, port)
    with (
        pymysql.connect(
            host=host,
            port=port,
            user=ROOT_USER,
            password=MYSQL_ROOT_PASSWORD,
            client_flag=CLIENT.MULTI_STATEMENTS,
            autocommit=True,
        ) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(f"DROP DATABASE IF EXISTS {DATABASE_NAME}")
        cursor.execute(f"CREATE DATABASE {DATABASE_NAME}")
        cursor.execute(f"USE {DATABASE_NAME}")
        for script in SCRIPTS:
            cursor.execute(script.read_text())
            while cursor.nextset():
                pass
    return DatabaseSettings(
        host=host,
        port=port,
        user=ROOT_USER,
        password=MYSQL_ROOT_PASSWORD,
        name=DATABASE_NAME,
    )


def reader_settings(settings: DatabaseSettings) -> DatabaseSettings:
    """Same database, seen through the Quality Console's read-only account.

    Args:
        settings: The settings ``load_company_database`` returned.

    Returns:
        The settings of the read-only account.
    """
    return replace(settings, user=READER_USER, password=READER_PASSWORD)


WRITTEN_TABLES = ("payments", "invoices", "order_items", "orders", "audit_logs")
"""Tables the order workflow adds rows to, children before parents."""


@contextmanager
def restored(settings: DatabaseSettings) -> Iterator[None]:
    """Put the company data back as it was once the block is over.

    The order workflow adds rows and takes stock. The database is loaded once
    per session and other tests count its rows, so a test placing orders
    removes what it added and gives the stock back.

    Args:
        settings: The settings ``load_company_database`` returned.
    """
    with connect(settings) as connection, connection.cursor() as cursor:
        highest = {}
        for table in WRITTEN_TABLES:
            cursor.execute(f"SELECT COALESCE(MAX(id), 0) FROM {table}")  # noqa: S608
            row = cursor.fetchone()
            assert row is not None
            highest[table] = row[0]
        cursor.execute("SELECT product_id, warehouse_id, quantity FROM stock_levels")
        stock = cursor.fetchall()
    yield
    with connect(settings) as connection, connection.cursor() as cursor:
        for table in WRITTEN_TABLES:
            cursor.execute(f"DELETE FROM {table} WHERE id > %s", (highest[table],))  # noqa: S608
        cursor.executemany(
            "UPDATE stock_levels SET quantity = %s"
            " WHERE product_id = %s AND warehouse_id = %s",
            [(quantity, product, warehouse) for product, warehouse, quantity in stock],
        )
        connection.commit()
