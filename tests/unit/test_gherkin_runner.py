"""How the Gherkin runner builds a run and reads its verdict."""

from pathlib import Path

import pytest

from gherkin_runner.main import pytest_command, verdict
from tests.metadata import metadata_test

pytestmark = [
    pytest.mark.unit,
    metadata_test(
        system="quality",
        product="test-results",
        business_capability="operate",
        component="gherkin-runner",
        group="qa-web",
        testing_scope="unit",
    ),
]

JUNIT = """<testsuites><testsuite>
<testcase classname="a" name="one" time="1"/>
<testcase classname="a" name="two" time="1"><failure message="boom"/></testcase>
<testcase classname="a" name="three" time="0"><skipped message="down"/></testcase>
</testsuite></testsuites>"""
"""A run with one scenario of each outcome."""


def test_a_scenario_run_narrows_pytest_to_it() -> None:
    command = pytest_command("checkout/place-order.feature", "Paid", Path("/r"))

    assert "--only-feature=checkout/place-order.feature" in command
    assert "--only-scenario=Paid" in command
    assert "--junitxml=/r/junit.xml" in command


def test_a_feature_run_has_no_scenario_filter() -> None:
    command = pytest_command("checkout/place-order.feature", "", Path("/r"))

    assert not any(part.startswith("--only-scenario") for part in command)


def test_one_failure_fails_the_run() -> None:
    result = verdict(JUNIT, 1)

    assert (result.status, result.passed, result.failed, result.skipped) == (
        "failed",
        1,
        1,
        1,
    )


def test_a_run_where_everything_skipped_is_skipped_not_passed() -> None:
    junit = (
        '<testsuite><testcase classname="a" name="b"><skipped/></testcase></testsuite>'
    )

    assert verdict(junit, 0).status == "skipped"


def test_no_report_is_an_error() -> None:
    assert verdict(None, 4).status == "error"
