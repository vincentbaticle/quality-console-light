"""Rebuild the run index of the results bucket, once.

This is the job a scheduler runs every 30 minutes in production (see the
``results-index`` job of ``gitlab-ci/results_stage.yml``). Locally it runs on
demand: ``mise run results:index``, or the Refresh button of the console.
"""

import datetime
import os
import sys

from scripts.upload_results import BUCKET_VARIABLE
from test_results.index import build_index
from test_results.storage import open_bucket


def main() -> int:
    """Crawl the bucket, write the index, print what it holds.

    Returns:
        The process exit code.
    """
    header = build_index(
        open_bucket(os.environ[BUCKET_VARIABLE]), datetime.datetime.now(datetime.UTC)
    )
    months = ", ".join(f"{s.month} ({s.run_count})" for s in header.shards)
    print(f"[results-index] {header.run_count} runs indexed: {months or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
