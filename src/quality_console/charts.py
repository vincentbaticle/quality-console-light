"""Charts drawn on the server as inline SVG: no JavaScript, works offline.

The pass rate chart of a job reads like the one of the results dashboard it
imitates: a smoothed pass rate line over dated runs, each point colored by the
run's own status, failed runs shaded, the selected run ringed. Every point
links to its run.
"""

from collections.abc import Callable
import datetime
from urllib.parse import quote

from markupsafe import Markup, escape

from test_results.models import RunMetadata
from test_results.trends import normalize_status, rolling_pass_rate

WIDTH = 720
"""Width of the drawing in SVG units; the chart scales to its container."""

HEIGHT = 240
"""Height of the drawing in SVG units."""

MARGIN_LEFT = 44
"""Room for the percentage labels."""

MARGIN_RIGHT = 16
"""Room after the newest point."""

MARGIN_TOP = 16
"""Room above 100%."""

MARGIN_BOTTOM = 36
"""Room for the date labels."""

GRID_STEPS = (0, 25, 50, 75, 100)
"""Percentages a horizontal grid line marks."""

MAX_DATE_LABELS = 8
"""Most date labels the axis shows, so they never overlap."""

POINT_RADIUS = 4
"""Radius of a run's point."""

SELECTED_RADIUS = 8
"""Radius of the ring around the selected run."""

STATUS_COLORS = {"success": "#22c55e", "failed": "#ef4444", "unknown": "#8b5cf6"}
"""Point color per run status, the same as the status badges."""


def _x_of(count: int) -> Callable[[int], float]:
    """Map a run's position to its horizontal coordinate."""
    plot = WIDTH - MARGIN_LEFT - MARGIN_RIGHT
    step = plot / max(count, 1)
    return lambda index: MARGIN_LEFT + step * (index + 0.5)


def _y_of(rate: float) -> float:
    """Map a percentage to its vertical coordinate."""
    plot = HEIGHT - MARGIN_TOP - MARGIN_BOTTOM
    return MARGIN_TOP + plot * (1 - rate / 100)


def _date(run: RunMetadata) -> str:
    """Day and month of a run, as the axis shows it."""
    return datetime.datetime.fromisoformat(run.timestamp).strftime("%d/%m")


def _grid() -> list[str]:
    """Horizontal grid lines and their percentage labels."""
    parts = []
    for rate in GRID_STEPS:
        y = _y_of(rate)
        parts.append(
            f'<line class="grid" x1="{MARGIN_LEFT}" x2="{WIDTH - MARGIN_RIGHT}" '
            f'y1="{y:.1f}" y2="{y:.1f}"/>'
            f'<text class="axis" x="{MARGIN_LEFT - 8}" y="{y + 4:.1f}" '
            f'text-anchor="end">{rate}%</text>'
        )
    return parts


def _bands(
    runs: list[RunMetadata], x: Callable[[int], float], step: float
) -> list[str]:
    """A shaded band behind every failed run."""
    height = HEIGHT - MARGIN_TOP - MARGIN_BOTTOM
    return [
        f'<rect class="failed-band" x="{x(i) - step / 2:.1f}" y="{MARGIN_TOP}" '
        f'width="{step:.1f}" height="{height}"/>'
        for i, run in enumerate(runs)
        if normalize_status(run.ci_job_status) == "failed"
    ]


def _line(rates: list[int], x: Callable[[int], float]) -> str:
    """The pass rate line, smoothed with horizontal tangents at each point."""
    points = [(x(i), _y_of(rate)) for i, rate in enumerate(rates)]
    path = f"M{points[0][0]:.1f},{points[0][1]:.1f}"
    for (x0, y0), (x1, y1) in zip(points, points[1:], strict=False):
        middle = (x0 + x1) / 2
        path += f" C{middle:.1f},{y0:.1f} {middle:.1f},{y1:.1f} {x1:.1f},{y1:.1f}"
    return f'<path class="rate-line" d="{path}"/>'


def _points(
    runs: list[RunMetadata],
    rates: list[int],
    x: Callable[[int], float],
    selected_id: str,
    link: Callable[[RunMetadata], str],
) -> list[str]:
    """One linked point per run, the selected one ringed."""
    parts = []
    for i, (run, rate) in enumerate(zip(runs, rates, strict=True)):
        status = normalize_status(run.ci_job_status)
        cx, cy = x(i), _y_of(rate)
        ring = (
            f'<circle class="selected-ring" cx="{cx:.1f}" cy="{cy:.1f}" '
            f'r="{SELECTED_RADIUS}"/>'
            if run.id == selected_id
            else ""
        )
        tooltip = escape(
            f"{run.timestamp[:16].replace('T', ' ')} UTC · {status} · "
            f"pipeline {run.pipeline_id} · pass rate {rate}%"
        )
        parts.append(
            f'<a href="{escape(link(run))}">{ring}'
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{POINT_RADIUS}" '
            f'fill="{STATUS_COLORS[status]}"><title>{tooltip}</title></circle></a>'
        )
    return parts


def _dates(runs: list[RunMetadata], x: Callable[[int], float]) -> list[str]:
    """Date labels under the axis, spread so they never overlap."""
    every = max(1, -(-len(runs) // MAX_DATE_LABELS))
    return [
        f'<text class="axis" x="{x(i):.1f}" y="{HEIGHT - 12}" '
        f'text-anchor="middle">{_date(run)}</text>'
        for i, run in enumerate(runs)
        if i % every == 0 or i == len(runs) - 1
    ]


def pass_rate_chart(history: list[RunMetadata], selected_id: str) -> Markup:
    """Draw the rolling pass rate of a job over its runs.

    Args:
        history: Runs of one job, newest first.
        selected_id: Run to ring, the one the page shows.

    Returns:
        The SVG, safe to put in a template as is.
    """
    if not history:
        return Markup("")
    runs = list(reversed(history))
    rates = rolling_pass_rate(history)
    x = _x_of(len(runs))
    step = (WIDTH - MARGIN_LEFT - MARGIN_RIGHT) / len(runs)

    def link(run: RunMetadata) -> str:
        return f"/test-results?date_range=all&tab=trends&run={quote(run.id, safe='')}"

    parts = [
        f'<svg class="chart" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" '
        f'aria-label="Rolling pass rate of the last {len(runs)} runs">',
        *_grid(),
        *_bands(runs, x, step),
        _line(rates, x),
        *_points(runs, rates, x, selected_id, link),
        *_dates(runs, x),
        "</svg>",
    ]
    return Markup("".join(parts))  # noqa: S704
