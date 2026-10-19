"""Account access: sign-in, and the emails of the tenant read from the QA mailbox."""

import uuid

import httpx
from playwright.sync_api import Page, expect
import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from identity.rules import plus_address
from tests.acceptance.conftest import Context, Stack
from tests.authenticator import AUTHENTICATORS, codes
from tests.mailbox import MAILBOX, ticket_of, wait_for_email
from tests.metadata import metadata_test

pytestmark = [
    pytest.mark.acceptance,
    metadata_test(
        system="identity",
        product="account-access",
        business_capability="protect",
        component="identity-service",
        group="qa-web",
        testing_scope="acceptance",
        tags="mailbox",
    ),
]

scenarios("account-access")


def identity(stack: Stack, path: str, body: dict[str, str]) -> httpx.Response:
    """Call the tenant through the storefront, as the page does."""
    return httpx.post(f"{stack.storefront}/api/identity/{path}", json=body)


@given("a new address of the QA mailbox")
def new_address(context: Context) -> None:
    context.values["address"] = plus_address(MAILBOX, f"bdd-{uuid.uuid4().hex[:8]}")


@when(parsers.parse('"{email}" signs in with "{password}"'))
def sign_in_as(stack: Stack, context: Context, email: str, password: str) -> None:
    context.values["email"] = email
    context.response = identity(stack, "login", {"email": email, "password": password})


@when("the customer sends the code of their authenticator app")
def send_code(stack: Stack, context: Context) -> None:
    assert context.response is not None
    token = context.response.json()["mfa_token"]
    for code in codes(AUTHENTICATORS[context.values["email"]]):
        context.response = identity(
            stack, "mfa/verify", {"mfa_token": token, "code": code}
        )
        if context.response.status_code == 200:
            break


@then("the sign-in is accepted")
def sign_in_accepted(context: Context) -> None:
    assert context.response is not None
    assert context.response.status_code == 200, context.response.text


@then(parsers.parse('the tenant answers {status:d} "{detail}"'))
def tenant_answers(context: Context, status: int, detail: str) -> None:
    assert context.response is not None
    assert (context.response.status_code, context.response.json()["detail"]) == (
        status,
        detail,
    )


@when("the customer creates an account with it")
def create_account(stack: Stack, context: Context) -> None:
    response = identity(stack, "signup", {"email": context.values["address"]})
    assert response.status_code == 201, response.text


@then(parsers.parse('the mailbox receives "{subject}" for that address'))
def mailbox_receives(stack: Stack, context: Context, subject: str) -> None:
    address = context.values["address"]
    context.values["email"] = wait_for_email(stack.mailbox, address, subject)


@then("the email holds a password link")
def email_holds_a_link(context: Context) -> None:
    assert ticket_of(context.values["email"].link)


@when(parsers.parse('the customer sets "{password}" from the link of "{subject}"'))
def set_password(stack: Stack, context: Context, password: str, subject: str) -> None:
    email = wait_for_email(stack.mailbox, context.values["address"], subject)
    context.values["ticket"] = ticket_of(email.link)
    response = identity(
        stack, "password", {"ticket": context.values["ticket"], "password": password}
    )
    assert response.status_code == 204, response.text


@then(parsers.parse('setting "{password}" from the same link is refused'))
def link_is_single_use(stack: Stack, context: Context, password: str) -> None:
    response = identity(
        stack, "password", {"ticket": context.values["ticket"], "password": password}
    )
    assert response.status_code == 400


@then(parsers.parse('the customer signs in with "{password}"'))
def signs_in(stack: Stack, context: Context, password: str) -> None:
    body = {"email": context.values["address"], "password": password}
    assert identity(stack, "login", body).status_code == 200


@then(parsers.parse('the customer cannot sign in with "{password}"'))
def cannot_sign_in(stack: Stack, context: Context, password: str) -> None:
    body = {"email": context.values["address"], "password": password}
    assert identity(stack, "login", body).status_code == 423


@when("the customer asks to reset the password")
def ask_reset(stack: Stack, context: Context) -> None:
    body = {"email": context.values["address"]}
    assert identity(stack, "password-reset", body).status_code == 202


@when(parsers.parse('the customer signs in {times:d} times with "{password}"'))
def sign_in_many_times(
    stack: Stack, context: Context, times: int, password: str
) -> None:
    body = {"email": context.values["address"], "password": password}
    for _ in range(times):
        identity(stack, "login", body)


@given(parsers.parse('a new account of the QA mailbox whose password is "{password}"'))
def new_account_with_password(stack: Stack, context: Context, password: str) -> None:
    new_address(context)
    create_account(stack, context)
    set_password(stack, context, password, "choose your password")


@when(parsers.parse('the customer signs in on the storefront page with "{password}"'))
def sign_in_on_page(stack: Stack, context: Context, page: Page, password: str) -> None:
    page.goto(f"{stack.storefront}/#account")
    account = page.get_by_role("region", name="Account access")
    account.get_by_label("Email", exact=True).fill(context.values["address"])
    account.get_by_label("Password", exact=True).fill(password)
    account.get_by_role("button", name="Sign in", exact=True).click()


@then("the page says the customer is signed in")
def page_says_signed_in(context: Context, page: Page) -> None:
    status = page.get_by_role("region", name="Account access").get_by_role("status")
    expect(status).to_contain_text(f"Signed in as {context.values['address']}")
