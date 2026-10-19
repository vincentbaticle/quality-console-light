"""Reading the Gherkin features of ``features/``, one folder per product.

A small parser of the subset the features use: tags, a feature and its
description, a background, scenarios with their goal (the free text under the
``Scenario:`` line) and their steps, step tables. It only
displays: running a scenario is the runner's job, with pytest-bdd.
"""

from dataclasses import dataclass, field
from pathlib import Path

STEP_KEYWORDS = ("Given", "When", "Then", "And", "But", "*")
"""Words a step line starts with."""

SCENARIO_KEYWORDS = ("Scenario Outline:", "Scenario:", "Example:")
"""Words a scenario starts with."""

TOOL_TAG = "@tool-"
"""Tag naming what drives a feature: pytest, playwright, k6, schemathesis..."""

GOAL_PREFIX = "Goal:"
"""How the free text under a scenario starts: what the scenario proves."""


@dataclass
class Step:
    """One line of a scenario, with its table rows if any."""

    keyword: str
    text: str
    table: list[list[str]] = field(default_factory=list)


@dataclass
class Scenario:
    """A scenario and its steps."""

    name: str
    tags: list[str]
    goal: str = ""
    steps: list[Step] = field(default_factory=list)
    examples: list[list[str]] = field(default_factory=list)


@dataclass
class Feature:
    """A feature file."""

    path: str
    section: str
    name: str
    tags: list[str]
    description: str
    background: list[Step] = field(default_factory=list)
    scenarios: list[Scenario] = field(default_factory=list)

    @property
    def tools(self) -> list[str]:
        """What drives the feature, from its ``@tool-`` tags."""
        return [t.removeprefix(TOOL_TAG) for t in self.tags if t.startswith(TOOL_TAG)]


class _Reader:
    """Reads a feature line by line, remembering where the next line belongs."""

    def __init__(self, path: str) -> None:
        self.feature = Feature(path, path.split("/", 1)[0], "", [], "")
        self.tags: list[str] = []
        self.description: list[str] = []
        self.steps: list[Step] | None = None
        self.in_examples = False

    def read(self, line: str) -> None:
        """Place one non-empty, non-comment line."""
        if line.startswith("@"):
            self.tags += line.split()
        elif line.startswith("Feature:"):
            self.feature.name = line.removeprefix("Feature:").strip()
            self.feature.tags, self.tags = self.tags, []
        elif line.startswith("Background:"):
            self.steps = self.feature.background
        elif line.startswith(SCENARIO_KEYWORDS):
            self._scenario(line.split(":", 1)[1].strip())
        elif line.startswith("Examples:"):
            self.in_examples = True
        elif line.startswith("|"):
            self._row([cell.strip() for cell in line.strip("|").split("|")])
        elif self.steps is not None and line.split(" ", 1)[0] in STEP_KEYWORDS:
            keyword, _, rest = line.partition(" ")
            self.steps.append(Step(keyword, rest))
        elif self.steps is None:
            self.description.append(line)
        elif self.feature.scenarios and not self.steps and not self.in_examples:
            scenario = self.feature.scenarios[-1]
            text = line.removeprefix(GOAL_PREFIX).strip() if not scenario.goal else line
            scenario.goal = f"{scenario.goal} {text}".strip()

    def _scenario(self, name: str) -> None:
        """Open a scenario."""
        self.feature.scenarios.append(Scenario(name, self.tags))
        self.tags = []
        self.in_examples = False
        self.steps = self.feature.scenarios[-1].steps

    def _row(self, cells: list[str]) -> None:
        """A table row: of the examples, or of the last step."""
        if self.in_examples and self.feature.scenarios:
            self.feature.scenarios[-1].examples.append(cells)
        elif self.steps:
            self.steps[-1].table.append(cells)


def parse_feature(text: str, path: str) -> Feature:
    """Parse one feature file.

    Args:
        text: Content of the file.
        path: Its path relative to ``features/``, ``<section>/<name>.feature``.

    Returns:
        The feature, its background and its scenarios, an outline with the
        rows of its examples, the header row first.
    """
    reader = _Reader(path)
    for raw in text.splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            reader.read(line)
    reader.feature.description = " ".join(reader.description)
    return reader.feature


def load_features(root: Path) -> list[Feature]:
    """Read every feature file under a folder, sorted by path.

    Args:
        root: The ``features/`` folder.

    Returns:
        The features.
    """
    return [
        parse_feature(file.read_text(), file.relative_to(root).as_posix())
        for file in sorted(root.glob("*/*.feature"))
    ]
