"""Scenario designs: the map of a journey, and the paths the scenarios walk.

A design draws every step a user or a file can go through, as a graph: the
states, and the transitions between them. Each Gherkin scenario is a path on
that graph. Drawn together, they show at a glance which transitions a scenario
proves and which none does yet: the gaps of the test design. Gherkin says what
one scenario checks; the design says where all of them go.

Designs are YAML files of ``designs/``, rendered as Mermaid flowcharts.
"""

from dataclasses import dataclass, field
from pathlib import Path

import yaml

NODE_SHAPES = {
    "start": ('(["', '"])'),
    "state": ('["', '"]'),
    "check": ('{{"', '"}}'),
    "outcome": ('(["', '"])'),
    "failure": ('(["', '"])'),
}
"""Mermaid shape of each kind of node: a stadium for ends, a hexagon for checks."""

NODE_CLASSES = {
    "start": "fill:#dbeafe,stroke:#2563eb,color:#0f172a",
    "state": "fill:#ffffff,stroke:#94a3b8,color:#0f172a",
    "check": "fill:#fef3c7,stroke:#b45309,color:#0f172a",
    "outcome": "fill:#dcfce7,stroke:#15803d,color:#0f172a",
    "failure": "fill:#fee2e2,stroke:#b91c1c,color:#0f172a",
}
"""Colors of each kind of node."""

COVERED_EDGE = "stroke:#64748b,stroke-width:1.5px"
"""A transition at least one scenario walks."""

GAP_EDGE = "stroke:#ef4444,stroke-width:1.5px,stroke-dasharray:5 4"
"""A transition no scenario walks yet."""

HIGHLIGHT_EDGE = "stroke:#2563eb,stroke-width:4px"
"""A transition of the selected scenario."""


@dataclass(frozen=True)
class Node:
    """A state or a check of the journey."""

    id: str
    label: str
    kind: str


@dataclass(frozen=True)
class Edge:
    """A transition, with what triggers it."""

    source: str
    target: str
    label: str


@dataclass(frozen=True)
class Walk:
    """A scenario, as the path it walks on the graph."""

    name: str
    feature: str
    nodes: list[str]

    @property
    def edges(self) -> list[tuple[str, str]]:
        """The transitions the path walks, in order."""
        return list(zip(self.nodes, self.nodes[1:], strict=False))


@dataclass
class Design:
    """One journey and its scenarios."""

    key: str
    title: str
    product: str
    purpose: str
    nodes: list[Node]
    edges: list[Edge]
    paths: list[Walk] = field(default_factory=list)

    @property
    def covered(self) -> set[tuple[str, str]]:
        """Every transition at least one scenario walks."""
        return {edge for path in self.paths for edge in path.edges}

    @property
    def gaps(self) -> list[Edge]:
        """Transitions no scenario walks."""
        return [e for e in self.edges if (e.source, e.target) not in self.covered]

    def problems(self, scenarios: set[tuple[str, str]]) -> list[str]:
        """What does not hold: unknown nodes, transitions or scenarios.

        Args:
            scenarios: Every (feature path, scenario name) of ``features/``.

        Returns:
            One line per problem, empty when the design holds together.
        """
        ids = {n.id for n in self.nodes}
        edges = {(e.source, e.target) for e in self.edges}
        found = [
            f"edge {e.source} -> {e.target} names an unknown node"
            for e in self.edges
            if e.source not in ids or e.target not in ids
        ]
        for path in self.paths:
            if (path.feature, path.name) not in scenarios:
                found.append(f"no scenario {path.name!r} in {path.feature}")
            found += [
                f"{path.name!r} walks {a} -> {b}, not an edge"
                for a, b in path.edges
                if (a, b) not in edges
            ]
        return found


def parse_design(text: str, key: str) -> Design:
    """Read one design file.

    Args:
        text: The YAML content.
        key: The file name without extension.

    Returns:
        The design.
    """
    data = yaml.safe_load(text)
    return Design(
        key=key,
        title=data["title"],
        product=data["product"],
        purpose=data["purpose"],
        nodes=[Node(n["id"], n["label"], n["kind"]) for n in data["nodes"]],
        edges=[
            Edge(e["from"], e["to"], str(e.get("label", ""))) for e in data["edges"]
        ],
        paths=[Walk(p["scenario"], p["feature"], p["path"]) for p in data["scenarios"]],
    )


def load_designs(root: Path) -> list[Design]:
    """Every design of a folder, by file name.

    Args:
        root: The ``designs/`` folder.

    Returns:
        The designs.
    """
    return [parse_design(f.read_text(), f.stem) for f in sorted(root.glob("*.yaml"))]


def _quote(text: str) -> str:
    """Make a label safe inside Mermaid quotes."""
    return text.replace('"', "'")


def mermaid(design: Design, selected: str = "") -> str:
    """Draw a design as a Mermaid flowchart.

    Args:
        design: The design.
        selected: Name of the scenario whose path is highlighted, if any.

    Returns:
        The Mermaid source: nodes shaped and colored by kind, transitions
        walked by a scenario plain, gaps dashed red, the selected path bold blue.
    """
    lines = ["flowchart TD"]
    for node in design.nodes:
        opening, closing = NODE_SHAPES[node.kind]
        lines.append(f"  {node.id}{opening}{_quote(node.label)}{closing}:::{node.kind}")
    for edge in design.edges:
        label = f'|"{_quote(edge.label)}"|' if edge.label else ""
        lines.append(f"  {edge.source} -->{label} {edge.target}")
    covered = design.covered
    highlighted = {
        edge for path in design.paths if path.name == selected for edge in path.edges
    }
    for index, edge in enumerate(design.edges):
        pair = (edge.source, edge.target)
        style = (
            HIGHLIGHT_EDGE
            if pair in highlighted
            else COVERED_EDGE
            if pair in covered
            else GAP_EDGE
        )
        lines.append(f"  linkStyle {index} {style}")
    lines += [f"  classDef {kind} {style}" for kind, style in NODE_CLASSES.items()]
    return "\n".join(lines)
