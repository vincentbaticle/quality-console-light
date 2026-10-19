"""Record what the Bank Partner really answers, into a journal.

A hand-written example is a guess about a partner nobody asked. This script asks:
it calls the partner for every username of the story and writes each request beside
the answer it got. What it writes is a transcript, not a fixture: the merge step
turns it into Microcks examples, and only that diff gets reviewed and committed.

Usage::

    mise run capture:examples

Exit codes: 0 when every username was answered, 1 when the partner could not be
reached or answered an error, in which case no journal is written.
"""

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import sys

import httpx
import hvac

from hello_api.bank_partner import API_KEY_HEADER
from tests.story import CAPTURED_USERNAMES

PARTNER_URL_VARIABLE = "CAPTURE_PARTNER_URL"
"""Environment variable naming the partner to capture, set by the mise task."""

JOURNAL_PATH = Path("capture/journal.json")
"""Where the transcript is written, and where the merge reads it from."""

REQUEST_TIMEOUT_SECONDS = 5.0
"""Budget for one call to the partner."""

VAULT = {
    "url": ("VAULT_ADDR", "http://localhost:8200"),
    "token": ("VAULT_TOKEN", "tests-token"),
}
"""Where Vault answers and the token allowed to read the bank's key."""


def partner_api_key() -> str:
    """The key the bank issued us, read from Vault like the tests do."""
    settings = {
        name: os.environ.get(var, default) for name, (var, default) in VAULT.items()
    }
    secret = hvac.Client(**settings).secrets.kv.v2.read_secret(path="bank-partner")
    return str(secret["data"]["data"]["api_key"])


def capture(partner_url: str, api_key: str) -> list[dict[str, object]]:
    """Ask the partner about every username of the story.

    Args:
        partner_url: Root URL of the partner to record.
        api_key: The key the bank issued us.

    Returns:
        One record per username: the request, the status and the body answered.

    Raises:
        httpx.HTTPError: When the partner is unreachable or answers an error.
    """
    records = []
    with httpx.Client(
        base_url=partner_url,
        timeout=REQUEST_TIMEOUT_SECONDS,
        headers={API_KEY_HEADER: api_key},
    ) as client:
        for username in CAPTURED_USERNAMES:
            response = client.get("/balance", params={"username": username})
            response.raise_for_status()
            records.append(
                {
                    "example": username,
                    "request": {"username": username},
                    "status": response.status_code,
                    "body": response.json(),
                }
            )
    return records


def main() -> int:
    """Capture the partner and write the journal.

    Returns:
        The process exit code.
    """
    partner_url = os.environ[PARTNER_URL_VARIABLE]
    try:
        records = capture(partner_url, partner_api_key())
    except httpx.HTTPError as exc:
        print(f"[capture] {partner_url} could not be recorded: {exc}")
        return 1
    journal = {
        "partner_url": partner_url,
        "captured_at": datetime.now(UTC).isoformat(),
        "records": records,
    }
    JOURNAL_PATH.parent.mkdir(exist_ok=True)
    JOURNAL_PATH.write_text(json.dumps(journal, indent=2) + "\n")
    print(f"[capture] {len(records)} answers written to {JOURNAL_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
