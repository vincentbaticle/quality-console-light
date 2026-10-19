"""Pure greeting rules: no Docker, no network, milliseconds."""

import pytest

from hello_api.greeting import build_greeting, format_amount, visits_key
from tests.metadata import metadata_test

pytestmark = [
    pytest.mark.unit,
    metadata_test(
        system="storefront",
        product="customer-welcome",
        business_capability="engage",
        component="hello-api",
        group="storefront-squad",
        testing_scope="unit",
    ),
]


def test_greeting_names_the_customer_the_count_and_the_balance() -> None:
    assert (
        build_greeting("Ada", 3, "12.50 EUR")
        == "Hello Ada! You are visitor number 3. Your balance is 12.50 EUR."
    )


def test_greeting_without_account_says_nothing_about_money() -> None:
    assert build_greeting("Ada", 1, None) == "Hello Ada! You are visitor number 1."


@pytest.mark.parametrize(
    ("cents", "expected"),
    [(123456, "1234.56 EUR"), (5, "0.05 EUR"), (100, "1.00 EUR"), (0, "0.00 EUR")],
)
def test_amount_keeps_two_decimals(cents: int, expected: str) -> None:
    assert format_amount(cents, "EUR") == expected


def test_visits_key_ignores_case_and_spaces() -> None:
    assert visits_key(" Ada ") == visits_key("ada") == "visits:ada"
