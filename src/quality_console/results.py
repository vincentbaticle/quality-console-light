"""Test results pages of the console: the runs CI uploaded to the results bucket.

Laid out like the results dashboard it imitates: the runs on the left, with
the index age, the counters and the filters; the selected run on the right,
with a Details tab (JUnit, k6, files) and a Trends tab (the job's pass rate
over its last runs, its streak, its history). Lists and counters come from the
run index, never from a crawl on the request. Refresh rebuilds the index on
demand, which a scheduler does every 30 minutes in production. A report file
is served from the bucket, an HTML report sandboxed so it cannot script the
console.
"""

from collections.abc import Callable
import datetime
from http import HTTPStatus
from typing import Any
from urllib.parse import quote, urlencode

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from quality_console.charts import pass_rate_chart
from test_results.models import IndexHeader, RunMetadata
from test_results.reader import STATUS_FILTERS, ResultsReader, RunFilters
from test_results.trends import (
    current_streak,
    job_history,
    job_summaries,
    normalize_status,
    pass_rate,
)

PAGE_SIZE = 50
"""Runs shown on the list, the newest ones."""

DATE_RANGES = {"24h": 1, "7d": 7, "30d": 30, "all": None}
"""Date range presets of the list, in days; ``all`` has no bound."""

DEFAULT_DATE_RANGE = "7d"
"""Preset the list opens on, as the dashboard it imitates does."""

FACET_FILTERS = ("system", "product", "component", "testing_scope", "group", "tags")
"""Test metadata facets offered as filters."""

LIST_FILTERS = ("env", "artifact_type", "status", "job_name")
"""Run fields offered as filters."""

TABS = ("details", "trends")
"""Tabs of the selected run."""

SANDBOX_POLICY = "sandbox"
"""Content-Security-Policy of a served HTML report: no script, no same origin."""

SECONDS_PER_MINUTE = 60
"""Seconds in a minute, to say how old the index is."""


def _index_age_minutes(header: IndexHeader | None) -> int | None:
    """Minutes since the index was generated, None before the first one."""
    if header is None:
        return None
    generated = datetime.datetime.fromisoformat(header.generated_at)
    age = datetime.datetime.now(datetime.UTC) - generated
    return int(age.total_seconds() // SECONDS_PER_MINUTE)


def _since(date_range: str) -> str:
    """Oldest ISO timestamp a date range keeps, empty for no bound."""
    days = DATE_RANGES.get(date_range, DATE_RANGES[DEFAULT_DATE_RANGE])
    if days is None:
        return ""
    start = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=days)
    return start.isoformat()


def _trends(runs: list[RunMetadata], run: RunMetadata) -> dict[str, Any]:
    """Everything the Trends tab of a run shows about its job."""
    history = job_history(runs, run.job_name, run.artifact_type, run.env)
    return {
        "history": history,
        "chart": pass_rate_chart(history, run.id),
        "pass_rate": pass_rate(history),
        "passed": sum(1 for r in history if r.ci_job_status == "success"),
        "streak": current_streak(history),
    }


def results_router(
    reader: ResultsReader,
    rebuild: Callable[[], IndexHeader],
    templates: Jinja2Templates,
) -> APIRouter:
    """Build the routes of the test results pages.

    Args:
        reader: Reads the index and the run folders.
        rebuild: Rebuilds the index now, the job a scheduler runs in production.
        templates: The console's templates.

    Returns:
        The router to include in the console.
    """
    router = APIRouter(prefix="/test-results")
    templates.env.filters["status"] = normalize_status

    @router.get("", response_class=HTMLResponse)
    def runs(
        request: Request,
        date_range: str = DEFAULT_DATE_RANGE,
        run: str = "",
        tab: str = "details",
    ) -> HTMLResponse:
        """The runs on the left, the selected run and its tabs on the right."""
        params = request.query_params
        chosen = {name: params.get(name, "") for name in LIST_FILTERS + FACET_FILTERS}
        filters = RunFilters(
            chosen["env"],
            chosen["artifact_type"],
            chosen["status"],
            chosen["job_name"],
            {name: chosen[name] for name in FACET_FILTERS},
        )
        header = reader.header()
        everything = reader.runs(RunFilters())
        since = _since(date_range)
        selected = [r for r in reader.runs(filters) if r.timestamp >= since]
        keep = {k: v for k, v in params.items() if k not in ("run", "tab") and v}
        context: dict[str, Any] = {
            "header": header,
            "age": _index_age_minutes(header),
            "stats": reader.stats(selected),
            "runs": selected[:PAGE_SIZE],
            "matching": len(selected),
            "options": reader.facet_values(everything),
            "statuses": STATUS_FILTERS,
            "date_ranges": list(DATE_RANGES),
            "chosen": {**chosen, "date_range": date_range},
            "list_filters": LIST_FILTERS,
            "facet_filters": FACET_FILTERS,
            "selected_id": run,
            "tab": tab if tab in TABS else "details",
            "tabs": TABS,
            "query": urlencode(keep),
            "detail": None,
        }
        if run:
            detail = reader.detail(run)
            context["detail"] = detail
            context["trends"] = _trends(everything, detail.metadata)
        return templates.TemplateResponse(request, "results.html", context)

    @router.get("/run")
    def run_page(id: str) -> RedirectResponse:  # noqa: A002
        """Old address of a run, kept working: the run inside the dashboard."""
        target = f"/test-results?date_range=all&run={quote(id, safe='')}"
        return RedirectResponse(target, status_code=HTTPStatus.SEE_OTHER)

    @router.post("/refresh")
    def refresh() -> RedirectResponse:
        """Rebuild the index now, then show the list again."""
        rebuild()
        return RedirectResponse("/test-results", status_code=HTTPStatus.SEE_OTHER)

    @router.get("/trends", response_class=HTMLResponse)
    def trends(request: Request) -> HTMLResponse:
        """Every job at a glance: last runs, pass rate, streak, latest run."""
        return templates.TemplateResponse(
            request,
            "trends.html",
            {"jobs": job_summaries(reader.runs(RunFilters()))},
        )

    @router.get("/artifact")
    def artifact(path: str) -> Response:
        """Serve one report file from the bucket."""
        content, content_type = reader.artifact(path)
        headers = (
            {"Content-Security-Policy": SANDBOX_POLICY}
            if content_type == "text/html"
            else {}
        )
        return Response(content, media_type=content_type, headers=headers)

    return router
