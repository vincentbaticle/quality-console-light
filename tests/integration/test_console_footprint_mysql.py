"""retro-footprint run for real: the real API in process, a real MySQL.

The lab reads the table counters of ``performance_schema`` with the console's
read-only account, colleagues query from their own connection, the test is
played ten times, without the minute of pause. No Tempo here: the
intersection is the only answer for the API calls, the test's own SQL names
its tables itself.
"""

import random

from fastapi.testclient import TestClient
import pytest

from company_db import DatabaseSettings
from quality_console.footprint import (
    COLLEAGUE_TABLES,
    RUNS,
    RUNS_PER_BATCH,
    TARGETS,
    Experiment,
)
from quality_console.footprint_lab import FootprintLab
from tests.database import reader_settings
from tests.metadata import metadata_test

pytestmark = [
    pytest.mark.integration,
    metadata_test(
        system="quality",
        product="quality-console",
        business_capability="operate",
        component="quality-console",
        group="qa-core",
        testing_scope="integration",
        tags="mysql",
    ),
]


def test_ten_real_runs_narrow_the_tables_down_to_the_api_then_the_sql(
    api: TestClient, database: DatabaseSettings
) -> None:
    lab = FootprintLab(reader_settings(database), api, tempo=None, pause_seconds=0)
    experiment = Experiment("test", TARGETS["hello-then-sql"])

    lab.run(experiment, random.Random(1))  # noqa: S311

    assert experiment.error is None
    assert len(experiment.runs) == RUNS
    assert experiment.found == [
        "customers",
        "customer_addresses",
        "customer_preferences",
    ]
    first = experiment.runs[0]
    assert [step.kind for step in first.steps] == ["api", "sql"]
    assert first.steps[0].outcome == "HTTP 200"
    assert "customers" in first.steps[0].tables
    assert {"customers", "customer_addresses", "customer_preferences"} <= set(
        first.steps[1].tables
    )
    assert len(first.hits) >= COLLEAGUE_TABLES[0][0]
    assert set(first.colleagues) <= {hit.table for hit in first.hits}
    assert set(experiment.looping) <= set(first.colleagues)
    assert sorted(first.order) == sorted(hit.table for hit in first.hits)
    assert [run.batch for run in experiment.runs[RUNS_PER_BATCH - 1 :]] == [1] + [
        2
    ] * RUNS_PER_BATCH
    assert experiment.trace_ids == []
    assert not experiment.checked
    assert experiment.progress == 100


def test_a_test_reading_the_database_itself_needs_no_trace(
    api: TestClient, database: DatabaseSettings
) -> None:
    lab = FootprintLab(reader_settings(database), api, tempo=None, pause_seconds=0)
    experiment = Experiment("test", TARGETS["sql-only"])

    lab.run(experiment, random.Random(2))  # noqa: S311

    assert experiment.error is None
    assert experiment.found == ["products", "stock_levels"]
    assert experiment.checked
    assert experiment.exact == experiment.found
    assert experiment.phase == "Done"


def test_an_api_reading_no_table_converges_on_none(
    api: TestClient, database: DatabaseSettings
) -> None:
    lab = FootprintLab(reader_settings(database), api, tempo=None, pause_seconds=0)
    experiment = Experiment("test", TARGETS["api-only"])

    lab.run(experiment, random.Random(3))  # noqa: S311

    assert experiment.error is None
    assert [run.steps[0].outcome for run in experiment.runs] == ["HTTP 200"] * RUNS
    assert experiment.found == []


def test_a_front_reading_a_table_after_a_redirect_shows_it_on_its_step(
    api: TestClient, console: TestClient, database: DatabaseSettings
) -> None:
    lab = FootprintLab(
        reader_settings(database),
        api,
        tempo=None,
        pause_seconds=0,
        fronts={"storefront": console, "quality-console": console},
    )
    experiment = Experiment("test", TARGETS["front-api-redirect"])

    lab.run(experiment, random.Random(4))  # noqa: S311

    assert experiment.error is None
    first = experiment.runs[0]
    assert [step.kind for step in first.steps] == ["front", "api", "front"]
    assert all(step.outcome == "HTTP 200" for step in first.steps)
    assert "customers" in first.steps[2].tables
    assert "customers" in experiment.found
    assert [front.operation for front in experiment.fronts] == ["", "redirect"]
