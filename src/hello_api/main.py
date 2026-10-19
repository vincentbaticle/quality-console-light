"""HTTP layer: the greeting (database, Redis, bank) and the order routes."""

from collections.abc import Callable
from http import HTTPStatus
import os
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel
from redis import Redis

from company_db import DatabaseSettings, settings_from_environment
from hello_api.bank_partner import (
    BankPartner,
    BankPartnerUnavailableError,
    partner_key_from_environment,
)
from hello_api.customers import CustomerRepository
from hello_api.greeting import build_greeting, format_amount, visits_key
from hello_api.orders import orders_router
from order_workflow.broker import BrokerUrl, publisher, url_from_environment
from order_workflow.store import OrderStore

REDIS_URL_VARIABLE = "REDIS_URL"
"""Environment variable holding the Redis connection URL, set by whoever deploys."""

PARTNER_URL_VARIABLE = "PARTNER_URL"
"""Environment variable holding the Bank Partner root URL, set by whoever deploys."""

UNKNOWN_CUSTOMER = "Unknown customer"
"""Detail of the ``404`` answered for a username no active customer has."""

USERNAME_MAX_LENGTH = 50
"""Longest username the API accepts, so a pasted novel never reaches Redis."""

Username = Annotated[str, Query(min_length=1, max_length=USERNAME_MAX_LENGTH)]
"""``username`` query parameter, validated the same way by every route taking one."""


class Greeting(BaseModel):
    """Body of a successful hello."""

    message: str
    visits: int
    balance_cents: int | None


class Health(BaseModel):
    """Body of the health probe."""

    status: str


def create_app(
    redis_url: str,
    partner_url: str,
    database: DatabaseSettings,
    broker_url: BrokerUrl,
    partner_api_key: Callable[[], str] | None = None,
) -> FastAPI:
    """Build the application against its three neighbours.

    Args:
        redis_url: Where the visit counters live, for example
            ``redis://localhost:6379/0``.
        partner_url: Root URL of the Bank Partner, the real one or a mock.
        database: Coordinates of the company database holding the customers.
        broker_url: AMQP URL of the broker the order workflow runs through,
            or what gives it afresh (short-lived credentials).
        partner_api_key: Gives the key the bank issued us, sent on each call;
            None when the partner asks for none (Microcks).

    Returns:
        The FastAPI application, ready to be served.
    """
    redis = Redis.from_url(redis_url, decode_responses=True)
    partner = BankPartner(partner_url, partner_api_key)
    customers = CustomerRepository(database)
    app = FastAPI(title="Storefront API")
    app.include_router(orders_router(OrderStore(database), publisher(broker_url)))

    @app.get("/api/health")
    def health() -> Health:
        """Answer ``ok`` once Redis answers a ping."""
        redis.ping()
        return Health(status="ok")

    @app.get("/api/hello")
    def hello(username: Username) -> Greeting:
        """Greet a customer by first name, count its visits, add its balance."""
        first_name = customers.find_first_name(username)
        if first_name is None:
            raise HTTPException(HTTPStatus.NOT_FOUND, UNKNOWN_CUSTOMER)
        try:
            balance = partner.get_balance(username)
        except BankPartnerUnavailableError as exc:
            raise HTTPException(HTTPStatus.BAD_GATEWAY, str(exc)) from exc
        visits = int(redis.incr(visits_key(username)))
        amount: str | None = None
        balance_cents: int | None = None
        if balance is not None:
            amount = format_amount(balance.balance_cents, balance.currency)
            balance_cents = balance.balance_cents
        return Greeting(
            message=build_greeting(first_name, visits, amount),
            visits=visits,
            balance_cents=balance_cents,
        )

    return app


def app_from_environment() -> FastAPI:
    """Build the application from its environment, the entry point uvicorn serves.

    Returns:
        The FastAPI application.
    """
    return create_app(
        os.environ[REDIS_URL_VARIABLE],
        os.environ[PARTNER_URL_VARIABLE],
        settings_from_environment(),
        url_from_environment(),
        partner_key_from_environment(),
    )
