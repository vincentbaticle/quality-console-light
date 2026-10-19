"""How a job's trend is computed and drawn: pass rates, streaks, the chart."""

import pytest

from quality_console.charts import pass_rate_chart
from test_results.models import RunMetadata
from test_results.trends import (
    current_streak,
    job_history,
    job_summaries,
    pass_rate,
    rolling_pass_rate,
)
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


def run(day: int, status: str | None, job_name: str = "api-tests") -> RunMetadata:
    """A run of a given day of September 2026, with a given CI status."""
    return RunMetadata(
        id=f"test-runner/reports/int/backend/202609{day:02d}_080000_{day}/{job_name}",
        pipeline_id=str(day),
        job_id=str(day),
        job_name=job_name,
        artifact_type="backend",
        commit_sha="abc1234",
        env="int",
        timestamp=f"2026-09-{day:02d}T08:00:00+00:00",
        ci_job_status=status,
    )


NEWEST_FIRST = [
    run(5, "failed"),
    run(4, "failed"),
    run(3, "success"),
    run(2, "success"),
]
"""Two successes, then two failures, newest first as the index lists them."""


def test_rolling_pass_rate_averages_the_last_three_runs_in_time_order() -> None:
    assert rolling_pass_rate(NEWEST_FIRST) == [100, 100, 67, 33]


def test_pass_rate_and_streak_of_a_job() -> None:
    streak = current_streak(NEWEST_FIRST)

    assert pass_rate(NEWEST_FIRST) == 50
    assert (streak.count, streak.status) == (2, "failed")


def test_history_keeps_only_the_job_asked_for() -> None:
    runs = [run(6, "success", "other-job"), *NEWEST_FIRST]

    assert job_history(runs, "api-tests", "backend", "int") == NEWEST_FIRST


def test_an_unreported_status_counts_as_unknown() -> None:
    summary = job_summaries([run(7, None), *NEWEST_FIRST])[0]

    assert summary.statuses[-1] == "unknown"
    assert summary.streak.status == "unknown"


def test_chart_links_every_run_and_rings_the_selected_one() -> None:
    svg = str(pass_rate_chart(NEWEST_FIRST, NEWEST_FIRST[1].id))

    assert svg.count("<a href=") == 4
    assert svg.count('class="selected-ring"') == 1
    assert svg.count('class="failed-band"') == 2
    assert ">02/09<" in svg
