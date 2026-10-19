"""Scenario design: each journey drawn as a graph, with the paths its scenarios walk."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from quality_console.designs import load_designs, mermaid
from quality_console.gherkin_files import load_features
from quality_console.tools import NotFoundError


def designs_router(
    designs: Path, features: Path, templates: Jinja2Templates
) -> APIRouter:
    """Build the route of the scenario design tool.

    Args:
        designs: The ``designs/`` folder.
        features: The ``features/`` folder, to check every path is a scenario.
        templates: The console's templates.

    Returns:
        The router to include in the console.
    """
    router = APIRouter(prefix="/tools/designs")

    @router.get("", response_class=HTMLResponse)
    def designs_page(
        request: Request, design: str = "", scenario: str = ""
    ) -> HTMLResponse:
        """The designs on the left, the selected one drawn, a path highlighted."""
        found = load_designs(designs)
        selected = next((d for d in found if d.key == design), None)
        if design and selected is None:
            raise NotFoundError(f"Unknown design: {design}")
        selected = selected or (found[0] if found else None)
        scenarios = {
            (f.path, s.name) for f in load_features(features) for s in f.scenarios
        }
        return templates.TemplateResponse(
            request,
            "designs.html",
            {
                "section": "tools",
                "designs": found,
                "selected": selected,
                "scenario": scenario,
                "diagram": mermaid(selected, scenario) if selected else "",
                "problems": selected.problems(scenarios) if selected else [],
            },
        )

    return router
