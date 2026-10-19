"""The console's test results pages against a real Cloud Storage emulator."""

from pathlib import Path
from urllib.parse import quote

from fastapi.testclient import TestClient
from google.cloud.storage import Bucket
import pytest

from tests.metadata import metadata_test
from tests.sample_runs import upload_sample

pytestmark = [
    pytest.mark.integration,
    metadata_test(
        system="quality",
        product="test-results",
        business_capability="operate",
        component="quality-console",
        group="qa-core",
        testing_scope="integration",
        tags="gcs",
    ),
]


def test_before_any_index_the_page_says_so(console: TestClient) -> None:
    response = console.get("/test-results")

    assert response.status_code == 200
    assert "Not indexed yet." in response.text


def test_refresh_indexes_what_ci_uploaded(
    console: TestClient, results_bucket: Bucket, tmp_path: Path
) -> None:
    upload_sample(results_bucket, tmp_path)

    response = console.post("/test-results/refresh")

    assert response.status_code == 200
    assert "1 runs indexed" in response.text
    listed = console.get("/test-results", params={"date_range": "all"})
    assert "api-tests" in listed.text


def test_run_page_shows_the_junit_breakdown(
    console: TestClient, results_bucket: Bucket, tmp_path: Path
) -> None:
    metadata, report = upload_sample(results_bucket, tmp_path)
    console.post("/test-results/refresh")

    response = console.get("/test-results/run", params={"id": report.run_id})

    assert response.status_code == 200
    assert "assert 502 == 200" in response.text
    assert "system: hello" in response.text


def test_trends_tab_charts_the_job_history(
    console: TestClient, results_bucket: Bucket, tmp_path: Path
) -> None:
    _, report = upload_sample(results_bucket, tmp_path)
    console.post("/test-results/refresh")

    response = console.get(
        "/test-results",
        params={"date_range": "all", "run": report.run_id, "tab": "trends"},
    )

    assert response.status_code == 200
    assert '<svg class="chart"' in response.text
    assert "Current streak" in response.text


def test_jobs_overview_lists_every_job(
    console: TestClient, results_bucket: Bucket, tmp_path: Path
) -> None:
    upload_sample(results_bucket, tmp_path)
    console.post("/test-results/refresh")

    response = console.get("/test-results/trends")

    assert "api-tests" in response.text
    assert "0%" in response.text


def test_html_report_is_served_sandboxed(
    console: TestClient, results_bucket: Bucket, tmp_path: Path
) -> None:
    _, report = upload_sample(results_bucket, tmp_path)

    response = console.get(
        f"/test-results/artifact?path={quote(report.run_id)}/report.html"
    )

    assert response.status_code == 200
    assert response.headers["content-security-policy"] == "sandbox"


def test_a_path_climbing_out_of_the_reports_is_a_404(console: TestClient) -> None:
    response = console.get(
        "/test-results/artifact",
        params={"path": "test-runner/reports/../run-index/index.json"},
    )

    assert response.status_code == 404
