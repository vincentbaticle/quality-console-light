"""The API against the Bank Partner as Microcks replays it from captured examples."""

from fastapi.testclient import TestClient
import pytest

from company_db import DatabaseSettings
from hello_api.main import create_app
from tests.metadata import metadata_test
from tests.story import ADA_BALANCE_CENTS, ADA_BALANCE_TEXT, NO_ACCOUNT_USERNAME

pytestmark = [
    pytest.mark.integration,
    metadata_test(
        system="storefront",
        product="customer-welcome",
        business_capability="engage",
        component="hello-api",
        group="partners-squad",
        testing_scope="contract",
        tags="microcks",
    ),
]


UNREACHABLE_BANK_URL = "http://127.0.0.1:9"
"""A bank nobody listens for: the discard port, refused on any machine."""


def test_greeting_carries_the_balance_the_bank_answered(api: TestClient) -> None:
    response = api.get("/api/hello", params={"username": "ada"})

    assert response.status_code == 200
    assert response.json() == {
        "message": "Hello Ada! You are visitor number 1. "
        f"Your balance is {ADA_BALANCE_TEXT}.",
        "visits": 1,
        "balance_cents": ADA_BALANCE_CENTS,
    }


def test_customer_without_account_is_greeted_without_balance(
    api: TestClient,
) -> None:
    response = api.get("/api/hello", params={"username": NO_ACCOUNT_USERNAME})

    assert response.status_code == 200
    assert response.json() == {
        "message": "Hello Zoe! You are visitor number 1.",
        "visits": 1,
        "balance_cents": None,
    }


def test_bank_out_of_reach_is_a_bad_gateway(
    redis_url: str, database: DatabaseSettings, broker: str
) -> None:
    app = create_app(redis_url, UNREACHABLE_BANK_URL, database, broker)

    with TestClient(app) as client:
        response = client.get("/api/hello", params={"username": "ada"})

    assert response.status_code == 502
