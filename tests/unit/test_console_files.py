"""What the console's tools read from the repository: features, folders."""

import pytest

from quality_console.gherkin_files import load_features, parse_feature
from quality_console.tools.bucket import crumbs
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

FEATURE = """
Feature: Greet a customer
  Said once, read twice.

  Background:
    Given the storefront is running

  Scenario: Ada is greeted
    Goal: a known customer is greeted
    by first name.
    When "ada" asks for a greeting
    Then the greeting is
      | first name | Ada |
"""
"""A feature with a description, a background, a scenario and a step table."""


def test_a_feature_is_parsed_with_its_background_and_scenarios() -> None:
    feature = parse_feature(FEATURE, "customer-welcome/greeting.feature")

    assert feature.section == "customer-welcome"
    assert feature.name == "Greet a customer"
    assert feature.description == "Said once, read twice."
    assert [s.text for s in feature.background] == ["the storefront is running"]
    scenario = feature.scenarios[0]
    assert scenario.name == "Ada is greeted"
    assert scenario.goal == "a known customer is greeted by first name."
    assert [s.keyword for s in scenario.steps] == ["When", "Then"]
    assert scenario.steps[1].table == [["first name", "Ada"]]


def test_every_feature_of_the_repository_sits_in_a_product_folder() -> None:
    features = load_features(PROJECT_ROOT / "features")

    assert {f.section for f in features} == {
        "customer-welcome",
        "checkout",
        "account-access",
        "partner-contracts",
        "bucket-checks",
        "quality-console",
    }


def test_every_scenario_of_the_repository_says_its_goal() -> None:
    features = load_features(PROJECT_ROOT / "features")

    missing = [
        f"{f.path}: {s.name}" for f in features for s in f.scenarios if not s.goal
    ]

    assert not missing
    assert all(f.scenarios for f in features)


def test_crumbs_open_each_folder_of_a_prefix() -> None:
    assert crumbs("local/backend/") == [
        ("local", "local/"),
        ("backend", "local/backend/"),
    ]
    assert crumbs("") == []
