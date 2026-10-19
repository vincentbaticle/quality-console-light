"""Pure greeting rules, no I/O: the only code the unit tests cover."""

from decimal import Decimal

VISITS_KEY_PREFIX = "visits:"
"""Prefix of the Redis key counting the visits of one username."""

GREETING_TEMPLATE = "Hello {first_name}! You are visitor number {visits}."
"""Sentence the API answers with, and the one the browser test reads back."""

BALANCE_TEMPLATE = " Your balance is {amount}."
"""Added to the greeting when the Bank Partner holds an account for the username."""

CENTS_EXPONENT = -2
"""Power of ten turning an amount in cents into an amount in units."""


def format_amount(cents: int, currency: str) -> str:
    """Write an amount the way the page shows it, never through a float.

    Args:
        cents: Amount in cents, as the bank sends it.
        currency: ISO currency code, for example ``EUR``.

    Returns:
        The amount with two decimals and its currency, for example
        ``1234.56 EUR``.
    """
    return f"{Decimal(cents).scaleb(CENTS_EXPONENT)} {currency}"


def build_greeting(first_name: str, visits: int, balance: str | None) -> str:
    """Turn a first name, a visit count and a balance into the greeting.

    Args:
        first_name: First name of the customer, as the database holds it.
        visits: How many times this customer has been greeted, this one included.
        balance: Formatted balance, None when the bank holds no such account.

    Returns:
        The greeting, with the balance sentence only when there is a balance.
    """
    greeting = GREETING_TEMPLATE.format(first_name=first_name, visits=visits)
    if balance is None:
        return greeting
    return greeting + BALANCE_TEMPLATE.format(amount=balance)


def visits_key(username: str) -> str:
    """Name the Redis key counting a visitor, the same for ``Ada`` and `` ada ``.

    Args:
        username: Username typed by the user.

    Returns:
        The Redis key holding that username's visit count.
    """
    return f"{VISITS_KEY_PREFIX}{username.strip().lower()}"
