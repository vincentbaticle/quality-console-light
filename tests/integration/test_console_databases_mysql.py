"""The Quality Console against the real company database, as its read-only account."""

from fastapi.testclient import TestClient
import pymysql
import pytest

from company_db import DatabaseSettings, connect
from tests.database import reader_settings
from tests.metadata import metadata_test

pytestmark = [
    pytest.mark.integration,
    metadata_test(
        system="quality",
        product="quality-console",
        business_capability="operate",
        component="quality-console",
        group="qa-core",
        testing_scope="integration",
        tags="mysql",
    ),
]


CUSTOMERS_PAGE = "/databases/mycompany/tables/customers"
"""Table page the tests browse: every row of it is known from the seed."""


def test_databases_page_lists_what_the_account_can_read(console: TestClient) -> None:
    response = console.get("/databases")

    assert response.status_code == 200
    for name in ("mycompany", "orchestrator", "catalog", "identity"):
        assert f'href="/databases/{name}"' in response.text


def test_identity_users_are_seen_without_their_password_hash(
    console: TestClient,
) -> None:
    tables = console.get("/databases/identity")
    accounts = console.get("/databases/identity/tables/accounts")

    assert "accounts" in tables.text
    assert 'href="/databases/identity/tables/users"' not in tables.text
    assert "qa-mailbox+ada@mycompany.test" in accounts.text
    assert "pbkdf2" not in accounts.text
    assert console.get("/databases/identity/tables/users").status_code == 404


def test_database_page_lists_the_30_tables_and_their_row_counts(
    console: TestClient,
) -> None:
    response = console.get("/databases/mycompany")

    assert response.status_code == 200
    assert "30 tables" in response.text
    assert "64 rows" in response.text
    assert "113 rows" in response.text


def test_table_page_shows_the_rows(console: TestClient) -> None:
    response = console.get(CUSTOMERS_PAGE)

    assert response.status_code == 200
    assert "<td>ada@example.com</td>" in response.text
    assert "50 rows shown." in response.text


def test_contains_search_filters_the_rows(console: TestClient) -> None:
    response = console.get(
        CUSTOMERS_PAGE,
        params={"column": "first_name", "mode": "contains", "value": "ar"},
    )

    assert "<td>Margaret</td>" in response.text
    assert "<td>Barbara</td>" in response.text
    assert "<td>Ada</td>" not in response.text


def test_exact_search_finds_one_customer(console: TestClient) -> None:
    response = console.get(
        CUSTOMERS_PAGE, params={"column": "username", "mode": "exact", "value": "ada"}
    )

    assert "1 rows shown." in response.text


def test_unknown_table_is_a_404(console: TestClient) -> None:
    response = console.get("/databases/mycompany/tables/salaries")

    assert response.status_code == 404
    assert "Unknown table: salaries" in response.text


def test_unknown_column_is_a_404_not_an_injection(console: TestClient) -> None:
    response = console.get(
        CUSTOMERS_PAGE, params={"column": "1=1; DROP TABLE customers", "value": "x"}
    )

    assert response.status_code == 404


def test_console_account_cannot_write(database: DatabaseSettings) -> None:
    with (
        connect(reader_settings(database)) as connection,
        connection.cursor() as cursor,
        pytest.raises(pymysql.err.OperationalError),
    ):
        cursor.execute("DELETE FROM customers")
