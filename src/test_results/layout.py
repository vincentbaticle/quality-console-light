"""Where things live in the results bucket. Every reader and writer agrees on it."""

import datetime

REPORTS_PREFIX = "test-runner/reports"
"""Root of every run folder: ``<env>/<artifact type>/<run folder>/<job name>/``."""

INDEX_PREFIX = "test-runner/run-index"
"""Root of the run index, a sibling of the reports so a crawl never reads it."""

INDEX_HEADER = f"{INDEX_PREFIX}/index.json"
"""The index header: generation time, run count and the list of month shards."""

METADATA_FILE = "metadata.json"
"""File describing one run, written first by the uploader."""

RUN_INDEX_METADATA_KEY = "run-index"
"""Object metadata key carrying the run's metadata, so a crawl skips a download."""

COVERAGE_FILE = "coverage.xml"
"""Cobertura coverage report of a run, uploaded beside its JUnit report."""

ARTIFACT_TYPES = ("backend", "e2e", "acceptance", "performance")
"""Kinds of runs: API tests, browser tests, Gherkin scenarios, load tests."""

RUN_FOLDER_FORMAT = "%Y%m%d_%H%M%S"
"""UTC, zero-padded: the text order of folder names is their chronological order."""


def run_folder_name(now: datetime.datetime, pipeline_id: str) -> str:
    """Name the folder of a run: ``YYYYMMDD_HHMMSS_<pipeline id>``, in UTC.

    Args:
        now: Upload time, timezone-aware.
        pipeline_id: CI pipeline the run belongs to.

    Returns:
        The folder name.
    """
    stamp = now.astimezone(datetime.UTC).strftime(RUN_FOLDER_FORMAT)
    return f"{stamp}_{pipeline_id}"


def run_id(env: str, artifact_type: str, folder: str, job_name: str) -> str:
    """Build the id of a run, which is also the bucket path of its folder.

    Args:
        env: Environment the tests ran against.
        artifact_type: One of ``ARTIFACT_TYPES``.
        folder: Run folder name, see ``run_folder_name``.
        job_name: CI job that ran the tests.

    Returns:
        ``test-runner/reports/<env>/<artifact type>/<folder>/<job name>``.
    """
    return f"{REPORTS_PREFIX}/{env}/{artifact_type}/{folder}/{job_name}"


def is_report_path(path: str) -> bool:
    """Say whether a path a visitor sent stays inside the reports.

    Args:
        path: Bucket path taken from a request.

    Returns:
        True when the path is under ``REPORTS_PREFIX`` and climbs nowhere.
    """
    parts = path.split("/")
    climbs = ".." in parts or "" in parts
    return path.startswith(f"{REPORTS_PREFIX}/") and not climbs
