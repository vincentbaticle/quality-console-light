"""Quality Console: the back office of the quality platform and its tools."""

from http import HTTPStatus
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from catalog.reader import CatalogReader
from quality_console.catalog_pages import catalog_router
from quality_console.database_pages import database_router
from quality_console.databases import DatabaseBrowser, UnknownObjectError
from quality_console.footprint_lab import FootprintLab
from quality_console.results import results_router
from quality_console.settings import ConsoleSettings, settings_from_env
from quality_console.table_kinds import (
    bucket_kind,
    database_kind,
    feature_kind,
    table_kind,
)
from quality_console.tools import TOOLS, NotFoundError, doc_of
from quality_console.tools.announcements import announcements_router
from quality_console.tools.apis import apis_router
from quality_console.tools.audio_assets import audio_assets_router
from quality_console.tools.bucket import bucket_router
from quality_console.tools.designs import designs_router
from quality_console.tools.docs import docs_router
from quality_console.tools.footprint import footprint_router
from quality_console.tools.gherkin import gherkin_router
from quality_console.tools.recordings import recordings_router
from quality_console.tools.vault import vault_router
from quality_console.vault_view import VaultReader
from test_results.reader import RunNotFoundError

TEMPLATES = Jinja2Templates(directory=Path(__file__).parent / "templates")
"""The console's pages, rendered on the server like a classic back office."""

STATIC_DIR = Path(__file__).parent / "static"
"""Images the pages show, served as they are."""

LINK_DETAILS = {
    "QA mailbox": ("📬", "Mailpit: every email of the identity service. No login."),
    "Observability": ("📈", "Grafana on the traces of the last 15 minutes. No login."),
    "Message broker": ("🐇", "RabbitMQ management UI. Login guest / guest."),
    "Vault": ("🔐", "HashiCorp Vault, dev mode. Token root."),
    "Contract mocks (Prism)": (
        "🎭",
        "Prism: every OpenAPI contract of contracts/ answered as a mock under"
        " /<name>/, requests checked against the contract. One answer per"
        " operation, for anyone to try an API. The tests replay recorded answers"
        " with Microcks instead (Recorded examples). No login.",
    ),
}
"""Icon and what to know of each service running beside the console."""

STOREFRONT_PRODUCTS = (
    (
        "customer-welcome",
        "welcome",
        "Customer welcome",
        "Greet a customer: reads the database, counts the visit in Redis.",
    ),
    (
        "checkout",
        "checkout",
        "Checkout",
        "Place an order: writes orders, stock, invoices, payments, step by step.",
    ),
    (
        "account-access",
        "account",
        "Account access",
        "Sign in, sign up, reset: writes the users, emails the QA mailbox.",
    ),
)
"""Catalog product, anchor, name and purpose of each product of the storefront."""


def sections_router() -> APIRouter:
    """Build the pages of the DevX and utility sections, and the tips.

    Returns:
        The router to include in the console.
    """
    router = APIRouter()

    @router.get("/devx", response_class=HTMLResponse)
    def devx(request: Request) -> HTMLResponse:
        """The developer tools."""
        return TEMPLATES.TemplateResponse(request, "devx.html")

    @router.get("/devx/tips", response_class=HTMLResponse)
    def tips(request: Request) -> HTMLResponse:
        """Short reminders, one tab per topic."""
        return TEMPLATES.TemplateResponse(request, "tips.html")

    @router.get("/utility", response_class=HTMLResponse)
    def utility(request: Request) -> HTMLResponse:
        """The utility tools."""
        return TEMPLATES.TemplateResponse(request, "utility.html")

    return router


def create_app(settings: ConsoleSettings) -> FastAPI:
    """Build the console.

    Args:
        settings: Everything the console reads and calls.

    Returns:
        The FastAPI application, ready to be served.
    """
    browser = DatabaseBrowser(settings.database)
    catalog = CatalogReader(settings.database)
    app = FastAPI(title="Quality Console")
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    TEMPLATES.env.globals["tools"] = TOOLS
    TEMPLATES.env.globals["doc_of"] = doc_of
    TEMPLATES.env.globals["table_kind"] = table_kind
    TEMPLATES.env.globals["database_kind"] = database_kind
    TEMPLATES.env.globals["bucket_kind"] = bucket_kind
    TEMPLATES.env.globals["feature_kind"] = feature_kind
    app.include_router(
        results_router(settings.results, settings.rebuild_index, TEMPLATES)
    )
    app.include_router(database_router(browser, TEMPLATES))
    app.include_router(catalog_router(catalog, TEMPLATES, settings.results))
    app.include_router(
        apis_router(
            catalog,
            settings.contracts,
            TEMPLATES,
            settings.links.get("Contract mocks (Prism)"),
        )
    )
    app.include_router(
        gherkin_router(
            catalog,
            settings.features,
            settings.runner,
            TEMPLATES,
            live={
                product: f"{settings.storefront}/#{anchor}"
                for product, anchor, _, _ in STOREFRONT_PRODUCTS
            },
        )
    )
    app.include_router(docs_router(settings.docs, TEMPLATES))
    app.include_router(announcements_router(settings.announcements, TEMPLATES))
    app.include_router(designs_router(settings.designs, settings.features, TEMPLATES))
    app.include_router(
        recordings_router(settings.capture, settings.contracts, TEMPLATES)
    )
    app.include_router(
        footprint_router(
            FootprintLab(
                settings.database,
                settings.api,
                settings.tempo,
                fronts=settings.fronts,
            ),
            TEMPLATES,
        )
    )
    app.include_router(bucket_router(settings.storage, TEMPLATES))
    app.include_router(audio_assets_router(settings.audio_assets, TEMPLATES))
    app.include_router(
        vault_router(VaultReader(settings.vault) if settings.vault else None, TEMPLATES)
    )

    def page_context() -> dict[str, object]:
        return {
            "links": settings.links,
            "details": LINK_DETAILS,
            "storefront": settings.storefront,
            "products": STOREFRONT_PRODUCTS,
        }

    def not_found(request: Request, message: str) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request,
            "error.html",
            {"message": message},
            status_code=HTTPStatus.NOT_FOUND,
        )

    @app.exception_handler(RunNotFoundError)
    def unknown_run(request: Request, exc: RunNotFoundError) -> HTMLResponse:
        """Answer a ``404`` page for a run or a file the bucket does not hold."""
        return not_found(request, f"Unknown run or file: {exc}")

    @app.exception_handler(UnknownObjectError)
    def unknown_object(request: Request, exc: UnknownObjectError) -> HTMLResponse:
        """Answer a ``404`` page for a database, table or column nobody has."""
        return not_found(request, str(exc))

    @app.exception_handler(NotFoundError)
    def unknown_tool_item(request: Request, exc: NotFoundError) -> HTMLResponse:
        """Answer a ``404`` page for an API, feature or object nobody has."""
        return not_found(request, str(exc))

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request) -> HTMLResponse:
        """The tools of the quality platform and the ones running beside it."""
        return TEMPLATES.TemplateResponse(request, "home.html", page_context())

    @app.get("/tools", response_class=HTMLResponse)
    def tools(request: Request) -> HTMLResponse:
        """Every tool, with what it is for."""
        return TEMPLATES.TemplateResponse(request, "tools.html", page_context())

    app.include_router(sections_router())
    return app


def app_from_environment() -> FastAPI:
    """Build the console from its environment, the entry point uvicorn serves.

    Returns:
        The FastAPI application.
    """
    return create_app(settings_from_env())
