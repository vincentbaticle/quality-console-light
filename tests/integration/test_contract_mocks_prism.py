"""The contract mocks: Prism serving every OpenAPI contract of ``contracts/``.

A contract published in ``contracts/`` is a mock, with nothing else written:
Prism answers from the contract's schemas and examples, and checks each
request against the contract. The Bank Partner's captured examples stay in
Microcks, which picks the answer by request; Prism does not.
"""

import httpx
import pytest

from catalog.model import load_catalog
from quality_console.tools.apis import mock_name
from tests.metadata import metadata_test
from tests.neighbours import PROJECT_ROOT

pytestmark = [
    pytest.mark.integration,
    metadata_test(
        system="quality",
        product="quality-console",
        business_capability="operate",
        component="quality-console",
        group="qa-core",
        testing_scope="integration",
        tags="prism",
    ),
]

BANK_KEY = {"X-Api-Key": "any-key-the-contract-asks-for"}
"""The Bank Partner's contract asks for a key; Prism only checks it is there."""


def test_every_openapi_contract_of_the_catalog_is_a_mock(mocks_url: str) -> None:
    catalog = load_catalog(PROJECT_ROOT / "catalog" / "catalog.yaml")
    expected = {
        name for api in catalog.apis if (name := mock_name(api.definition)) is not None
    }

    listed = httpx.get(f"{mocks_url}/").json()["mocks"]

    assert {mock["name"] for mock in listed} == expected
    assert "order-workflow" not in expected


def test_the_bank_partner_mock_answers_the_shape_of_its_contract(
    mocks_url: str,
) -> None:
    answer = httpx.get(
        f"{mocks_url}/bank-partner/balance",
        params={"username": "ada"},
        headers=BANK_KEY,
    )

    assert answer.status_code == 200
    assert set(answer.json()) == {"username", "balance_cents", "currency"}


def test_the_mock_refuses_a_request_its_contract_refuses(mocks_url: str) -> None:
    no_key = httpx.get(f"{mocks_url}/bank-partner/balance", params={"username": "ada"})
    no_username = httpx.get(f"{mocks_url}/bank-partner/balance", headers=BANK_KEY)
    unknown = httpx.get(f"{mocks_url}/nobody/anything")

    assert no_key.status_code == 401
    assert no_username.status_code == 422
    assert no_username.json()["validation"][0]["code"] == "required"
    assert unknown.status_code == 404
