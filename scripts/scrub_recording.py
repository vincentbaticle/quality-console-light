"""Clean a recorded journey before it leaves the machine.

Usage::

    python -m scripts.scrub_recording <raw script> <clean script> [<raw har> <clean>]

Writes the cleaned copies, deletes the raw files, prints a JSON report of what
was removed and where, never a removed value.
"""

import json
from pathlib import Path
import sys

from quality_console.recording_scrub import clean_session

USAGE = __doc__.split("Usage::", 1)[1].split("\n\n", 2)[1].strip()
"""The command line, shown on a wrong call."""


def main(args: list[str]) -> int:
    """Clean the session the arguments name.

    Returns:
        The process exit code: 2 on a wrong call.
    """
    if len(args) not in (2, 4):
        print(f"Usage: {USAGE}")
        return 2
    paths = [Path(a) for a in args]
    report = clean_session(*paths)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
