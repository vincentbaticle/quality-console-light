"""The second factor of the tenant: time-based one-time codes (TOTP), pure.

The same codes an authenticator app shows (RFC 6238, the Google Authenticator
settings): six digits from a shared secret and the current 30-second step.
The tenant accepts the step before and after the current one, for clocks a
little apart, and never the same step twice for one account: a code seen once
is spent, which is why two test jobs sharing one account refuse each other.
"""

import base64
import datetime
import hashlib
import hmac
import secrets
import struct
from urllib.parse import quote, urlencode

TOTP_PERIOD_SECONDS = 30
"""How long one code lives, the authenticator apps' default."""

TOTP_DIGITS = 6
"""Length of a code."""

TOTP_DRIFT_STEPS = 1
"""Steps accepted on each side of the current one, for clocks a little apart."""

TOTP_SECRET_BYTES = 20
"""Size of a new secret, 160 bits as RFC 4226 recommends."""

MFA_TICKET_TTL = datetime.timedelta(minutes=10)
"""How long the token of a half-done sign-in waits for its code."""

ISSUER = "MyCompany"
"""Name an authenticator app shows above the account."""


def new_totp_secret() -> str:
    """Give a new shared secret, in the base32 an authenticator app reads."""
    return base64.b32encode(secrets.token_bytes(TOTP_SECRET_BYTES)).decode()


def totp_step(at: datetime.datetime) -> int:
    """Give the 30-second step an instant falls in.

    Args:
        at: An aware instant.

    Returns:
        The number of whole periods since the Unix epoch.
    """
    return int(at.timestamp()) // TOTP_PERIOD_SECONDS


def totp_code(secret: str, step: int) -> str:
    """Compute the code of one step (RFC 4226 HOTP over the step counter).

    Args:
        secret: The shared secret, base32.
        step: The step, see ``totp_step``.

    Returns:
        The code, ``TOTP_DIGITS`` digits, zero-padded.
    """
    key = base64.b32decode(secret.upper() + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10**TOTP_DIGITS).zfill(TOTP_DIGITS)


def matching_step(secret: str, code: str, at: datetime.datetime) -> int | None:
    """Find the step a typed code belongs to, within the accepted drift.

    Args:
        secret: The account's shared secret.
        code: The code typed.
        at: When it was typed.

    Returns:
        The matching step, None when the code matches none.
    """
    current = totp_step(at)
    for step in range(current - TOTP_DRIFT_STEPS, current + TOTP_DRIFT_STEPS + 1):
        if hmac.compare_digest(totp_code(secret, step), code):
            return step
    return None


def otpauth_uri(secret: str, email: str) -> str:
    """Build the link an authenticator app enrols from (the QR code's content).

    Args:
        secret: The shared secret, base32.
        email: The account, shown under the issuer.

    Returns:
        An ``otpauth://totp/`` URI.
    """
    query = urlencode(
        {
            "secret": secret,
            "issuer": ISSUER,
            "digits": TOTP_DIGITS,
            "period": TOTP_PERIOD_SECONDS,
        }
    )
    return f"otpauth://totp/{quote(ISSUER)}:{quote(email)}?{query}"
