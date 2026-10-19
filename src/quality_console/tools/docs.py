"""Documentation: every page of ``docs/``, one per tool or product, and the guides.

Each tool keeps its blue box, the help of the page itself; the full page of a
tool lives here, and the header of the tool links to it.
"""

from itertools import groupby
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from quality_console.docs_files import DOCS_PATH, GUIDES, load_docs
from quality_console.tools import NotFoundError


def docs_router(root: Path, templates: Jinja2Templates) -> APIRouter:
    """Build the route of the documentation tool.

    Args:
        root: The ``docs`` folder.
        templates: The console's templates.

    Returns:
        The router to include in the console.
    """
    router = APIRouter(prefix=DOCS_PATH)

    @router.get("", response_class=HTMLResponse)
    def documentation(request: Request, page: str = GUIDES[0]) -> HTMLResponse:
        """Every page on the left, the chosen one on the right."""
        docs = load_docs(root)
        selected = next((d for d in docs if d.slug == page), None)
        if selected is None:
            raise NotFoundError(f"Unknown documentation page: {page}")
        return templates.TemplateResponse(
            request,
            "docs.html",
            {
                "section": "tools",
                "groups": [
                    (name, list(pages))
                    for name, pages in groupby(docs, key=lambda d: d.group)
                ],
                "selected": selected,
            },
        )

    return router
