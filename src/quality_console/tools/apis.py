"""API docs: every contract of the catalog, Swagger UI for HTTP, a page for events."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
import yaml

from catalog.reader import CatalogReader, EntityRow
from quality_console.asyncapi import view
from quality_console.tools import NotFoundError

YAML_CONTENT_TYPE = "application/yaml"
"""Content type a contract is served with."""

OPENAPI_SUFFIX = "-openapi.yaml"
"""How an OpenAPI contract file ends; the mocks serve it under the rest."""


def mock_name(target: str | None) -> str | None:
    """Under which name the contract mocks serve a contract, if they do.

    Args:
        target: The definition path the catalog gives, ``contracts/x-openapi.yaml``.

    Returns:
        ``x`` for an OpenAPI contract, ``None`` otherwise (AsyncAPI, no file).
    """
    name = Path(target or "").name
    return name.removesuffix(OPENAPI_SUFFIX) if name.endswith(OPENAPI_SUFFIX) else None


def apis_router(
    catalog: CatalogReader,
    contracts: Path,
    templates: Jinja2Templates,
    mocks_url: str | None = None,
) -> APIRouter:
    """Build the routes of the API docs.

    Args:
        catalog: Lists the APIs and where their definition lives.
        contracts: The folder of the contracts, ``contracts/``.
        templates: The console's templates.
        mocks_url: Where the contract mocks answer, if they run.

    Returns:
        The router to include in the console.
    """
    router = APIRouter(prefix="/tools/apis")

    def find(name: str) -> tuple[EntityRow, Path]:
        """The API of that name and its definition file.

        Raises:
            NotFoundError: When the catalog has no definition for it.
        """
        api = next((a for a in catalog.apis() if a.name == name), None)
        if api is None or not api.target:
            raise NotFoundError(f"No contract for the API {name}")
        path = contracts / Path(api.target).name
        if not path.is_file():
            raise NotFoundError(f"Contract file missing: {api.target}")
        return api, path

    @router.get("", response_class=HTMLResponse)
    def apis(request: Request) -> HTMLResponse:
        """Every API of the catalog, with or without a contract."""
        found = catalog.apis()
        mocks = {
            api.name: f"{mocks_url}/{name}/"
            for api in found
            if mocks_url and (name := mock_name(api.target))
        }
        return templates.TemplateResponse(
            request,
            "apis.html",
            {"section": "tools", "apis": found, "mocks": mocks, "mocks_url": mocks_url},
        )

    @router.get("/{name}", response_class=HTMLResponse)
    def api(request: Request, name: str) -> HTMLResponse:
        """The documentation of one API, by the kind of its contract."""
        entity, path = find(name)
        if entity.type == "asyncapi":
            return templates.TemplateResponse(
                request,
                "api_asyncapi.html",
                {
                    "section": "tools",
                    "api": entity,
                    "doc": view(yaml.safe_load(path.read_text())),
                },
            )
        return templates.TemplateResponse(
            request, "api_openapi.html", {"section": "tools", "api": entity}
        )

    @router.get("/{name}/definition")
    def definition(name: str) -> Response:
        """The contract file itself, what Swagger UI loads."""
        _, path = find(name)
        return Response(path.read_text(), media_type=YAML_CONTENT_TYPE)

    return router
