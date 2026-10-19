"""Signing in through a second factor like a test does: computing the code.

A test has no phone. It keeps the account's TOTP secret where it keeps the
password (a vault, a CI variable; here the seed) and computes the code with a
library, the one an authenticator app runs. Two habits make it reliable:

- never type a code about to expire: wait for the next one when fewer than
  ``MIN_SECONDS_LEFT`` remain, or it can expire between typing and checking;
- when a code is refused, try once more with the next one: the tenant takes
  each code once per account, so a parallel job or a rerun inside the same
  30 seconds may have spent it already.
"""

from collections.abc import Iterator
import time

import pyotp

MIN_SECONDS_LEFT = 5
"""Seconds a code must still live when it is typed."""

LIN_EMAIL = "qa-mailbox+lin@mycompany.test"
"""The seeded account with a second factor."""

LIN_TOTP_SECRET = "OF2WC3DJOR4S2Y3PNZZW63DFFV2G65DQ"  # noqa: S105 - seeded demo account
"""Its TOTP secret, the one its authenticator app was enrolled with."""

AUTHENTICATORS = {LIN_EMAIL: LIN_TOTP_SECRET}
"""The TOTP secret of each seeded account with a second factor, by email."""


def _seconds_left(totp: pyotp.TOTP) -> float:
    """Seconds before the current code expires."""
    return totp.interval - time.time() % totp.interval


def fresh_code(secret: str) -> str:
    """Give a code that still lives at least ``MIN_SECONDS_LEFT`` seconds.

    Waits for the next 30-second step when the current one is nearly over:
    a wait on the clock, at most ``MIN_SECONDS_LEFT`` seconds, not a guess.
    """
    totp = pyotp.TOTP(secret)
    left = _seconds_left(totp)
    if left < MIN_SECONDS_LEFT:
        time.sleep(left)
    return totp.now()


def next_code(secret: str) -> str:
    """Wait for the next 30-second step and give its code, never seen before."""
    totp = pyotp.TOTP(secret)
    time.sleep(_seconds_left(totp))
    return totp.now()


def codes(secret: str) -> Iterator[str]:
    """Give a fresh code, then, if the test asks again, the next one.

    A test tries the first, and on a refusal the second: once is a spent
    code, twice is a wrong secret, and the test fails.
    """
    yield fresh_code(secret)
    yield next_code(secret)
