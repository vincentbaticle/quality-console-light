"""Rewrite the Microcks examples of the Bank Partner from a capture journal.

The capture records, this turns the recording into the examples Microcks replays.
The two are separate on purpose: this step touches nothing but a file, so what
lands in the examples can be read in a diff before anything is committed.

Only the examples the journal names are rewritten, both halves of each: the
query parameter that selects it and the response the partner sent. Every other
example is left as it stands, which is how the hand-written ones (the ``404`` no
partner serves on demand) survive a refresh.

Usage::

    mise run capture:merge

Exit codes: 0 when the examples were rewritten, 1 when nothing was.
"""

import json
from pathlib import Path
import sys
from typing import Any

import yaml

from scripts.capture_partner import JOURNAL_PATH

EXAMPLES_PATH = Path("contracts/bank-partner-examples.yaml")
"""Secondary Microcks artifact holding the examples of the Bank Partner."""

CAPTURED_STATUS = 200
"""Only successful answers are captured; error examples stay hand-written."""


def merge(examples: dict[str, Any], records: list[dict[str, Any]]) -> None:
    """Write each recorded answer into the example of the same name.

    Args:
        examples: The parsed secondary artifact, modified in place.
        records: The journal records, one per captured username.

    Raises:
        ValueError: When a record is not a successful answer.
    """
    operation = examples["paths"]["/balance"]["get"]
    parameter = operation["parameters"][0]
    response = operation["responses"][str(CAPTURED_STATUS)]
    response_examples = response["content"]["application/json"]["examples"]
    for record in records:
        if record["status"] != CAPTURED_STATUS:
            raise ValueError(f"{record['example']} was answered {record['status']}")
        parameter["examples"][record["example"]] = {
            "value": record["request"]["username"]
        }
        response_examples[record["example"]] = {"value": record["body"]}


def main() -> int:
    """Merge the journal into the examples file.

    Returns:
        The process exit code.
    """
    if not JOURNAL_PATH.exists():
        print(f"[merge] no journal at {JOURNAL_PATH}: run mise run capture:examples")
        return 1
    journal = json.loads(JOURNAL_PATH.read_text())
    examples = yaml.safe_load(EXAMPLES_PATH.read_text())
    try:
        merge(examples, journal["records"])
    except ValueError as exc:
        print(f"[merge] nothing written, the journal is not usable: {exc}")
        return 1
    EXAMPLES_PATH.write_text(yaml.safe_dump(examples, sort_keys=False, width=100))
    print(f"[merge] {len(journal['records'])} examples rewritten in {EXAMPLES_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
