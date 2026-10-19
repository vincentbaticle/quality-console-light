"""Small, known runs the results tests upload and expect to read back."""

import datetime
from pathlib import Path

from google.cloud.storage import Bucket

from test_results.models import RunMetadata
from test_results.uploader import CiContext, UploadReport, build_metadata, upload_run

JUNIT_TWO_PASSED_ONE_FAILED = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" tests="3">
<testcase classname="tests.test_hello" name="test_health" time="0.10">
<properties>
<property name="system" value="hello"/>
<property name="tags" value="smoke, redis"/>
</properties>
</testcase>
<testcase classname="tests.test_hello" name="test_greeting" time="0.20">
<properties>
<property name="system" value="hello"/>
<property name="component" value="hello-api"/>
</properties>
</testcase>
<testcase classname="tests.test_hello" name="test_balance" time="0.30">
<failure message="assert 502 == 200">AssertionError</failure>
</testcase>
</testsuite></testsuites>
"""
"""A JUnit report with two passed tests, one failed, and declared facets."""

REPORT_HTML = "<!doctype html><title>report</title><script>alert(1)</script>"
"""An HTML report, with a script the console must not let run."""

UPLOAD_TIME = datetime.datetime(2026, 9, 15, 8, 30, 5, tzinfo=datetime.UTC)
"""When the sample run is uploaded, which names its folder."""


def ci_context(job_name: str = "api-tests", status: str = "failed") -> CiContext:
    """CI context of the sample run."""
    return CiContext(
        pipeline_id="4242",
        job_id="99",
        job_name=job_name,
        commit_sha="abc1234",
        job_status=status,
        project_url="https://gitlab.example.com/qa/demo",
    )


def write_reports(folder: Path) -> Path:
    """Write the sample run's report files and return their folder."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "junit.xml").write_text(JUNIT_TWO_PASSED_ONE_FAILED)
    (folder / "report.html").write_text(REPORT_HTML)
    return folder


def upload_sample(
    bucket: Bucket,
    folder: Path,
    *,
    env: str = "int",
    job_name: str = "api-tests",
    status: str = "failed",
    when: datetime.datetime = UPLOAD_TIME,
) -> tuple[RunMetadata, UploadReport]:
    """Upload the sample run the way CI would, and return what was written."""
    reports = write_reports(folder)
    metadata = build_metadata(
        "backend", env, ci_context(job_name, status), reports, when
    )
    return metadata, upload_run(bucket, metadata, reports, when)
