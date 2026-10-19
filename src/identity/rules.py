"""The rules of the simulated Auth0 tenant, pure, each one unit tested.

They copy what the real tenant does and what tests run into: emails are
stored in lowercase, a password setup link is single use and lives five days,
ten wrong passwords block the account, and every test account is a plus tag
of one QA mailbox.
"""

import datetime
import hashlib
import hmac
import re
import secrets

TICKET_TTL = datetime.timedelta(days=5)
"""How long a password setup or reset link stays valid, Auth0's default."""

MAX_FAILED_LOGINS = 10
"""Wrong passwords in a row after which the account is blocked."""

PASSWORD_MIN_LENGTH = 8
"""Shortest password the tenant accepts."""

PASSWORD_ITERATIONS = 100_000
"""PBKDF2 rounds of a password hash, enough for a simulation, fast in tests."""

HASH_SCHEME = "pbkdf2_sha256"
"""Prefix of a stored password hash, so a later scheme can sit beside it."""

USER_ID_PREFIX = "auth0|"
"""Prefix of a user id, the database connection's own, as Auth0 writes it."""

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
"""Shape an email must have: one ``@``, a dot in the domain, no space."""

TICKET_LINK_PATTERN = re.compile(r"https?://\S*[?&]ticket=[\w-]+")
"""A password link inside an email body."""


class InvalidEmailError(ValueError):
    """An address the tenant cannot store."""


def normalize_email(email: str) -> str:
    """Write an email the way the tenant stores it: trimmed and lowercase.

    Args:
        email: The address as typed.

    Returns:
        The stored address.

    Raises:
        InvalidEmailError: When the address has not the shape of an email.
    """
    normalized = email.strip().lower()
    if not EMAIL_PATTERN.match(normalized):
        raise InvalidEmailError(f"Not an email: {email!r}")
    return normalized


def plus_address(mailbox: str, tag: str) -> str:
    """Give one test account its own address in the shared QA mailbox.

    Args:
        mailbox: The mailbox, for example ``qa-mailbox@mycompany.test``.
        tag: What identifies the account, for example ``ada``.

    Returns:
        ``qa-mailbox+ada@mycompany.test``: delivered to the mailbox, tag kept.
    """
    local, domain = mailbox.split("@", 1)
    return f"{local}+{tag}@{domain}"


def password_problems(password: str) -> list[str]:
    """List what a password lacks to meet the tenant's policy.

    Args:
        password: The password typed.

    Returns:
        One sentence per unmet rule, empty when the password is accepted.
    """
    checks = {
        f"at least {PASSWORD_MIN_LENGTH} characters": len(password)
        >= PASSWORD_MIN_LENGTH,
        "a lowercase letter": any(c.islower() for c in password),
        "an uppercase letter": any(c.isupper() for c in password),
        "a digit": any(c.isdigit() for c in password),
    }
    return [rule for rule, met in checks.items() if not met]


def hash_password(password: str, salt: bytes | None = None) -> str:
    """Hash a password for storage.

    Args:
        password: The password to store.
        salt: A fixed salt, only to write seed data; a random one otherwise.

    Returns:
        ``pbkdf2_sha256$<rounds>$<salt hex>$<hash hex>``.
    """
    salt = salt if salt is not None else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PASSWORD_ITERATIONS)
    return f"{HASH_SCHEME}${PASSWORD_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str | None) -> bool:
    """Say whether a password matches a stored hash.

    Args:
        password: The password typed.
        stored: The stored hash, None for an account without a password yet.

    Returns:
        True when they match.
    """
    if not stored:
        return False
    scheme, rounds, salt, expected = stored.split("$")
    if scheme != HASH_SCHEME:
        return False
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), int(rounds)
    )
    return hmac.compare_digest(digest.hex(), expected)


def new_user_id() -> str:
    """Give a new user id, ``auth0|`` then 24 hexadecimal characters."""
    return USER_ID_PREFIX + secrets.token_hex(12)


def new_ticket() -> str:
    """Give a new ticket, the secret a password link carries."""
    return secrets.token_urlsafe(32)


def is_expired(expires_at: datetime.datetime, now: datetime.datetime) -> bool:
    """Say whether a ticket expired.

    Args:
        expires_at: When the ticket stops being valid.
        now: The current time, in the same timezone.

    Returns:
        True from the expiry instant on.
    """
    return now >= expires_at


def ticket_link(public_url: str, ticket: str) -> str:
    """Build the link a password email carries.

    Args:
        public_url: Where the storefront is served, for example
            ``http://localhost:8080``.
        ticket: The ticket.

    Returns:
        The storefront page that sets the password, with the ticket.
    """
    return f"{public_url.rstrip('/')}/?ticket={ticket}#account"


def extract_link(body: str) -> str | None:
    """Find the password link in an email body, as a test reading the mailbox does.

    Args:
        body: The text of the email.

    Returns:
        The first password link, None when there is none.
    """
    match = TICKET_LINK_PATTERN.search(body)
    return match.group(0) if match else None
