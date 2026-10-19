"""Quality Console: the platform is listed and its data browsable, read-only."""

import httpx
import pytest
from pytest_bdd import parsers, scenarios, then, when

from tests.acceptance.conftest import Context, Stack
from tests.metadata import metadata_test

pytestmark = [
    pytest.mark.acceptance,
    metadata_test(
        system="quality",
        product="quality-console",
        business_capability="operate",
        component="quality-console",
        group="qa-core",
        testing_scope="acceptance",
    ),
]

scenarios("quality-console")


@when(parsers.parse('I open the console page "{path}"'))
def open_page(stack: Stack, context: Context, path: str) -> None:
    context.response = httpx.get(f"{stack.console}{path}")


@then(parsers.parse('the page shows "{text}"'))
def page_shows(context: Context, text: str) -> None:
    assert context.response is not None
    assert context.response.status_code == 200
    assert text in context.response.text
