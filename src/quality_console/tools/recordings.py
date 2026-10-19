"""Recordings: what the captures recorded, and which tests replay it."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from quality_console.recordings import load_recordings


def recordings_router(
    capture: Path, contracts: Path, templates: Jinja2Templates
) -> APIRouter:
    """Build the route of the recordings tool.

    Args:
        capture: The ``capture/`` folder holding the journals.
        contracts: The ``contracts/`` folder holding the merged examples.
        templates: The console's templates.

    Returns:
        The router to include in the console.
    """
    router = APIRouter(prefix="/tools/recordings")

    @router.get("", response_class=HTMLResponse)
    def recordings(request: Request) -> HTMLResponse:
        """Every recording: journal, examples, the tests replaying them."""
        return templates.TemplateResponse(
            request,
            "recordings.html",
            {"section": "tools", "recordings": load_recordings(capture, contracts)},
        )

    return router
