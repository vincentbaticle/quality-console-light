"""What the captures recorded, and what the tests replay from it.

Two recordings feed the tests. The Bank Partner capture asks the real partner
and keeps its HTTP answers; Microcks replays them. The events capture taps the
broker of the running stack and keeps the RabbitMQ events the order workflow
publishes; a test compares the events of the code with them. Each recording
has a journal (the raw transcript, never committed, in ``capture/``) and the
examples merged from it (committed, in ``contracts/``).
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Entry:
    """One recorded exchange: what was sent, what came back or followed."""

    label: str
    sent: str
    received: str
    after_ms: int | None = None


@dataclass(frozen=True)
class Example:
    """One example the tests replay, and where it came from."""

    name: str
    origin: str
    content: str


@dataclass
class Recording:
    """One capture, its journal and its examples."""

    key: str
    title: str
    kind: str
    purpose: str
    source: str
    journal: str
    captured_at: str | None
    entries: list[Entry] = field(default_factory=list)
    examples_file: str = ""
    examples: list[Example] = field(default_factory=list)
    replayed_by: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)


def _json(value: Any) -> str:
    """A compact, readable JSON text."""
    return json.dumps(value, ensure_ascii=False)


def _read_json(path: Path) -> dict[str, Any] | None:
    """A journal, None when it was never recorded on this machine."""
    return json.loads(path.read_text()) if path.is_file() else None


def bank_partner(capture: Path, contracts: Path) -> Recording:
    """The capture of the Bank Partner's answers.

    Args:
        capture: The ``capture/`` folder.
        contracts: The ``contracts/`` folder.

    Returns:
        The recording, its journal entries and its examples.
    """
    journal = _read_json(capture / "journal.json")
    recorded = {r["example"] for r in journal["records"]} if journal else set()
    document = yaml.safe_load((contracts / "bank-partner-examples.yaml").read_text())
    operation = document["paths"]["/balance"]["get"]
    examples = []
    for status, response in operation["responses"].items():
        content = response["content"]["application/json"]["examples"]
        for name, example in content.items():
            origin = "captured" if status == "200" else "written by hand"
            if name in recorded:
                origin = "captured, in the journal"
            examples.append(
                Example(name, origin, f"{status} {_json(example['value'])}")
            )
    return Recording(
        key="bank-partner",
        title="Bank Partner answers (HTTP)",
        kind="http",
        purpose=(
            "What the third-party bank really answers for the usernames of the "
            "story, so the tests replay real answers instead of guessed ones."
        ),
        source="the fake Bank Partner on http://localhost:8090, GET /balance",
        journal="capture/journal.json",
        captured_at=journal["captured_at"] if journal else None,
        entries=[
            Entry(
                r["example"],
                f"GET /balance?username={r['request']['username']}",
                f"{r['status']} {_json(r['body'])}",
            )
            for r in (journal["records"] if journal else [])
        ],
        examples_file="contracts/bank-partner-examples.yaml",
        examples=examples,
        replayed_by=[
            "tests/integration/test_hello_balance_microcks.py",
            "tests/integration/test_hello_page_browser.py",
        ],
        commands=[
            "mise run partner:up",
            "mise run capture:examples",
            "mise run capture:merge",
            "git diff contracts/",
        ],
    )


def order_events(capture: Path, contracts: Path) -> Recording:
    """The capture of the events the order workflow publishes.

    Args:
        capture: The ``capture/`` folder.
        contracts: The ``contracts/`` folder.

    Returns:
        The recording, its journal entries and its recorded examples.
    """
    journal = _read_json(capture / "events-journal.json")
    entries = [
        Entry(story, _json(record["order"]), _json(event["body"]), event["offset_ms"])
        for story, record in (journal["stories"].items() if journal else [])
        for event in record["events"]
    ]
    path = contracts / "order-workflow-recorded.yaml"
    recorded = yaml.safe_load(path.read_text()) if path.is_file() else {"stories": {}}
    examples = [
        Example(
            story,
            "recorded",
            " then ".join(e["body"]["type"] for e in content["events"]),
        )
        for story, content in recorded["stories"].items()
    ]
    return Recording(
        key="order-events",
        title="Order workflow events (RabbitMQ)",
        kind="events",
        purpose=(
            "What our own services really publish on the broker when an order is "
            "placed, so a test can check the code still sends the same events in "
            "the same order, with the same fields."
        ),
        source="the broker of mise run up, through its firehose (amq.rabbitmq.trace)",
        journal="capture/events-journal.json",
        captured_at=journal["captured_at"] if journal else None,
        entries=entries,
        examples_file="contracts/order-workflow-recorded.yaml",
        examples=examples,
        replayed_by=["tests/integration/test_orders_rabbitmq.py"],
        commands=[
            "mise run up",
            "mise run capture:events",
            "mise run capture:events-merge",
            "git diff contracts/",
        ],
    )


def load_recordings(capture: Path, contracts: Path) -> list[Recording]:
    """Every recording of the repository.

    Args:
        capture: The ``capture/`` folder, absent on a fresh clone.
        contracts: The ``contracts/`` folder.

    Returns:
        The recordings, HTTP first.
    """
    return [bank_partner(capture, contracts), order_events(capture, contracts)]
