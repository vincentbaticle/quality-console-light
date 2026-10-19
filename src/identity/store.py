"""The users of the tenant and their password tickets, in the ``identity`` database."""

from dataclasses import dataclass
import datetime
from typing import Any

import pymysql

from company_db import DatabaseSettings, connect
from identity.rules import MAX_FAILED_LOGINS, TICKET_TTL, is_expired, new_ticket

TICKET_KINDS = ("set_password", "reset_password", "unblock", "mfa")
"""Why a ticket was issued: an email's link, or a sign-in waiting for its code."""


class DuplicateUserError(LookupError):
    """An account already holds this email."""


class InvalidTicketError(LookupError):
    """A ticket nobody issued, already used, or expired."""


class ReplayedCodeError(ValueError):
    """A one-time code of a step this account already used."""


class AlreadyEnrolledError(ValueError):
    """An account that already has a second factor."""


@dataclass(frozen=True)
class User:
    """One account of the tenant."""

    id: str
    email: str
    password_hash: str | None
    blocked: bool
    failed_logins: int
    totp_secret: str | None = None


def _user(row: tuple[Any, ...]) -> User:
    """Build an account from its first six columns, in ``User``'s order."""
    return User(row[0], row[1], row[2], bool(row[3]), int(row[4]), row[5])


def _now() -> datetime.datetime:
    """Current UTC time without timezone, the way MySQL ``DATETIME`` stores it."""
    return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)


class UserStore:
    """Reads and writes the ``identity`` database."""

    def __init__(self, settings: DatabaseSettings) -> None:
        """Point at the identity database.

        Args:
            settings: Coordinates of an account that may write it.
        """
        self._settings = settings

    def find(self, email: str) -> User | None:
        """Find the account of a stored (lowercase) email."""
        row = self._one(
            "SELECT id, email, password_hash, blocked, failed_logins, totp_secret"
            " FROM users WHERE email = %s",
            (email,),
        )
        return _user(row) if row is not None else None

    def create(self, user_id: str, email: str) -> User:
        """Create an account without a password: it is set through the email.

        Raises:
            DuplicateUserError: When the email is taken.
        """
        try:
            self._write(
                "INSERT INTO users (id, email, created_at) VALUES (%s, %s, %s)",
                (user_id, email, _now()),
            )
        except pymysql.err.IntegrityError as exc:
            raise DuplicateUserError(email) from exc
        return User(user_id, email, None, blocked=False, failed_logins=0)

    def record_failed_login(self, user: User) -> bool:
        """Count a wrong password, and block the account at the limit.

        Returns:
            True when this failure blocked the account.
        """
        failures = user.failed_logins + 1
        blocking = failures >= MAX_FAILED_LOGINS and not user.blocked
        self._write(
            "UPDATE users SET failed_logins = %s, blocked = blocked OR %s"
            " WHERE id = %s",
            (failures, blocking, user.id),
        )
        return blocking

    def record_login(self, user: User) -> None:
        """Count a successful sign-in, which resets the failures."""
        self._write(
            "UPDATE users SET failed_logins = 0, logins_count = logins_count + 1,"
            " last_login = %s WHERE id = %s",
            (_now(), user.id),
        )

    def issue_ticket(
        self, user: User, kind: str, ttl: datetime.timedelta = TICKET_TTL
    ) -> str:
        """Issue a single-use ticket, for a password link or a pending sign-in.

        Returns:
            The ticket, valid for ``ttl``.
        """
        ticket = new_ticket()
        now = _now()
        self._write(
            "INSERT INTO tickets (token, user_id, kind, created_at, expires_at)"
            " VALUES (%s, %s, %s, %s, %s)",
            (ticket, user.id, kind, now, now + ttl),
        )
        return ticket

    def enroll_totp(self, user: User, secret: str) -> None:
        """Give an account its second factor.

        Raises:
            AlreadyEnrolledError: When it already has one.
        """
        if not self._update(
            "UPDATE users SET totp_secret = %s WHERE id = %s AND totp_secret IS NULL",
            (secret, user.id),
        ):
            raise AlreadyEnrolledError(user.email)

    def mfa_user(self, ticket: str) -> User:
        """Find the account of a sign-in waiting for its code.

        Raises:
            InvalidTicketError: When the ticket is unknown, used or expired.
        """
        row = self._one(
            "SELECT u.id, u.email, u.password_hash, u.blocked, u.failed_logins,"
            " u.totp_secret, t.expires_at, t.used_at"
            " FROM tickets t JOIN users u ON u.id = t.user_id"
            " WHERE t.token = %s AND t.kind = 'mfa'",
            (ticket,),
        )
        if row is None or row[7] is not None or is_expired(row[6], _now()):
            raise InvalidTicketError("Sign in again")
        return _user(row)

    def spend_code(self, ticket: str, user: User, step: int) -> None:
        """Finish a sign-in with the step of a valid code, once per step.

        The update only passes for a step later than the last one used, so
        two sign-ins racing with the same code cannot both win.

        Raises:
            ReplayedCodeError: When this step, or a later one, was used already.
        """
        if not self._update(
            "UPDATE users SET totp_last_step = %s WHERE id = %s"
            " AND (totp_last_step IS NULL OR totp_last_step < %s)",
            (step, user.id, step),
        ):
            raise ReplayedCodeError(user.email)
        self._write(
            "UPDATE tickets SET used_at = %s WHERE token = %s", (_now(), ticket)
        )
        self.record_login(user)

    def set_password(self, ticket: str, password_hash: str) -> None:
        """Use a ticket to set a password, which also unblocks the account.

        Raises:
            InvalidTicketError: When the ticket is unknown, used or expired.
        """
        now = _now()
        with connect(self._settings) as connection, connection.cursor() as cursor:
            cursor.execute(
                "SELECT user_id, expires_at, used_at FROM tickets"
                " WHERE token = %s FOR UPDATE",
                (ticket,),
            )
            row = cursor.fetchone()
            if row is None or row[2] is not None or is_expired(row[1], now):
                raise InvalidTicketError("This link is invalid, used or expired")
            cursor.execute(
                "UPDATE tickets SET used_at = %s WHERE token = %s", (now, ticket)
            )
            cursor.execute(
                "UPDATE users SET password_hash = %s, email_verified = TRUE,"
                " blocked = FALSE, failed_logins = 0 WHERE id = %s",
                (password_hash, row[0]),
            )
            connection.commit()

    def _one(self, statement: str, params: tuple[Any, ...]) -> tuple[Any, ...] | None:
        """Run one read and return its first row."""
        with connect(self._settings) as connection, connection.cursor() as cursor:
            cursor.execute(statement, params)
            row = cursor.fetchone()
            return tuple(row) if row is not None else None

    def _write(self, statement: str, params: tuple[Any, ...]) -> None:
        """Run one write and commit it."""
        self._update(statement, params)

    def _update(self, statement: str, params: tuple[Any, ...]) -> int:
        """Run one write, commit it, and give the number of rows it changed."""
        with connect(self._settings) as connection, connection.cursor() as cursor:
            changed = cursor.execute(statement, params)
            connection.commit()
            return int(changed)
