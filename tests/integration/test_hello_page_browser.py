"""A real browser on the real storefront, calling the real APIs and neighbours."""

from playwright.sync_api import Page, expect
import pytest

from tests.authenticator import LIN_EMAIL, LIN_TOTP_SECRET, codes
from tests.metadata import metadata_test
from tests.story import ADA_BALANCE_TEXT

pytestmark = [
    pytest.mark.integration,
    metadata_test(
        system="storefront",
        product="customer-welcome",
        business_capability="engage",
        component="front",
        group="qa-web",
        testing_scope="e2e",
        tags="smoke",
    ),
]


def test_user_is_greeted_and_counted(stack_url: str, page: Page) -> None:
    page.goto(stack_url)
    page.get_by_role("link", name="Customer welcome").first.click()
    welcome = page.get_by_role("region", name="Customer welcome")

    welcome.get_by_label("Your username").fill("ada")
    welcome.get_by_role("button", name="Say hello").click()
    expect(welcome.get_by_role("status")).to_have_text(
        f"Hello Ada! You are visitor number 1. Your balance is {ADA_BALANCE_TEXT}."
    )

    welcome.get_by_role("button", name="Say hello").click()
    expect(welcome.get_by_role("status")).to_have_text(
        f"Hello Ada! You are visitor number 2. Your balance is {ADA_BALANCE_TEXT}."
    )


@metadata_test(
    system="orders",
    product="checkout",
    business_capability="sell",
    component="front",
    group="qa-web",
    testing_scope="e2e",
    tags="smoke",
)
def test_an_order_is_followed_until_paid(stack_url: str, page: Page) -> None:
    page.goto(f"{stack_url}/#checkout")
    checkout = page.get_by_role("region", name="Checkout")

    checkout.get_by_role("button", name="ada buys Foundation").click()

    status = checkout.get_by_role("status")
    expect(status).to_contain_text("workflow completed")
    expect(status).to_contain_text("paid")
    expect(checkout.get_by_role("list", name="Workflow steps")).to_contain_text(
        "Capture payment · done"
    )


@metadata_test(
    system="identity",
    product="account-access",
    business_capability="protect",
    component="front",
    group="qa-web",
    testing_scope="e2e",
    tags="smoke",
)
def test_a_customer_signs_in_and_a_blocked_one_is_told_why(
    stack_url: str, page: Page
) -> None:
    page.goto(f"{stack_url}/#account")
    account = page.get_by_role("region", name="Account access")

    account.get_by_role("button", name="ada", exact=True).click()
    expect(account.get_by_role("status")).to_contain_text(
        "Signed in as qa-mailbox+ada@mycompany.test"
    )

    account.get_by_role("button", name="grace", exact=True).click()
    expect(account.get_by_role("status")).to_contain_text("Account blocked")
    expect(page.get_by_role("region", name="Checkout")).to_be_hidden()

    account.get_by_role("link", name="All products").click()
    expect(page.get_by_role("region", name="Pick a product")).to_be_visible()
    expect(account).to_be_hidden()


@metadata_test(
    system="identity",
    product="account-access",
    business_capability="protect",
    component="front",
    group="qa-web",
    testing_scope="e2e",
    tags="smoke, mfa",
)
def test_a_customer_signs_in_with_the_code_of_an_authenticator_app(
    stack_url: str, page: Page
) -> None:
    page.goto(f"{stack_url}/#account")
    account = page.get_by_role("region", name="Account access")
    second_factor = account.get_by_role("form", name="Second factor")

    account.get_by_role("button", name="lin", exact=True).click()
    expect(second_factor).to_be_visible()

    for code in codes(LIN_TOTP_SECRET):
        second_factor.get_by_label("Authenticator code").fill(code)
        with page.expect_response("**/api/identity/mfa/verify") as answer:
            second_factor.get_by_role("button", name="Verify").click()
        if answer.value.ok:
            break

    expect(account.get_by_role("status")).to_contain_text(f"Signed in as {LIN_EMAIL}")
    expect(second_factor).to_be_hidden()
