"""Write the OpenAPI contracts of our own HTTP services into ``contracts/``.

FastAPI generates each contract from the code; this script writes it down so
the catalog, the API docs page and a reviewer read the same file. Run it
after changing a route: ``mise run contracts:export``. A unit test fails
when a file drifts from its service.
"""

from collections.abc import Callable
from pathlib import Path
import sys
from typing import Any

from fastapi import FastAPI
import yaml

from company_db import DatabaseSettings
from gherkin_runner.main import create_app as create_runner
from hello_api.main import create_app as create_storefront
from identity.emails import Mailer
from identity.main import create_app as create_identity
from newsletter.main import create_app as create_newsletter

ROOT = Path(__file__).resolve().parent.parent
"""Root of the repository."""

NOWHERE = DatabaseSettings("localhost", 3306, "nobody", "", "none")
"""Database settings of an app built only to read its routes, never connected."""

SERVICES: dict[str, Callable[[], FastAPI]] = {
    "storefront-openapi.yaml": lambda: create_storefront(
        "redis://localhost", "http://localhost", NOWHERE, "amqp://localhost"
    ),
    "identity-openapi.yaml": lambda: create_identity(
        NOWHERE, Mailer("localhost", 25), "http://localhost:8080", "unused"
    ),
    "newsletter-openapi.yaml": lambda: create_newsletter(NOWHERE),
    "gherkin-runner-openapi.yaml": lambda: create_runner(ROOT, None, "local", "local"),
}
"""Each contract file and how to build the service it describes."""


def contract(build: Callable[[], FastAPI]) -> str:
    """The OpenAPI document of a service, as YAML."""
    document: dict[str, Any] = build().openapi()
    return yaml.safe_dump(document, sort_keys=False, allow_unicode=True)


def main() -> int:
    """Write every contract.

    Returns:
        The process exit code.
    """
    for name, build in SERVICES.items():
        (ROOT / "contracts" / name).write_text(contract(build))
        print(f"[contracts] contracts/{name} written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
