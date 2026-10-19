"""The catalog as a map: systems, products and components, coloured by their tests.

Three columns joined by arrows: each system points to its products and its
components, a component calling another one's API (or consuming its events)
points to it. Each item is coloured by what the test results say of it, read
from the facets the tests declare (``system``, ``product``, ``component``):

- grey: no run ever named it, no test is known;
- green: every job naming it ran lately and its last run passed;
- red: the last run of a job naming it failed;
- between grey and green: only part of its known jobs ran lately.
"""

from dataclasses import dataclass, field
import datetime
from urllib.parse import quote

from markupsafe import Markup, escape

from catalog.reader import SystemView
from test_results.models import RunMetadata
from test_results.trends import normalize_status

RECENT_DAYS = 7
"""A job that ran in this many days counts as executed lately."""

UNTESTED, PASSING, PARTIAL, FAILING = "untested", "passing", "partial", "failing"
"""What the colour of an item says."""

FACETS = {"system": "system", "product": "product", "component": "component"}
"""The test facet that names each kind of item."""

NODE_WIDTH, NODE_HEIGHT, ROW_GAP = 236, 50, 14
"""Size of an item on the map, and the space between two of a column."""

COLUMNS = {"system": 16, "product": 340, "component": 664}
"""Left edge of each column."""

TOP = 40
"""Room above the first row, for the column titles."""

CALL_BULGE, CALL_BULGE_PER_ROW = 30, 12
"""How far right of the components an arrow between two of them bends, and how
much further for each row it crosses, so that long arrows pass outside short ones."""

ICONS = {
    "system": "M4 7l8-4 8 4-8 4zM4 12l8 4 8-4M4 17l8 4 8-4",
    "product": "M6 8h12l-1 12H7zM9 8a3 3 0 0 1 6 0",
    "website": "M3 5h18v14H3zM3 9h18",
    "service": "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c3 3 3 15 0 18",
    "worker": "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM12 2v3M12 19v3M2 12h3M19 12h3",
    "external": "M7 18a4 4 0 0 1 0-8 5 5 0 0 1 9.6-1.5A4 4 0 0 1 17 18z",
    "test-suite": "M4 12l5 5L20 6",
    "library": "M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3zM5 17a3 3 0 0 1 3-3h11",
}
"""One small line icon per kind of item, components by their type."""


@dataclass(frozen=True)
class Health:
    """What the test results say of one item."""

    status: str
    known: int
    executed: int
    failing: list[str]
    last_run: str
    passed: int = 0
    total: int = 0

    @property
    def ratio(self) -> float:
        """Share of the known jobs that ran lately."""
        return self.executed / self.known if self.known else 0.0

    @property
    def summary(self) -> str:
        """One line under the item's name."""
        if self.status == UNTESTED:
            return "no test known"
        tests = f"{self.passed}/{self.total} tests passed · " if self.total else ""
        if self.status == FAILING:
            jobs = len(self.failing)
            return f"{tests}{jobs} {'job' if jobs == 1 else 'jobs'} failed"
        return f"{tests}{self.executed}/{self.known} jobs lately"

    @property
    def details(self) -> str:
        """Everything the tooltip says: the failing jobs and their counts."""
        lines = [self.summary]
        lines += [f"failed: {job}" for job in self.failing]
        if self.last_run:
            lines.append(f"last run {self.last_run[:16].replace('T', ' ')}")
        return "\n".join(lines)


@dataclass
class Node:
    """An item placed on the map."""

    kind: str
    name: str
    title: str
    icon: str
    health: Health
    x: int = 0
    y: int = 0


@dataclass
class CatalogMap:
    """Every item placed, and the arrows between them."""

    nodes: dict[str, Node] = field(default_factory=dict)
    links: list[tuple[str, str]] = field(default_factory=list)
    calls: list[tuple[str, str]] = field(default_factory=list)
    height: int = 0


