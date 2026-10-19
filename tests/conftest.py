"""Hooks every test shares."""

from collections.abc import Callable

import pytest

from tests.metadata import METADATA_MARKER


@pytest.fixture(autouse=True)
def declare_test_metadata(
    request: pytest.FixtureRequest, record_property: Callable[[str, object], None]
) -> None:
    """Write the test's ``metadata`` marker as JUnit properties.

    The closest marker wins: one on the test overrides one on its class, which
    overrides the module's ``pytestmark``. The uploader aggregates those
    properties into the run's ``test_meta``, and the console filters runs on
    them (system, product, component...), the way a test runner's metadata
    decorator feeds its results dashboard.
    """
    marker = request.node.get_closest_marker(METADATA_MARKER)
    if marker is None:
        return
    for name, value in marker.kwargs.items():
        record_property(name, value)


def pytest_addoption(parser: pytest.Parser) -> None:
    """Options of the acceptance runs: which feature, which scenario."""
    group = parser.getgroup("acceptance", "Gherkin scenarios of features/")
    group.addoption(
        "--only-feature",
        default="",
        help="Run only this feature, its path relative to features/",
    )
    group.addoption(
        "--only-scenario", default="", help="Run only the scenario of this exact name"
    )
