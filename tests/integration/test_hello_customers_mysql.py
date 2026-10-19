"""The API against the real company database: only active customers are greeted."""

from fastapi.testclient import TestClient
import pymysql
import pytest
from redis import Redis

from company_db import DatabaseSettings
from tests.database import ROW_COUNTS, SEEDED_ROWS
from tests.metadata import metadata_test
from tests.story import CLOSED_USERNAME, UNKNOWN_USERNAME

pytestmark = [
    pytest.mark.integration,
    metadata_test(
        system="storefront",
        product="customer-welcome",
        business_capability="engage",
        component="hello-api",
        group="storefront-squad",
        testing_scope="integration",
        tags="mysql",
    ),
]


MAX_ROWS = 113
"""No table of the company database holds more rows."""

COMPANY_TABLES = 30
"""Tables of ``db/01-schema.sql``: the API reads one, the bank another."""


def test_customer_is_greeted_by_the_first_name_in_the_database(
    api: TestClient,
) -> None:
    response = api.get("/api/hello", params={"username": "grace"})

    assert response.status_code == 200
    assert response.json()["message"].startswith("Hello Grace! ")


def test_closed_customer_is_refused_and_not_counted(
    api: TestClient, redis_client: Redis
) -> None:
    response = api.get("/api/hello", params={"username": CLOSED_USERNAME})

    assert response.status_code == 404
    assert response.json() == {"detail": "Unknown customer"}
    assert redis_client.get(f"visits:{CLOSED_USERNAME}") is None


def test_unknown_username_is_refused(api: TestClient) -> None:
    response = api.get("/api/hello", params={"username": UNKNOWN_USERNAME})

    assert response.status_code == 404


def test_company_database_is_loaded_in_full(database: DatabaseSettings) -> None:
    with (
        pymysql.connect(
            host=database.host,
            port=database.port,
            user=database.user,
            password=database.password,
            database=database.name,
        ) as connection,
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = %s",
            (database.name,),
        )
        tables = [row[0] for row in cursor.fetchall()]
        row_counts = {}
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")  # noqa: S608
            count_row = cursor.fetchone()
            assert count_row is not None
            row_counts[table] = count_row[0]

    assert len(tables) == COMPANY_TABLES
    assert row_counts == {t: ROW_COUNTS.get(t, SEEDED_ROWS) for t in tables}
    assert max(row_counts.values()) == MAX_ROWS
