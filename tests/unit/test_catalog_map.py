"""The colour of a catalog item, read from the test runs that name it."""

import datetime

import pytest

from quality_console.catalog_map import FAILING, PARTIAL, PASSING, UNTESTED, health
from test_results.models import RunMetadata
from tests.metadata import metadata_test

pytestmark = [
    pytest.mark.unit,
    metadata_test(
        system="quality",
        product="quality-console",
        business_capability="operate",
        component="quality-console",
        group="qa-core",
        testing_scope="unit",
    ),
]

NOW = datetime.datetime(2026, 10, 12, 12, tzinfo=datetime.UTC)
"""The time the map is drawn."""


def run(
    job: str, days_ago: int, status: str, component: str = "hello-api"
) -> RunMetadata:
    """A run of a job naming a component, some days before NOW."""
    return RunMetadata(
        pipeline_id="1",
        job_id="1",
        job_name=job,
        artifact_type="backend",
        commit_sha="abc",
        env="int",
        timestamp=(NOW - datetime.timedelta(days=days_ago)).isoformat(),
        ci_job_status=status,
        test_meta={"component": [component]},
    )


def test_an_item_no_run_names_is_untested() -> None:
    assert (
        health("component", "front", [run("api", 1, "success")], NOW).status == UNTESTED
    )


def test_every_job_ran_lately_and_passed_is_green() -> None:
    runs = [run("api", 1, "success"), run("browser", 2, "success")]

    found = health("component", "hello-api", runs, NOW)

    assert (found.status, found.known, found.executed) == (PASSING, 2, 2)


def test_only_the_last_run_of_a_job_decides_red() -> None:
    runs = [run("api", 1, "failed"), run("api", 3, "success")]
    recovered = [run("api", 1, "success"), run("api", 3, "failed")]

    assert health("component", "hello-api", runs, NOW).status == FAILING
    assert health("component", "hello-api", recovered, NOW).status == PASSING


def test_a_job_that_did_not_run_lately_makes_it_partial() -> None:
    runs = [run("api", 1, "success"), run("browser", 20, "success")]

    found = health("component", "hello-api", runs, NOW)

    assert found.status == PARTIAL
    assert found.ratio == 0.5


def test_a_failed_job_says_how_much_of_it_passed() -> None:
    failed = run("e2e", 1, "failed").model_copy(
        update={"test_counts": {"total": 10, "passed": 8, "failed": 0, "errors": 2}}
    )

    found = health("component", "hello-api", [failed], NOW)

    assert found.status == FAILING
    assert found.failing == ["e2e (int): 8/10 passed, 2 errors"]
    assert found.summary == "8/10 tests passed · 1 job failed"
