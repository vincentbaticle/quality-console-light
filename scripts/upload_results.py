"""Upload the reports of a test run to the results bucket, like a CI job does.

The local twin of a test runner's ``gcs-upload`` step: it runs after the tests,
whatever their outcome, and never fails the job. Locally the bucket is the
emulator of ``docker-compose.yml``; when it is not running, the upload is
skipped with the reason, the tests' verdict stands.

Usage::

    python -m scripts.upload_results <artifact type> <reports dir>

The job context comes from the GitLab CI predefined variables (``CI_JOB_NAME``,
``CI_PIPELINE_ID``...), which the mise test tasks set themselves locally.
"""

import datetime
import os
from pathlib import Path
import sys

from test_results.layout import ARTIFACT_TYPES
from test_results.storage import is_reachable, open_bucket
from test_results.uploader import CiContext, build_metadata, upload_run

BUCKET_VARIABLE = "RESULTS_BUCKET"
"""Variable naming the results bucket."""

ENV_VARIABLE = "TEST_ENV"
"""Variable naming the environment the tests ran against."""


def main(artifact_type: str, reports_dir: Path) -> int:
    """Upload one run and print where it went.

    Returns:
        Always 0: an upload problem is reported, never a job failure.
    """
    if artifact_type not in ARTIFACT_TYPES:
        print(f"[upload-results] unknown artifact type {artifact_type}")
        return 0
    if not reports_dir.is_dir():
        print(f"[upload-results] no reports in {reports_dir}, nothing to upload")
        return 0
    bucket_name = os.environ.get(BUCKET_VARIABLE)
    if not bucket_name:
        print(f"[upload-results] {BUCKET_VARIABLE} not set, upload skipped")
        return 0
    now = datetime.datetime.now(datetime.UTC)
    metadata = build_metadata(
        artifact_type,
        os.environ[ENV_VARIABLE],
        CiContext.from_environment(),
        reports_dir,
        now,
    )
    bucket = open_bucket(bucket_name)
    if not is_reachable(bucket):
        print(
            f"[upload-results] bucket {bucket.name} unreachable, upload skipped:"
            " start it with mise run up"
        )
        return 0
    report = upload_run(bucket, metadata, reports_dir, now)
    print(f"[upload-results] {len(report.uploaded)} file(s) uploaded")
    if report.refused:
        print(f"[upload-results] {len(report.refused)} file(s) refused")
    print(f"[upload-results] gs://{bucket.name}/{report.run_id}/")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], Path(sys.argv[2])))
