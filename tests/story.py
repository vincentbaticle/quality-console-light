"""The visitors the tests greet, and what the Bank Partner answered for them.

The customers come from ``db/02-seed.sql``. The balances are the ones the
capture recorded and the merge wrote into
``contracts/bank-partner-examples.yaml``. A new capture that brings other
balances changes them here in the same commit: they are data the bank owns, not
values a test may pick.
"""

CAPTURED_USERNAMES = ("ada", "grace")
"""Usernames the capture asks the bank about, one Microcks example each."""

ADA_BALANCE_CENTS = 125075
"""Balance the bank answered for ada at the last capture, in cents."""

ADA_BALANCE_TEXT = "1250.75 EUR"
"""That same balance, the way the greeting writes it."""

NO_ACCOUNT_USERNAME = "zoe"
"""Active customer the bank holds no account for: the hand-written 404 example."""

CLOSED_USERNAME = "dennis"
"""Customer whose ``status`` is ``closed`` in the database."""

UNKNOWN_USERNAME = "nobody"
"""Username no row of ``customers`` holds."""

MANAGEMENT_TOKEN = "test-management-token"
"""Bearer token of the simulated Auth0 Management API in tests."""

PUBLIC_URL = "http://storefront.test"
"""Storefront address the password links of the tenant point to in tests."""