def health(
    facet: str, name: str, runs: list[RunMetadata], now: datetime.datetime
) -> Health:
    """Read the test results of one item.

    Args:
        facet: The test facet naming this kind of item.
        name: The item.
        runs: Every indexed run, newest first.
        now: The time "lately" is counted from.

    Returns:
        Its colour, how many jobs are known and ran lately, which failed last.
    """
    latest: dict[tuple[str, str], RunMetadata] = {}
    for run in runs:
        if name in run.test_meta.get(facet, []):
            latest.setdefault((run.job_name, run.env), run)
    if not latest:
        return Health(UNTESTED, 0, 0, [], "")
    since = now - datetime.timedelta(days=RECENT_DAYS)
    executed = sum(
        1
        for run in latest.values()
        if datetime.datetime.fromisoformat(run.timestamp) >= since
    )
    failing = sorted(
        f"{job} ({env}){_counts(run)}"
        for (job, env), run in latest.items()
        if normalize_status(run.ci_job_status) == "failed"
    )
    status = FAILING if failing else PASSING if executed == len(latest) else PARTIAL
    last_run = max(run.timestamp for run in latest.values())
    return Health(
        status,
        len(latest),
        executed,
        failing,
        last_run,
        passed=sum(run.test_counts.get("passed", 0) for run in latest.values()),
        total=sum(run.test_counts.get("total", 0) for run in latest.values()),
    )


def _counts(run: RunMetadata) -> str:
    """How much of a failed run passed: ``, 8/10 passed, 2 errors``."""
    counts = run.test_counts
    if not counts.get("total"):
        return ""
    parts = [f"{counts['passed']}/{counts['total']} passed"]
    for key, word in (("failed", "failed"), ("errors", "errors")):
        if counts.get(key):
            parts.append(f"{counts[key]} {word}")
    return ": " + ", ".join(parts)


def component_calls(systems: list[SystemView]) -> list[tuple[str, str]]:
    """Who calls whom: consumer to provider, publisher to subscriber.

    Args:
        systems: The catalog.

    Returns:
        The arrows between components, as pairs of map keys.
    """
    components = [c for s in systems for c in s.components]
    providers = {api: c.name for c in components for api in c.apis.get("provides", [])}
    calls = []
    for component in components:
        calls += [
            (component.name, providers[api])
            for api in component.apis.get("consumes", [])
            if providers.get(api, component.name) != component.name
        ]
        calls += [
            (publisher.name, component.name)
            for api in component.apis.get("subscribes", [])
            for publisher in components
            if api in publisher.apis.get("publishes", [])
            and publisher.name != component.name
        ]
    return [(f"component:{a}", f"component:{b}") for a, b in calls]


def build_map(
    systems: list[SystemView], runs: list[RunMetadata], now: datetime.datetime
) -> CatalogMap:
    """Place every item, one band per system, its products and components beside it.

    Each system opens a band of rows as tall as its longest column, so its
    arrows run straight across and never cross another system's.

    Args:
        systems: The catalog.
        runs: Every indexed run, newest first.
        now: The time "lately" is counted from.

    Returns:
        The map, ready to draw.
    """
    found = CatalogMap()
    band = 0
    rows = {"system": 0, "product": 0, "component": 0}

    def place(kind: str, key: str, name: str, title: str, icon: str) -> None:
        node = Node(kind, name, title, icon, health(FACETS[kind], name, runs, now))
        node.x = COLUMNS[kind]
        node.y = TOP + rows[kind] * (NODE_HEIGHT + ROW_GAP)
        rows[kind] += 1
        found.nodes[key] = node

    for system in systems:
        rows = dict.fromkeys(rows, band)
        place("system", f"system:{system.name}", system.name, system.title, "system")
        for product in system.products:
            key = f"product:{product.name}"
            place("product", key, product.name, product.title, "product")
            found.links.append((f"system:{system.name}", key))
        for component in system.components:
            key = f"component:{component.name}"
            icon = component.type if component.type in ICONS else "service"
            place("component", key, component.name, component.title, icon)
            found.links.append((f"system:{system.name}", key))
        band = max(rows.values())
    found.calls = component_calls(systems)
    found.height = TOP + band * (NODE_HEIGHT + ROW_GAP)
    return found


def _href(node: Node) -> str:
    """The test runs of an item, in the test results page."""
    return f"/test-results?date_range=all&{node.kind}={quote(node.name)}"


