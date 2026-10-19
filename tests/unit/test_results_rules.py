"""Pure rules of the results bucket: names, paths, report parsing."""

import datetime
import json

import pytest

from test_results.junit import aggregate_test_meta, parse_junit
from test_results.k6 import parse_k6_summary
from test_results.layout import is_report_path, run_folder_name
from tests.metadata import metadata_test
from tests.sample_runs import JUNIT_TWO_PASSED_ONE_FAILED

pytestmark = [
    pytest.mark.unit,
    metadata_test(
        system="quality",
        product="test-results",
        business_capability="operate",
        component="test-results-uploader",
        group="qa-core",
        testing_scope="unit",
    ),
]


def test_run_folder_is_utc_and_sorts_like_time() -> None:
    paris = datetime.timezone(datetime.timedelta(hours=2))
    early = datetime.datetime(2026, 9, 1, 1, 0, 0, tzinfo=paris)
    late = datetime.datetime(2026, 10, 1, 9, 5, 3, tzinfo=datetime.UTC)

    assert run_folder_name(early, "7") == "20260831_230000_7"
    assert run_folder_name(early, "7") < run_folder_name(late, "7")


@pytest.mark.parametrize(
    ("path", "allowed"),
    [
        ("test-runner/reports/int/backend/20260915_083005_1/job/junit.xml", True),
        ("test-runner/reports/../run-index/index.json", False),
        ("test-runner/run-index/index.json", False),
        ("test-runner/reports//junit.xml", False),
    ],
)
def test_only_report_paths_are_readable(path: str, allowed: bool) -> None:
    assert is_report_path(path) is allowed


def test_junit_counts_statuses_and_keeps_the_failure_message() -> None:
    results = parse_junit([JUNIT_TWO_PASSED_ONE_FAILED])

    assert (results.total, results.passed, results.failed) == (3, 2, 1)
    assert results.tests[2].message == "assert 502 == 200"


def test_facets_are_merged_sorted_and_split_on_commas() -> None:
    facets = aggregate_test_meta(parse_junit([JUNIT_TWO_PASSED_ONE_FAILED]))

    assert facets == {
        "component": ["hello-api"],
        "system": ["hello"],
        "tags": ["redis", "smoke"],
    }


def test_k6_summary_lists_the_broken_thresholds() -> None:
    summary = {
        "metrics": {
            "http_reqs": {"count": 1000, "rate": 50.123},
            "http_req_failed": {
                "value": 0.02,
                "thresholds": {"rate<0.01": {"ok": False}},
            },
            "http_req_duration": {
                "avg": 120.04,
                "p(95)": 250.06,
                "p(99)": 400.0,
                "thresholds": {"p(95)<500": {"ok": True}},
            },
        }
    }

    perf = parse_k6_summary(json.dumps(summary))

    assert perf.req_rate == 50.12
    assert perf.duration_p95 == 250.1
    assert perf.breaches == ["http_req_failed: rate<0.01"]
