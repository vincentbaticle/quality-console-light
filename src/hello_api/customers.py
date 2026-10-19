"""Customers, read from the company database the API shares with other services."""

from company_db import DatabaseSettings, connect

FIND_ACTIVE_FIRST_NAME = (
    "SELECT first_name FROM customers WHERE username = %s AND status = 'active'"
)
"""Query of the only column the API needs: a closed customer is no customer."""


class CustomerRepository:
    """Reads customers from the ``customers`` table."""

    def __init__(self, settings: DatabaseSettings) -> None:
        """Point at the database.

        Args:
            settings: Coordinates and credentials of the company database.
        """
        self._settings = settings

    def find_first_name(self, username: str) -> str | None:
        """Return the first name of an active customer, None for anyone else.

        Args:
            username: Username typed by the user, matched case-insensitively.

        Returns:
            The customer's first name, None when no active customer has it.
        """
        with connect(self._settings) as connection, connection.cursor() as cursor:
            cursor.execute(FIND_ACTIVE_FIRST_NAME, (username.strip().lower(),))
            row = cursor.fetchone()
        if row is None:
            return None
        return str(row[0])
