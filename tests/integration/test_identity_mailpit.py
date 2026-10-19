"""The simulated Auth0 tenant against a real MySQL and a real mailbox (Mailpit).

Each test signs up its own account, a plus tag of the QA mailbox, so tests
never share a user, and reads the emails the tenant really sent.
"""

import time
import uuid

from fastapi.testclient import TestClient
import pyotp
import pytest

from identity.rules import MAX_FAILED_LOGINS, plus_address
from identity.tenant import MFA_REQUIRED, WRONG_CODE
from tests.authenticator import fresh_code
from tests.mailbox import MAILBOX, emails_to, ticket_of, wait_for_email
from tests.metadata import metadata_test
from tests.story import MANAGEMENT_TOKEN, PUBLIC_URL

pytestmark = [
    pytest.mark.integration,
    metadata_test(
        system="identity",
        product="account-access",
        business_capability="protect",
        component="identity-service",
        group="identity-squad",
        testing_scope="integration",
        tags="mysql, mailbox",
    ),
]

PASSWORD = "Foundation-2026"
"""A password the policy accepts."""

WELCOME = "choose your password"
"""Part of the subject of the email a new account receives."""


def new_address() -> str:
    """An address of the QA mailbox nobody used yet."""
    return plus_address(MAILBOX, f"test-{uuid.uuid4().hex[:8]}")


def signed_up(identity: TestClient, mailbox: str, address: str) -> None:
    """Sign up and set the password through the welcome email, as a user does."""
    assert (
        identity.post("/api/identity/signup", json={"email": address}).status_code
        == 201
    )
    link = wait_for_email(mailbox, address, WELCOME).link
    response = identity.post(
        "/api/identity/password", json={"ticket": ticket_of(link), "password": PASSWORD}
    )
    assert response.status_code == 204


def test_sign_up_sends_the_set_password_email(
    identity: TestClient, mailbox: str
) -> None:
    address = new_address()

    response = identity.post("/api/identity/signup", json={"email": address})

    assert response.status_code == 201
    assert response.json()["user_id"].startswith("auth0|")
    email = wait_for_email(mailbox, address, WELCOME)
    assert email.link.startswith(f"{PUBLIC_URL}/?ticket=")


def test_no_sign_in_before_the_password_is_set(
    identity: TestClient, mailbox: str
) -> None:
    address = new_address()
    identity.post("/api/identity/signup", json={"email": address})

    response = identity.post(
        "/api/identity/login", json={"email": address, "password": PASSWORD}
    )

    assert response.status_code == 403


