"""The template of a recorded scenario: who plays, from which data, what is seen."""

import pytest

from quality_console.gherkin_files import load_features
from quality_console.scenario_template import RECORDED_TAG, feature_problems, problems
from tests.metadata import metadata_test
from tests.neighbours import PROJECT_ROOT

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

READY = """
Feature: Order on the page
  Scenario: A customer orders
    Given "ada", a customer of the company who can order
    And the stock of "BK-0004" holds at least 1 item
    When "ada" orders 1 "BK-0004" on the storefront page
    Then the page shows every step done and the order paid
"""
"""A draft that follows the template."""


def test_a_draft_in_the_template_is_ready() -> None:
    assert problems(READY) == []


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (
            ('Given "ada", a customer of the company who can order\n    And', "Given"),
            "No actor",
        ),
        (
            ("a customer of the company who can order", "the customer"),
            "without account type",
        ),
        (('And the stock of "BK-0004" holds at least 1 item\n', ""), "No data recipe"),
        (
            ("Then the page shows every step done and the order paid", ""),
            "Nothing observed",
        ),
        (("holds at least 1 item", "holds stock on 2026-10-12"), "Hardcoded date"),
    ],
)
def test_a_draft_missing_a_fact_says_which(
    change: tuple[str, str], expected: str
) -> None:
    draft = READY.replace(*change)

    assert any(expected in problem for problem in problems(draft)), problems(draft)


def test_every_recorded_feature_follows_the_template() -> None:
    recorded = [
        f for f in load_features(PROJECT_ROOT / "features") if RECORDED_TAG in f.tags
    ]

    assert len(recorded) >= 3
    assert {f.path: feature_problems(f) for f in recorded} == {
        f.path: [] for f in recorded
    }
