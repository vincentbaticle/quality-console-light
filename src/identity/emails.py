"""The emails the tenant sends, and the one way it sends them: SMTP."""

from dataclasses import dataclass
from email.message import EmailMessage
import smtplib

from identity.rules import MAX_FAILED_LOGINS, TICKET_TTL

SENDER = "MyCompany accounts <no-reply@mycompany.test>"
"""Who the identity emails come from."""

SMTP_TIMEOUT_SECONDS = 10
"""Budget for handing one email to the mail server."""


@dataclass(frozen=True)
class Email:
    """What an identity email says."""

    subject: str
    text: str


def set_password_email(link: str) -> Email:
    """The email of a new account: choose a password."""
    return Email(
        "Welcome to MyCompany, choose your password",
        "Your MyCompany account is ready.\n\n"
        f"Choose your password here: {link}\n\n"
        f"The link works once and expires in {TICKET_TTL.days} days.\n",
    )


def reset_password_email(link: str) -> Email:
    """The email of a forgotten password."""
    return Email(
        "Reset your MyCompany password",
        "Someone asked to reset the password of this account.\n\n"
        f"Choose a new password here: {link}\n\n"
        f"The link works once and expires in {TICKET_TTL.days} days. "
        "If you did not ask, ignore this email.\n",
    )


def blocked_email(link: str) -> Email:
    """The email of an account blocked after too many wrong passwords."""
    return Email(
        "Your MyCompany account is blocked",
        f"We blocked your account after {MAX_FAILED_LOGINS} wrong passwords.\n\n"
        f"Choose a new password to unblock it: {link}\n",
    )


@dataclass(frozen=True)
class Mailer:
    """Sends emails through an SMTP server, Mailpit locally and in tests."""

    host: str
    port: int

    def send(self, to: str, email: Email) -> None:
        """Send one email.

        Args:
            to: Recipient address.
            email: What to send.
        """
        message = EmailMessage()
        message["From"] = SENDER
        message["To"] = to
        message["Subject"] = email.subject
        message.set_content(email.text)
        with smtplib.SMTP(self.host, self.port, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
            smtp.send_message(message)
