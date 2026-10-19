"""Customer welcome: a returning customer is greeted, counted and shown a balance.

The load baseline runs k6 (``perf/customer-welcome-baseline.js``) and reads the
summary it writes, the same file a load test job files in Test results.
"""

from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import httpx
from playwright.sync_api import Page, expect
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from hello_api.bank_partner import API_KEY_HEADER
from test_results.k6 import SUMMARY_FILE, parse_k6_summary
from tests.acceptance.conftest import Context, Stack
from tests.metadata import metadata_test
from tests.neighbours import PROJECT_ROOT

pytestmark = [
    pytest.mark.acceptance,
    metadata_test(
        system="storefront",
        product="customer-welcome",
        business_capability="engage",
        component="hello-api",
        group="qa-web",
        testing_scope="acceptance",
    ),
]

scenarios("customer-welcome")

K6_TIMEOUT_SECONDS = 120
"""Budget of one k6 run, its stages last 30 seconds."""

VISIT_NUMBER = re.compile(r"visitor number (\d+)")
"""Where the greeting says which visit this is."""


@when(parsers.parse('"{username}" asks for a greeting'))
@when(parsers.parse('"{username}" asks for a greeting again'))
def ask_greeting(stack: Stack, context: Context, username: str) -> None:
    context.response = httpx.get(
        f"{stack.storefront}/api/hello", params={"username": username}
    )
    if context.response.is_success:
        context.values.setdefault("greetings", []).append(
            context.response.json()["message"]
        )


@then(parsers.parse('the greeting starts with "{start}"'))
def greeting_starts_with(context: Context, start: str) -> None:
    assert context.values["greetings"][-1].startswith(start)


@then("the greeting shows a balance in EUR")
def greeting_shows_a_balance(context: Context) -> None:
    assert context.values["greetings"][-1].endswith(" EUR.")


@then("the greeting shows no balance")
def greeting_shows_no_balance(context: Context) -> None:
    assert "balance" not in context.values["greetings"][-1]


@then("the second visit number is one more than the first")
def visit_is_counted(context: Context) -> None:
    first, second = (
        int(VISIT_NUMBER.search(g).group(1))  # type: ignore[union-attr]
        for g in context.values["greetings"][-2:]
    )
    assert second == first + 1


@when(parsers.parse('k6 plays "{script}" against the storefront'))
def k6_plays(stack: Stack, context: Context, script: str) -> None:
    k6 = shutil.which("k6")
    if k6 is None:
        pytest.skip("k6 is not installed: mise install")
    with tempfile.TemporaryDirectory() as reports:
        subprocess.run(  # noqa: S603
            [
                k6,
                "run",
                "--quiet",
                "-e",
                f"BASE_URL={stack.storefront}",
                "-e",
                f"REPORTS_DIR={reports}",
                str(PROJECT_ROOT / "perf" / script),
            ],
            check=False,
            capture_output=True,
            timeout=K6_TIMEOUT_SECONDS,
        )
        context.values["load"] = parse_k6_summary(
            (Path(reports) / SUMMARY_FILE).read_text()
        )


@then(parsers.parse("less than {percent:d} percent of the calls fail"))
def few_calls_fail(context: Context, percent: int) -> None:
    assert context.values["load"].error_rate < percent / 100, context.values["load"]


@then(parsers.parse("95 percent of the greetings answer within {limit:d} ms"))
def greetings_are_fast(context: Context, limit: int) -> None:
    assert context.values["load"].duration_p95 < limit, context.values["load"]


@given(parsers.parse('the partner bank holds an account for "{username}"'))
def bank_holds_account(stack: Stack, partner_api_key: str, username: str) -> None:
    response = httpx.get(
        f"{stack.partner}/balance",
        params={"username": username},
        headers={API_KEY_HEADER: partner_api_key},
    )
    assert response.status_code == 200, response.text


@when(parsers.parse('"{username}" greets themselves on the storefront page'))
def greet_on_page(stack: Stack, page: Page, username: str) -> None:
    page.goto(f"{stack.storefront}/#welcome")
    welcome = page.get_by_role("region", name="Customer welcome")
    welcome.get_by_label("Your username").fill(username)
    welcome.get_by_role("button", name="Say hello").click()


@then(parsers.parse('the page greets "{first_name}" with a balance in EUR'))
def page_greets(page: Page, first_name: str) -> None:
    status = page.get_by_role("region", name="Customer welcome").get_by_role("status")
    expect(status).to_contain_text(f"Hello {first_name}!")
    expect(status).to_contain_text(" EUR.")
