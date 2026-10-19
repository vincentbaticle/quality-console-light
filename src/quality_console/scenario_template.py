"""The template of a recorded scenario, and its checks.

A recording shows clicks, not who plays, from which data, nor what must be
seen at the end. A recorded scenario says the three, in a fixed shape:

- one ``Given`` per actor: ``"<actor>", a <account type> who <rights>``, the
  account and its rights being part of the test data (the person who recorded
  played with their own account and would not think to say so);
- at least one other ``Given``: the recipe of the data the journey starts from;
- at least one ``Then``: what is observed.

One scenario, no examples table, no hardcoded date. Features tagged
``@recorded`` follow it; ``problems`` says what a draft misses.
"""

import re
from typing import Final

from quality_console.gherkin_files import Feature, Scenario, Step, parse_feature

RECORDED_TAG: Final[str] = "@recorded"
"""Tag of a feature written from a recording, in this template."""

ACTOR: Final[re.Pattern[str]] = re.compile(
    r'^"(?P<actor>[^"]+)", an? (?P<account>.+?) who (?P<rights>.+)$'
)
"""An actor line: who plays, the account type, the rights in business words."""

HARDCODED_DATE: Final[re.Pattern[str]] = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b"
)
"""A date written in a step: it ages, the scenario breaks a day later."""


def _kinds(steps: list[Step]) -> list[tuple[str, Step]]:
    """Each step with its real keyword, an ``And`` or ``But`` taking the previous."""
    kinds = []
    current = "Given"
    for step in steps:
        if step.keyword not in ("And", "But", "*"):
            current = step.keyword
        kinds.append((current, step))
    return kinds


def scenario_problems(scenario: Scenario) -> list[str]:
    """What a scenario misses to follow the template.

    Args:
        scenario: One scenario.

    Returns:
        One sentence per problem, none when it follows the template.
    """
    found = []
    steps = _kinds(scenario.steps)
    givens = [step.text for kind, step in steps if kind == "Given"]
    actors = [text for text in givens if ACTOR.match(text)]
    if not actors:
        found.append(
            "No actor: add one Given per account that plays, "
            '"<actor>", a <account type> who <rights>.'
        )
    unclear = [
        text for text in givens if text.startswith('"') and not ACTOR.match(text)
    ]
    found += [f'Actor without account type or rights: "{text}".' for text in unclear]
    if len(givens) - len(actors) - len(unclear) < 1:
        found.append("No data recipe: add a Given saying what data the journey needs.")
    if not any(kind == "Then" for kind, _ in steps):
        found.append("Nothing observed: add a Then saying what must be seen.")
    dated = [step.text for _, step in steps if HARDCODED_DATE.search(step.text)]
    found += [f'Hardcoded date: "{text}", compute it instead.' for text in dated]
    if scenario.examples:
        found.append("An examples table: a recorded scenario plays one journey.")
    return found


def feature_problems(feature: Feature) -> list[str]:
    """What a recorded feature misses, scenario by scenario.

    Args:
        feature: A feature, tagged ``@recorded`` or a draft.

    Returns:
        One line per problem, prefixed by its scenario.
    """
    if not feature.scenarios:
        return ["No scenario."]
    found = []
    if len(feature.scenarios) > 1:
        found.append("More than one scenario: one recording, one scenario.")
    for scenario in feature.scenarios:
        found += [f"{scenario.name}: {p}" for p in scenario_problems(scenario)]
    return found


def problems(text: str) -> list[str]:
    """Check a draft written in the template.

    Args:
        text: The Gherkin of a feature with its scenario.

    Returns:
        What it misses, nothing when it is ready to become a test.
    """
    return feature_problems(parse_feature(text, "draft/draft.feature"))
