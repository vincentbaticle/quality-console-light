"""Client of the Bank Partner, the third-party API holding the accounts."""

from collections.abc import Callable
from http import HTTPStatus
import os

import httpx
from pydantic import BaseModel

from company_secrets import read_env_file

REQUEST_TIMEOUT_SECONDS = 5.0
"""Budget for one call to the partner, after which the greeting fails."""

API_KEY_HEADER = "X-Api-Key"
"""Header carrying the key the bank issued us."""

API_KEY_FILE_VARIABLE = "BANK_PARTNER_API_KEY_FILE"
"""File holding ``BANK_PARTNER_API_KEY``, written by the Vault Agent."""


def partner_key_from_environment() -> Callable[[], str] | None:
    """The key of the bank as the environment gives it.

    Returns:
        A function reading the key file again on every call, None without one.
        The key is long-lived: the bank issued it once, it changes when the
        bank rotates it, and the agent rewrites the file then.
    """
    path = os.environ.get(API_KEY_FILE_VARIABLE)
    if not path:
        return None
    return lambda: read_env_file(path)["BANK_PARTNER_API_KEY"]


class Balance(BaseModel):
    """What the partner answers for an account, as its contract declares it."""

    username: str
    balance_cents: int
    currency: str


class BankPartnerUnavailableError(Exception):
    """The partner is unreachable, or answered neither a balance nor a not found."""


class BankPartner:
    """Asks the partner for the balance of an account."""

    def __init__(self, base_url: str, api_key: Callable[[], str] | None = None) -> None:
        """Point at the partner.

        Args:
            base_url: Root URL of the partner, the real one or a Microcks mock.
            api_key: Gives the key the bank issued us, None to send none.
        """
        self._api_key = api_key
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"), timeout=REQUEST_TIMEOUT_SECONDS
        )

    def get_balance(self, username: str) -> Balance | None:
        """Return the balance of an account, or None when the bank has none.

        Usernames are case-insensitive at the bank, so the one sent is the typed
        one stripped and lowercased.

        Args:
            username: Username typed by the user.

        Returns:
            The balance the partner holds, None on its ``404``.

        Raises:
            BankPartnerUnavailableError: When the partner cannot be reached, or
                answers anything but 200 or 404.
        """
        try:
            headers = {API_KEY_HEADER: self._api_key()} if self._api_key else {}
            response = self._client.get(
                "/balance",
                params={"username": username.strip().lower()},
                headers=headers,
            )
        except httpx.TransportError as exc:
            raise BankPartnerUnavailableError(
                f"Bank Partner unreachable: {exc}"
            ) from exc
        if response.status_code == HTTPStatus.NOT_FOUND:
            return None
        if response.status_code != HTTPStatus.OK:
            raise BankPartnerUnavailableError(
                f"Bank Partner answered HTTP {response.status_code}"
            )
        return Balance.model_validate(response.json())
