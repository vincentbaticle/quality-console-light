"""Release announcements: the drafts of ``/announce-release``, as Slack shows them.

The skill drafts a short announcement for a whole system from the changelogs of
its components; the draft is saved in ``announcements/`` and the developer
sends it. The page shows each draft and where the next run starts.
"""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from quality_console.announcements import load_announcements, starting_points


def announcements_router(root: Path, templates: Jinja2Templates) -> APIRouter:
    """Build the route of the release announcements.

    Args:
        root: The ``announcements/`` folder.
        templates: The console's templates.

    Returns:
        The router to include in the console.
    """
    router = APIRouter(prefix="/tools/announcements")

    @router.get("", response_class=HTMLResponse)
    def announcements(request: Request) -> HTMLResponse:
        """Every announcement, newest first, and each system's starting point."""
        found = load_announcements(root)
        return templates.TemplateResponse(
            request,
            "announcements.html",
            {
                "section": "tools",
                "announcements": found,
                "starts": starting_points(found),
            },
        )

    return router
