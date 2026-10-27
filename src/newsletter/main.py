"""HTTP layer of the newsletter service, reading the company database.

A small service of the storefront squad, deployed beside the storefront API.
Its telemetry names the service but no team: retro-footprint uses it to show
tables reaching the observability platform owned by nobody.
"""

from http import HTTPStatus

from fastapi import FastAPI, HTTPException, Path
from pydantic import BaseModel

from company_db import DatabaseSettings, connect, settings_from_environment

USERNAME_MAX_LENGTH = 50
"""Longest username the service accepts."""

FIND_CUSTOMER = (
    "SELECT c.id, p.language FROM customers c"
    " JOIN customer_preferences p ON p.customer_id = c.id"
    " WHERE c.username = %s AND c.status = 'active'"
)
"""An active customer and the language their newsletters are sent in."""

FIND_NEWSLETTERS = (
    "SELECT n.title FROM newsletter_subscriptions s"
    " JOIN newsletters n ON n.id = s.newsletter_id"
    " WHERE s.customer_id = %s ORDER BY n.sent_on"
)
"""The newsletters a customer subscribed to, oldest first."""

UNKNOWN_CUSTOMER = "Unknown customer"
"""Detail of the ``404`` answered for a username no active customer has."""


class Subscriptions(BaseModel):
    """The newsletters of one customer."""

    username: str
    language: str
    newsletters: list[str]


def create_app(database: DatabaseSettings) -> FastAPI:
    """Build the newsletter service.

    Args:
        database: Coordinates and credentials of the company database.

    Returns:
        The FastAPI application.
    """
    app = FastAPI(title="Newsletter service")

    @app.get("/newsletters/{username}")
    def newsletters(
        username: str = Path(min_length=1, max_length=USERNAME_MAX_LENGTH),
    ) -> Subscriptions:
        """The newsletters an active customer receives, and in which language."""
        name = username.strip().lower()
        with connect(database) as connection, connection.cursor() as cursor:
            cursor.execute(FIND_CUSTOMER, (name,))
            customer = cursor.fetchone()
            if customer is None:
                raise HTTPException(HTTPStatus.NOT_FOUND, UNKNOWN_CUSTOMER)
            cursor.execute(FIND_NEWSLETTERS, (customer[0],))
            titles = [str(row[0]) for row in cursor.fetchall()]
        return Subscriptions(
            username=name, language=str(customer[1]), newsletters=titles
        )

    return app


def app_from_environment() -> FastAPI:
    """Build the service from its environment, the entry point uvicorn serves.

    Returns:
        The FastAPI application.
    """
    return create_app(settings_from_environment())
