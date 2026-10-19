"""Gherkin scenarios: the features of ``features/`` by product, and a Run button.

Each folder of ``features/`` is a product of the catalog, which gives the
section its title and its purpose. Clicking a feature or a scenario asks the
Gherkin runner to run it against the stack, and shows the verdict.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import httpx

from catalog.reader import CatalogReader, ProductRow
from quality_console.gherkin_files import Feature, load_features
from quality_console.tools import NotFoundError

SECTION_ORDER = (
    "customer-welcome",
    "checkout",
    "account-access",
    "partner-contracts",
    "bucket-checks",
    "quality-console",
)
"""Order of the sections: the customer's journey first, the back office last."""

UNTAGGED = "other"
"""The filter of the features naming no tool."""


@dataclass
class Section:
    """The features of one product."""

    name: str
    title: str
    purpose: str
    features: list[Feature] = field(default_factory=list)


def sections(features: list[Feature], products: dict[str, ProductRow]) -> list[Section]:
    """Group the features by product, in the order of the journey.

    Args:
        features: Every feature.
        products: The products of the catalog, by name.

    Returns:
        One section per folder; a folder the catalog does not know is listed
        last under its own name.
    """
    found: dict[str, Section] = {}
    for feature in features:
        product = products.get(feature.section)
        section = found.setdefault(
            feature.section,
            Section(
                feature.section,
                product.title if product else feature.section,
                product.description if product else "",
            ),
        )
        section.features.append(feature)

    def rank(section: Section) -> int:
        return (
            SECTION_ORDER.index(section.name)
            if section.name in SECTION_ORDER
            else len(SECTION_ORDER)
        )

    return sorted(found.values(), key=rank)


def tool_counts(features: list[Feature]) -> list[tuple[str, int]]:
    """Each tool driving a feature, with its number of features, most used first.

    A feature naming no tool counts under ``other``.
    """
    counts: dict[str, int] = {}
    for feature in features:
        for tool in feature.tools or [UNTAGGED]:
            counts[tool] = counts.get(tool, 0) + 1
    return sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))


def driven_by(features: list[Feature], tool: str) -> list[Feature]:
    """The features the tool drives, every feature for an empty tool."""
    if not tool:
        return features
    return [f for f in features if tool in (f.tools or [UNTAGGED])]


def gherkin_router(
    catalog: CatalogReader,
    root: Path,
    runner: httpx.Client,
    templates: Jinja2Templates,
    live: dict[str, str] | None = None,
) -> APIRouter:
    """Build the routes of the Gherkin tool.

    Args:
        catalog: Gives each product's title and purpose.
        root: The ``features/`` folder.
        runner: HTTP client of the Gherkin runner.
        templates: The console's templates.
        live: Where each product can be tried by hand, by product name.

    Returns:
        The router to include in the console.
    """
    router = APIRouter(prefix="/tools/gherkin")

    def page(
        request: Request, result: dict[str, Any] | None, tool: str
    ) -> HTMLResponse:
        found = load_features(root)
        tools = tool_counts(found)
        if tool and tool not in dict(tools):
            raise NotFoundError(f"Unknown tool: {tool}")
        return templates.TemplateResponse(
            request,
            "gherkin.html",
            {
                "section": "tools",
                "sections": sections(driven_by(found, tool), catalog.products()),
                "tools": tools,
                "tool": tool,
                "total": len(found),
                "result": result,
                "live": live or {},
            },
        )

    @router.get("", response_class=HTMLResponse)
    def features(request: Request, tool: str = "") -> HTMLResponse:
        """Every feature by product, or only the ones a tool drives."""
        return page(request, None, tool)

    @router.post("/run", response_class=HTMLResponse)
    def run(
        request: Request, feature: str, scenario: str = "", tool: str = ""
    ) -> HTMLResponse:
        """Ask the runner to run a feature or a scenario, show the verdict."""
        if feature not in {f.path for f in load_features(root)}:
            raise NotFoundError(f"Unknown feature: {feature}")
        try:
            response = runner.post(
                "/runs", json={"feature": feature, "scenario": scenario}
            )
            response.raise_for_status()
            result = response.json()
        except httpx.HTTPError as exc:
            result = {
                "feature": feature,
                "scenario": scenario,
                "status": "error",
                "output": f"The Gherkin runner did not answer: {exc}",
                "run_id": "",
            }
        return page(request, result, tool)

    return router
