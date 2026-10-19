"""Turn the events journal into the recorded examples of the order workflow.

Like the merge of the Bank Partner, this step only writes a file, so what a
recording changes is read in a diff before it is committed. The workflow ids
of the journal are replaced by a placeholder: an id changes at every capture,
the sequence and the shape of the events are what a test relies on.

Usage::

    mise run capture:events-merge

Exit codes: 0 when the examples were written, 1 without a journal.
"""

import json
from pathlib import Path
import sys
from typing import Any

import yaml

from scripts.capture_events import JOURNAL_PATH

RECORDED_PATH = Path("contracts/order-workflow-recorded.yaml")
"""The recorded examples, read by the tests and the API docs."""

WORKFLOW_PLACEHOLDER = "<workflow_id>"
"""Stands for the workflow id the capture saw."""


def examples(journal: dict[str, Any]) -> dict[str, Any]:
    """The recorded examples of a journal.

    Args:
        journal: The parsed events journal.

    Returns:
        One entry per story: the order placed and the events, ids replaced.
    """
    stories = {}
    for story, record in journal["stories"].items():
        stories[story] = {
            "order": record["order"],
            "events": [
                {
                    "after_ms": event["offset_ms"],
                    "queue": event["queue"],
                    "body": {**event["body"], "workflow_id": WORKFLOW_PLACEHOLDER},
                }
                for event in record["events"]
            ],
        }
    return {"captured_at": journal["captured_at"], "stories": stories}


def main() -> int:
    """Write the recorded examples.

    Returns:
        The process exit code.
    """
    if not JOURNAL_PATH.exists():
        print(f"[merge] no {JOURNAL_PATH}: run mise run capture:events first")
        return 1
    recorded = examples(json.loads(JOURNAL_PATH.read_text()))
    RECORDED_PATH.write_text(yaml.safe_dump(recorded, sort_keys=False))
    print(f"[merge] {RECORDED_PATH} written, review it with git diff")
    return 0


if __name__ == "__main__":
    sys.exit(main())
