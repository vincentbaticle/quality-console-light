"""The QA mailbox, read the way a test reads an email: wait for it, open the link.

Mailpit plays the mailbox: it accepts every email over SMTP and serves them
through an HTTP API. Each test account is a plus tag of one address, so a
test waits for the emails of its own address and ignores everyone else's.
"""

from dataclasses import dataclass
import time

import httpx

from identity.rules import extract_link

MAILBOX = "qa-mailbox@mycompany.test"
"""The QA mailbox every test account is a plus tag of."""

WAIT_TIMEOUT_SECONDS = 15
"""Budget for an email to arrive, generous for a loaded laptop."""

POLL_SECONDS = 0.3
"""Delay between two looks into the mailbox."""

READINESS_TIMEOUT_SECONDS = 60
"""Budget for a Mailpit sidecar to answer."""


@dataclass(frozen=True)
class ReceivedEmail:
    """An email as the mailbox holds it."""

    to: str
    subject: str
    text: str

    @property
    def link(self) -> str:
        """The password link of the email, which every identity email carries."""
        found = extract_link(self.text)
        assert found is not None, f"no password link in {self.subject!r}"
        return found


def wait_until_ready(base_url: str) -> None:
    """Poll Mailpit until its API answers.

    Raises:
        RuntimeError: When it never answered in time.
    """
    deadline = time.monotonic() + READINESS_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{base_url}/api/v1/info").is_success:
                return
        except httpx.TransportError:
            pass
        time.sleep(POLL_SECONDS)
    raise RuntimeError(f"Mailpit at {base_url} not ready")


def empty(base_url: str) -> None:
    """Delete every email of the mailbox."""
    httpx.delete(f"{base_url}/api/v1/messages").raise_for_status()


def emails_to(base_url: str, address: str) -> list[ReceivedEmail]:
    """Every email received for one address, the newest first."""
    found = httpx.get(
        f"{base_url}/api/v1/search", params={"query": f'to:"{address}"'}
    ).json()
    emails = []
    for summary in found["messages"]:
        message = httpx.get(f"{base_url}/api/v1/message/{summary['ID']}").json()
        emails.append(ReceivedEmail(address, message["Subject"], message["Text"]))
    return emails


def wait_for_email(base_url: str, address: str, subject: str) -> ReceivedEmail:
    """Wait for the email of one address whose subject contains a text.

    Args:
        base_url: Root URL of Mailpit.
        address: The recipient, a plus tag of the mailbox.
        subject: Part of the subject to look for.

    Returns:
        The newest matching email.

    Raises:
        AssertionError: When none arrived in time.
    """
    deadline = time.monotonic() + WAIT_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        for email in emails_to(base_url, address):
            if subject in email.subject:
                return email
        time.sleep(POLL_SECONDS)
    raise AssertionError(f"no email {subject!r} for {address} in time")


def ticket_of(link: str) -> str:
    """The ticket a password link carries."""
    return httpx.URL(link).params["ticket"]
