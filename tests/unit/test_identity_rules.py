"""The rules of the simulated Auth0 tenant."""

import base64
import datetime

import pyotp
import pytest

from identity.emails import set_password_email
from identity.rules import (
    TICKET_TTL,
    InvalidEmailError,
    extract_link,
    hash_password,
    is_expired,
    new_user_id,
    normalize_email,
    password_problems,
    plus_address,
    ticket_link,
    verify_password,
)
from identity.totp import (
    matching_step,
    new_totp_secret,
    otpauth_uri,
    totp_code,
    totp_step,
)
from tests.metadata import metadata_test

pytestmark = [
    pytest.mark.unit,
    metadata_test(
        system="identity",
        product="account-access",
        business_capability="protect",
        component="identity-service",
        group="identity-squad",
        testing_scope="unit",
    ),
]


def test_email_is_stored_in_lowercase() -> None:
    assert normalize_email("  QA-Mailbox+Ada@MyCompany.TEST ") == (
        "qa-mailbox+ada@mycompany.test"
    )


@pytest.mark.parametrize("email", ["", "ada", "ada@", "ada@mycompany", "a b@c.de"])
def test_a_malformed_email_is_refused(email: str) -> None:
    with pytest.raises(InvalidEmailError):
        normalize_email(email)


def test_plus_address_keeps_the_mailbox_and_adds_the_tag() -> None:
    assert plus_address("qa-mailbox@mycompany.test", "ada") == (
        "qa-mailbox+ada@mycompany.test"
    )


def test_a_strong_password_has_no_problem() -> None:
    assert password_problems("Foundation-2026") == []


def test_a_weak_password_lists_every_missing_rule() -> None:
    assert password_problems("abc") == [
        "at least 8 characters",
        "an uppercase letter",
        "a digit",
    ]


def test_a_hashed_password_verifies_and_a_wrong_one_does_not() -> None:
    stored = hash_password("Foundation-2026")

    assert verify_password("Foundation-2026", stored)
    assert not verify_password("foundation-2026", stored)
    assert not verify_password("anything", None)


def test_two_hashes_of_one_password_differ_by_their_salt() -> None:
    assert hash_password("Foundation-2026") != hash_password("Foundation-2026")


def test_user_id_looks_like_an_auth0_database_user() -> None:
    user_id = new_user_id()

    assert user_id.startswith("auth0|")
    assert len(user_id) == len("auth0|") + 24


def test_a_ticket_expires_after_five_days() -> None:
    issued = datetime.datetime(2026, 10, 1, 9, 0)

    assert not is_expired(issued + TICKET_TTL, issued + TICKET_TTL / 2)
    assert is_expired(issued + TICKET_TTL, issued + TICKET_TTL)


def test_the_link_of_an_email_is_found_in_its_body() -> None:
    link = ticket_link("http://localhost:8080/", "abc-123_XYZ")

    body = set_password_email(link).text

    assert link == "http://localhost:8080/?ticket=abc-123_XYZ#account"
    assert extract_link(body) == "http://localhost:8080/?ticket=abc-123_XYZ"


def test_a_body_without_link_gives_none() -> None:
    assert extract_link("Hello, nothing to click here.") is None


RFC_6238_SECRET = base64.b32encode(b"12345678901234567890").decode()
"""The SHA-1 secret of the test vectors of RFC 6238."""


@pytest.mark.parametrize(
    ("unix_time", "code"),
    [(59, "287082"), (1111111109, "081804"), (1234567890, "005924")],
)
def test_totp_codes_are_the_ones_of_rfc_6238(unix_time: int, code: str) -> None:
    at = datetime.datetime.fromtimestamp(unix_time, datetime.UTC)

    assert totp_code(RFC_6238_SECRET, totp_step(at)) == code


def test_a_code_of_the_step_before_or_after_is_accepted() -> None:
    at = datetime.datetime(2026, 10, 9, 12, 0, 10, tzinfo=datetime.UTC)
    step = totp_step(at)

    assert matching_step(RFC_6238_SECRET, totp_code(RFC_6238_SECRET, step - 1), at)
    assert matching_step(RFC_6238_SECRET, totp_code(RFC_6238_SECRET, step + 1), at)
    assert (
        matching_step(RFC_6238_SECRET, totp_code(RFC_6238_SECRET, step - 2), at) is None
    )


def test_the_tests_authenticator_and_the_tenant_agree() -> None:
    secret = new_totp_secret()
    now = datetime.datetime.now(datetime.UTC)

    assert pyotp.TOTP(secret).at(now) == totp_code(secret, totp_step(now))


def test_the_enrolment_link_carries_the_secret_and_the_account() -> None:
    uri = otpauth_uri("ABCDEFGH", "qa-mailbox+lin@mycompany.test")

    assert uri.startswith("otpauth://totp/MyCompany:qa-mailbox%2Blin%40mycompany.test?")
    assert "secret=ABCDEFGH" in uri
