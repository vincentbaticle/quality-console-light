"""Database pages of the console: every database the account reads, its tables, rows."""

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from quality_console.databases import DatabaseBrowser
from quality_console.table_kinds import LIVE, table_kind

SEARCH_MODES = {"exact": True, "contains": False}
"""Search modes the table page offers, and whether each is an exact match."""


def database_router(browser: DatabaseBrowser, templates: Jinja2Templates) -> APIRouter:
    """Build the routes of the database pages.

    Args:
        browser: Reads the databases with the console's read-only account.
        templates: The console's templates.

    Returns:
        The router to include in the console.
    """
    router = APIRouter(prefix="/databases")

    @router.get("", response_class=HTMLResponse)
    def databases(request: Request) -> HTMLResponse:
        """List the databases the account can read."""
        return templates.TemplateResponse(
            request,
            "databases.html",
            {"databases": browser.databases(), "user": browser.user},
        )

    @router.get("/{database}", response_class=HTMLResponse)
    def database(request: Request, database: str) -> HTMLResponse:
        """List the tables of a database with their row counts, live ones first."""
        tables = browser.tables(database)
        return templates.TemplateResponse(
            request,
            "database.html",
            {
                "database": database,
                "tables": tables,
                "live_names": [
                    t.name for t in tables if table_kind(database, t.name) == LIVE
                ],
            },
        )

    @router.get("/{database}/tables/{table}", response_class=HTMLResponse)
    def table(
        request: Request,
        database: str,
        table: str,
        column: str = "",
        value: str = "",
        mode: str = "exact",
    ) -> HTMLResponse:
        """Show the rows of a table, filtered on one column when asked."""
        content = browser.content(
            database,
            table,
            column if value else "",
            value,
            exact=SEARCH_MODES.get(mode, True),
        )
        return templates.TemplateResponse(
            request,
            "table.html",
            {
                "database": database,
                "table": table,
                "content": content,
                "column": column,
                "value": value,
                "mode": mode,
                "modes": list(SEARCH_MODES),
            },
        )

    return router
