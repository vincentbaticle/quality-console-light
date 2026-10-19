"""The software catalog page: what the company runs, who owns it, how it is tested."""

import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from catalog.reader import CatalogReader
from quality_console.catalog_map import RECENT_DAYS, build_map, catalog_map_svg
from test_results.reader import ResultsReader, RunFilters

RELATION_LABELS = {
    "provides": "provides",
    "consumes": "calls",
    "publishes": "publishes",
    "subscribes": "consumes events",
}
"""How a component's link to an API reads on the page."""


def catalog_router(
    catalog: CatalogReader, templates: Jinja2Templates, results: ResultsReader
) -> APIRouter:
    """Build the route of the catalog page.

    Args:
        catalog: Reads the catalog database.
        templates: The console's templates.
        results: Reads the test runs that colour the map.

    Returns:
        The router to include in the console.
    """
    router = APIRouter()

    @router.get("/catalog", response_class=HTMLResponse)
    def catalog_page(request: Request) -> HTMLResponse:
        """Every system with its products, components, APIs and resources."""
        systems = catalog.systems()
        now = datetime.datetime.now(datetime.UTC)
        found = build_map(systems, results.runs(RunFilters()), now)
        return templates.TemplateResponse(
            request,
            "catalog.html",
            {
                "section": "catalog",
                "systems": systems,
                "resources": {r.name: r for s in systems for r in s.resources},
                "apis": {a.name: a for s in systems for a in s.apis},
                "teams": catalog.teams(),
                "relations": RELATION_LABELS,
                "map": catalog_map_svg(found),
                "recent_days": RECENT_DAYS,
            },
        )

    return router