def test_sign_in_with_the_password_set_from_the_email(
    identity: TestClient, mailbox: str
) -> None:
    address = new_address()
    signed_up(identity, mailbox, address)

    response = identity.post(
        "/api/identity/login", json={"email": address, "password": PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["email"] == address


def test_the_link_works_once(identity: TestClient, mailbox: str) -> None:
    address = new_address()
    identity.post("/api/identity/signup", json={"email": address})
    ticket = ticket_of(wait_for_email(mailbox, address, WELCOME).link)
    body = {"ticket": ticket, "password": PASSWORD}

    first = identity.post("/api/identity/password", json=body)
    second = identity.post("/api/identity/password", json=body)

    assert first.status_code == 204
    assert second.status_code == 400


def test_a_weak_password_is_refused_and_says_why(
    identity: TestClient, mailbox: str
) -> None:
    address = new_address()
    identity.post("/api/identity/signup", json={"email": address})
    ticket = ticket_of(wait_for_email(mailbox, address, WELCOME).link)

    response = identity.post(
        "/api/identity/password", json={"ticket": ticket, "password": "short"}
    )

    assert response.status_code == 422
    assert "an uppercase letter" in response.json()["detail"]


def test_the_email_reaches_the_lowercase_address_whatever_was_typed(
    identity: TestClient, mailbox: str
) -> None:
    address = new_address()

    identity.post("/api/identity/signup", json={"email": address.upper()})

    assert wait_for_email(mailbox, address, WELCOME).to == address


def test_reset_sends_a_link_and_says_the_same_for_an_unknown_account(
    identity: TestClient, mailbox: str
) -> None:
    address = new_address()
    signed_up(identity, mailbox, address)

    known = identity.post("/api/identity/password-reset", json={"email": address})
    unknown = identity.post(
        "/api/identity/password-reset", json={"email": new_address()}
    )

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert wait_for_email(mailbox, address, "Reset your").link


def test_ten_wrong_passwords_block_the_account_and_send_an_unblock_email(
    identity: TestClient, mailbox: str
) -> None:
    address = new_address()
    signed_up(identity, mailbox, address)
    wrong = {"email": address, "password": "Wrong-password-1"}

    answers = [
        identity.post("/api/identity/login", json=wrong).status_code
        for _ in range(MAX_FAILED_LOGINS)
    ]

    assert answers == [401] * (MAX_FAILED_LOGINS - 1) + [423]
    right = identity.post(
        "/api/identity/login", json={"email": address, "password": PASSWORD}
    )
    assert right.status_code == 423
    link = wait_for_email(mailbox, address, "blocked").link
    identity.post(
        "/api/identity/password", json={"ticket": ticket_of(link), "password": PASSWORD}
    )
    unblocked = identity.post(
        "/api/identity/login", json={"email": address, "password": PASSWORD}
    )
    assert unblocked.status_code == 200


def test_management_ticket_gives_a_link_without_any_email(
    identity: TestClient, mailbox: str
) -> None:
    address = new_address()
    signed_up(identity, mailbox, address)
    before = len(emails_to(mailbox, address))

    response = identity.post(
        "/api/identity/management/tickets/password-change",
        json={"email": address},
        headers={"Authorization": f"Bearer {MANAGEMENT_TOKEN}"},
    )

    assert response.status_code == 201
    assert response.json()["ticket"].startswith(f"{PUBLIC_URL}/?ticket=")
    assert len(emails_to(mailbox, address)) == before


def test_management_api_refuses_a_call_without_its_token(
    identity: TestClient, mailbox: str
) -> None:
    response = identity.post(
        "/api/identity/management/tickets/password-change",
        json={"email": new_address()},
    )

    assert response.status_code == 401


def test_a_seeded_blocked_account_cannot_sign_in(identity: TestClient) -> None:
    response = identity.post(
        "/api/identity/login",
        json={"email": "qa-mailbox+grace@mycompany.test", "password": "Ultrabook-2026"},
    )

    assert response.status_code == 423


def enrolled(identity: TestClient, mailbox: str, address: str) -> str:
    """Sign up, set the password, add a second factor: give its TOTP secret."""
    signed_up(identity, mailbox, address)
    credentials = {"email": address, "password": PASSWORD}
    response = identity.post("/api/identity/mfa/enroll", json=credentials)
    assert response.status_code == 201
    return str(response.json()["secret"])


def mfa_token(identity: TestClient, address: str) -> str:
    """Sign in with the password, which asks for the code: give its token."""
    response = identity.post(
        "/api/identity/login", json={"email": address, "password": PASSWORD}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == MFA_REQUIRED
    return str(response.json()["mfa_token"])


def test_a_second_factor_asks_for_the_code_then_signs_in(
    identity: TestClient, mailbox: str
) -> None:
    address = new_address()
    secret = enrolled(identity, mailbox, address)

    response = identity.post(
        "/api/identity/mfa/verify",
        json={"mfa_token": mfa_token(identity, address), "code": fresh_code(secret)},
    )

    assert response.status_code == 200
    assert response.json()["email"] == address


def test_a_code_signs_in_once(identity: TestClient, mailbox: str) -> None:
    address = new_address()
    code = fresh_code(enrolled(identity, mailbox, address))
    first = {"mfa_token": mfa_token(identity, address), "code": code}
    replay = {"mfa_token": mfa_token(identity, address), "code": code}

    assert identity.post("/api/identity/mfa/verify", json=first).status_code == 200
    response = identity.post("/api/identity/mfa/verify", json=replay)

    assert response.status_code == 401
    assert response.json()["detail"] == WRONG_CODE


def test_an_old_code_is_refused(identity: TestClient, mailbox: str) -> None:
    address = new_address()
    totp = pyotp.TOTP(enrolled(identity, mailbox, address))
    ten_steps_ago = totp.at(time.time() - 10 * totp.interval)

    response = identity.post(
        "/api/identity/mfa/verify",
        json={"mfa_token": mfa_token(identity, address), "code": ten_steps_ago},
    )

    assert response.status_code == 401


def test_a_second_factor_is_added_once(identity: TestClient, mailbox: str) -> None:
    address = new_address()
    enrolled(identity, mailbox, address)

    response = identity.post(
        "/api/identity/mfa/enroll", json={"email": address, "password": PASSWORD}
    )

    assert response.status_code == 409
