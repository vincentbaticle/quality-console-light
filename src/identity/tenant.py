"""What the tenant does, apart from HTTP: each refusal is a ``TenantError``."""

from dataclasses import dataclass
import datetime
from http import HTTPStatus

from identity.emails import (
    Mailer,
    blocked_email,
    reset_password_email,
    set_password_email,
)
from identity.rules import (
    InvalidEmailError,
    hash_password,
    new_user_id,
    normalize_email,
    password_problems,
    ticket_link,
    verify_password,
)
from identity.store import (
    AlreadyEnrolledError,
    DuplicateUserError,
    InvalidTicketError,
    ReplayedCodeError,
    User,
    UserStore,
)
from identity.totp import MFA_TICKET_TTL, matching_step, new_totp_secret, otpauth_uri

WRONG_CREDENTIALS = "Wrong email or password"
"""Same answer for an unknown email and a wrong password: no account probing."""

BLOCKED = "Account blocked, check your email"
"""Answer to a blocked account, whatever the password."""

NO_PASSWORD_YET = "No password yet, open the link of your email"  # noqa: S105
"""Answer to an account whose owner never opened the welcome email."""

MFA_REQUIRED = "mfa_required"
"""Answer to a right password on an account with a second factor, as Auth0 says it."""

WRONG_CODE = "Wrong or already used code"
"""Same answer for a wrong code and a replayed one, as a real tenant gives."""


@dataclass(frozen=True)
class TenantError(Exception):
    """A refusal of the tenant, with the HTTP status it answers."""

    status: HTTPStatus
    detail: str


@dataclass(frozen=True)
class MfaRequiredError(Exception):
    """A right password on an account that also needs its code."""

    mfa_token: str


@dataclass(frozen=True)
class Enrollment:
    """A new second factor: the secret, once, and the link an app enrols from."""

    secret: str
    otpauth_uri: str


def _email(raw: str) -> str:
    """Normalise an address, or refuse it."""
    try:
        return normalize_email(raw)
    except InvalidEmailError as exc:
        raise TenantError(HTTPStatus.UNPROCESSABLE_ENTITY, str(exc)) from exc


@dataclass(frozen=True)
class Tenant:
    """The simulated Auth0 tenant: its users, its emails, its links."""

    users: UserStore
    mailer: Mailer
    public_url: str

    def _link(self, user: User, kind: str) -> str:
        """Issue a ticket and write the link that carries it."""
        return ticket_link(self.public_url, self.users.issue_ticket(user, kind))

    def signup(self, raw_email: str) -> User:
        """Create an account and send the email that sets its password."""
        email = _email(raw_email)
        try:
            user = self.users.create(new_user_id(), email)
        except DuplicateUserError as exc:
            raise TenantError(HTTPStatus.CONFLICT, "This email has an account") from exc
        self.mailer.send(email, set_password_email(self._link(user, "set_password")))
        return user

    def login(self, raw_email: str, password: str) -> User:
        """Sign in, or ask for the code of an account with a second factor.

        Raises:
            MfaRequiredError: When the password is right and a code is due.
        """
        user = self._check_password(raw_email, password)
        if user.totp_secret is not None:
            ticket = self.users.issue_ticket(user, "mfa", MFA_TICKET_TTL)
            raise MfaRequiredError(ticket)
        self.users.record_login(user)
        return user

    def verify_code(self, mfa_token: str, code: str, at: datetime.datetime) -> User:
        """Finish a sign-in with the code of the authenticator app."""
        try:
            user = self.users.mfa_user(mfa_token)
        except InvalidTicketError as exc:
            raise TenantError(HTTPStatus.UNAUTHORIZED, str(exc)) from exc
        step = matching_step(user.totp_secret or "", code, at)
        if step is None:
            raise TenantError(HTTPStatus.UNAUTHORIZED, WRONG_CODE)
        try:
            self.users.spend_code(mfa_token, user, step)
        except ReplayedCodeError as exc:
            raise TenantError(HTTPStatus.UNAUTHORIZED, WRONG_CODE) from exc
        return user

    def enroll(self, raw_email: str, password: str) -> Enrollment:
        """Give an account a second factor, proved by its password."""
        user = self._check_password(raw_email, password)
        secret = new_totp_secret()
        try:
            self.users.enroll_totp(user, secret)
        except AlreadyEnrolledError as exc:
            raise TenantError(HTTPStatus.CONFLICT, "Second factor already set") from exc
        return Enrollment(secret, otpauth_uri(secret, user.email))

    def _check_password(self, raw_email: str, password: str) -> User:
        """Check a password, count a wrong one, block and send an email at the limit."""
        user = self.users.find(_email(raw_email))
        if user is None:
            raise TenantError(HTTPStatus.UNAUTHORIZED, WRONG_CREDENTIALS)
        if user.blocked:
            raise TenantError(HTTPStatus.LOCKED, BLOCKED)
        if user.password_hash is None:
            raise TenantError(HTTPStatus.FORBIDDEN, NO_PASSWORD_YET)
        if verify_password(password, user.password_hash):
            return user
        if self.users.record_failed_login(user):
            self.mailer.send(user.email, blocked_email(self._link(user, "unblock")))
            raise TenantError(HTTPStatus.LOCKED, BLOCKED)
        raise TenantError(HTTPStatus.UNAUTHORIZED, WRONG_CREDENTIALS)

    def request_reset(self, raw_email: str) -> None:
        """Send a reset link when the account exists, silently otherwise."""
        user = self.users.find(_email(raw_email))
        if user is not None:
            email = reset_password_email(self._link(user, "reset_password"))
            self.mailer.send(user.email, email)

    def set_password(self, ticket: str, password: str) -> None:
        """Set the password of a link's account, once."""
        problems = password_problems(password)
        if problems:
            raise TenantError(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "The password needs " + ", ".join(problems),
            )
        try:
            self.users.set_password(ticket, hash_password(password))
        except InvalidTicketError as exc:
            raise TenantError(HTTPStatus.BAD_REQUEST, str(exc)) from exc

    def management_ticket(self, raw_email: str) -> str:
        """Give a password link without any email, as the Management API does."""
        user = self.users.find(_email(raw_email))
        if user is None:
            raise TenantError(HTTPStatus.NOT_FOUND, "Unknown user")
        return self._link(user, "reset_password")