def _colour(node: Node) -> str:
    """The colour of an item: a CSS value, mixed for a partial one."""
    if node.health.status == PARTIAL:
        share = round(node.health.ratio * 100)
        return f"color-mix(in srgb, var(--positive) {share}%, var(--fg-muted))"
    return {
        UNTESTED: "var(--fg-muted)",
        PASSING: "var(--positive)",
        FAILING: "var(--negative)",
    }[node.health.status]


def _node(node: Node) -> str:
    """One item: a card with its icon, its name and what its tests say."""
    colour = _colour(node)
    tip = f"{node.title} ({node.kind})\n{node.health.details}"
    bar = round(NODE_WIDTH * node.health.ratio)
    return (
        f'<a href="{escape(_href(node))}" class="map-node {node.health.status}"'
        f' style="--node: {colour}"><title>{escape(tip)}</title>'
        f'<rect x="{node.x}" y="{node.y}" width="{NODE_WIDTH}" height="{NODE_HEIGHT}"'
        ' rx="10" class="map-card"/>'
        f'<rect x="{node.x}" y="{node.y + NODE_HEIGHT - 4}" width="{bar}" height="4"'
        ' class="map-bar"/>'
        f'<g transform="translate({node.x + 12} {node.y + 13})" class="map-icon">'
        f'<path d="{ICONS[node.icon]}"/></g>'
        f'<text x="{node.x + 46}" y="{node.y + 22}" class="map-title">'
        f"{escape(node.title)}</text>"
        f'<text x="{node.x + 46}" y="{node.y + 38}" class="map-sub">'
        f"{escape(node.health.summary[:40])}</text></a>"
    )


def _link(start: Node, end: Node) -> str:
    """An arrow from a system to one of its items, left to right."""
    x1, y1 = start.x + NODE_WIDTH, start.y + NODE_HEIGHT / 2
    x2, y2 = end.x - 6, end.y + NODE_HEIGHT / 2
    middle = (x1 + x2) / 2
    return (
        f'<path d="M{x1} {y1} C{middle} {y1} {middle} {y2} {x2} {y2}"'
        ' class="map-link" marker-end="url(#map-arrow)"/>'
    )


def _call(start: Node, end: Node) -> str:
    """An arrow between two components, bending out to the right."""
    x = start.x + NODE_WIDTH
    y1, y2 = start.y + NODE_HEIGHT / 2, end.y + NODE_HEIGHT / 2
    rows = abs(y2 - y1) / (NODE_HEIGHT + ROW_GAP)
    bend = x + CALL_BULGE + CALL_BULGE_PER_ROW * rows
    return (
        f'<path d="M{x} {y1} C{bend} {y1} {bend} {y2} {x + 6} {y2}"'
        ' class="map-call" marker-end="url(#map-arrow-call)"/>'
    )


def catalog_map_svg(found: CatalogMap) -> Markup:
    """Draw the map.

    Args:
        found: The items placed and their arrows.

    Returns:
        The SVG, every item a link to its test runs.
    """
    width = COLUMNS["component"] + NODE_WIDTH + 140
    titles = "".join(
        f'<text x="{x}" y="22" class="map-column">{label}</text>'
        for label, x in (
            ("Systems", COLUMNS["system"]),
            ("Products", COLUMNS["product"]),
            ("Components, and who calls whom", COLUMNS["component"]),
        )
    )
    arrows = "".join(
        _link(found.nodes[a], found.nodes[b]) for a, b in found.links
    ) + "".join(_call(found.nodes[a], found.nodes[b]) for a, b in found.calls)
    nodes = "".join(_node(node) for node in found.nodes.values())
    return Markup(  # noqa: S704
        f'<svg viewBox="0 0 {width} {found.height}" class="catalog-map" role="img"'
        ' aria-label="Systems, products and components, coloured by their tests">'
        '<defs><marker id="map-arrow" viewBox="0 0 10 10" refX="8" refY="5"'
        ' markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M0 0L10 5L0 10z" class="map-arrowhead"/></marker>'
        '<marker id="map-arrow-call" viewBox="0 0 10 10" refX="8" refY="5"'
        ' markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M0 0L10 5L0 10z" class="map-arrowhead-call"/></marker></defs>'
        f"{titles}{arrows}{nodes}</svg>"
    )
