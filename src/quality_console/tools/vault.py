"""Vault: which credentials are out, for how long, and which one never expires.

The page reads Vault with the console's own token (leases and metadata only)
and shows each service's short-lived credentials, renewed then replaced by
the Vault Agent, beside the Bank Partner's long-lived key.
"""

import datetime

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from quality_console.vault_view import VaultReader, VaultState, age


def vault_router(reader: VaultReader | None, templates: Jinja2Templates) -> APIRouter:
    """Build the route of the Vault page.

    Args:
        reader: Reads Vault, None when the console runs without one.
        templates: The console's templates.

    Returns:
        The router to include in the console.
    """
    router = APIRouter(prefix="/devx/vault")

    @router.get("", response_class=HTMLResponse)
    def page(request: Request) -> HTMLResponse:
        """The roles and their live leases, the static secrets."""
        state = (
            reader.state()
            if reader
            else VaultState(error="No Vault configured (VAULT_ADDR is not set).")
        )
        now = datetime.datetime.now(datetime.UTC)
        return templates.TemplateResponse(
            request,
            "vault.html",
            {
                "section": "devx",
                "state": state,
                "age": lambda timestamp: age(timestamp, now),
            },
        )

    return router
