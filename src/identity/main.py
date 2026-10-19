"""A simulated Auth0 tenant: sign-up, sign-in, password emails, management tickets.

It behaves like the real tenant on the points tests depend on: emails are
stored in lowercase, a new account has no password until its owner opens the
link of the welcome email, a reset never says whether the account exists, ten
wrong passwords block the account and send an unblock email, the
Management API hands a password link without sending any email, and an
account with a second factor answers ``mfa_required`` to its password, then
signs in with the one-time code of its authenticator app, each code once.
"""

from http import HTTPStatus
import os
import secrets
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from company_db import DatabaseSettings, settings_from_environment
from identity.emails import Mailer
from identity.mfa import mfa_router
from identity.models import EMAIL_MAX_LENGTH, PASSWORD_MAX_LENGTH, Credentials, Session
from identity.store import UserStore
from identity.tenant import MFA_REQUIRED, MfaRequiredError, Tenant, TenantError

RESET_ACCEPTED = "If an account uses this email, a reset link is on its way"
"""Answer to every reset request, whether the account exists or not."""

ENVIRONMENT = {
    "smtp_host": "SMTP_HOST",
    "smtp_port": "SMTP_PORT",
    "public_url": "PUBLIC_URL",
    "management_token": "MANAGEMENT_TOKEN",
}
"""Environment variable holding each setting of the tenant."""


class EmailOnly(BaseModel):
    """What the sign-up and reset forms send."""

    email: str = Field(min_length=3, max_length=EMAIL_MAX_LENGTH)


class NewPassword(BaseModel):
    """What the set-password form sends: the ticket of the link, the password."""

    ticket: str = Field(min_length=10, max_length=100)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class Account(BaseModel):
    """A created account."""

    user_id: str
    email: str


class Message(BaseModel):
    """A plain answer."""

    detail: str


class PasswordTicket(BaseModel):
    """What the Management API answers: the link, no email sent."""

    ticket: str


def create_app(
    database: DatabaseSettings,
    mailer: Mailer,
    public_url: str,
    management_token: str,
) -> FastAPI:
    """Build the tenant against its database and its mail server.

    Args:
        database: The ``identity`` database, with an account that may write.
        mailer: Where the emails go.
        public_url: Where the storefront is served, the base of every link.
        management_token: Bearer token the Management API requires.

    Returns:
        The FastAPI application, ready to be served.
    """
    tenant = Tenant(UserStore(database), mailer, public_url)
    app = FastAPI(title="Identity API (simulated Auth0)")

    @app.exception_handler(TenantError)
    def refused(_request: Request, exc: TenantError) -> JSONResponse:
        """Answer a refusal of the tenant with its status and its reason."""
        return JSONResponse({"detail": exc.detail}, status_code=exc.status)

    @app.exception_handler(MfaRequiredError)
    def code_due(_request: Request, exc: MfaRequiredError) -> JSONResponse:
        """Ask for the code, with the token that carries the sign-in on."""
        return JSONResponse(
            {"detail": MFA_REQUIRED, "mfa_token": exc.mfa_token},
            status_code=HTTPStatus.FORBIDDEN,
        )

    app.include_router(mfa_router(tenant))

    @app.get("/api/identity/health")
    def health() -> Message:
        """Answer ``ok``."""
        return Message(detail="ok")

    @app.post("/api/identity/signup", status_code=HTTPStatus.CREATED)
    def signup(body: EmailOnly) -> Account:
        """Create an account and send the email that sets its password."""
        user = tenant.signup(body.email)
        return Account(user_id=user.id, email=user.email)

    @app.post("/api/identity/login")
    def login(body: Credentials) -> Session:
        """Sign in, count a wrong password, block at the limit, ask for a code."""
        return Session.of(tenant.login(body.email, body.password))

    @app.post("/api/identity/password-reset", status_code=HTTPStatus.ACCEPTED)
    def password_reset(body: EmailOnly) -> Message:
        """Send a reset link when the account exists, answer the same either way."""
        tenant.request_reset(body.email)
        return Message(detail=RESET_ACCEPTED)

    @app.post("/api/identity/password", status_code=HTTPStatus.NO_CONTENT)
    def set_password(body: NewPassword) -> Response:
        """Set the password of the link's account, once."""
        tenant.set_password(body.ticket, body.password)
        return Response(status_code=HTTPStatus.NO_CONTENT)

    @app.post(
        "/api/identity/management/tickets/password-change",
        status_code=HTTPStatus.CREATED,
    )
    def password_change_ticket(
        body: EmailOnly, authorization: Annotated[str, Header()] = ""
    ) -> PasswordTicket:
        """Give a password link without any email, as the Management API does."""
        if not secrets.compare_digest(authorization, f"Bearer {management_token}"):
            raise HTTPException(HTTPStatus.UNAUTHORIZED, "Management token required")
        return PasswordTicket(ticket=tenant.management_ticket(body.email))

    return app


def app_from_environment() -> FastAPI:
    """Build the tenant from its environment, the entry point uvicorn serves.

    Returns:
        The FastAPI application.
    """
    return create_app(
        settings_from_environment(),
        Mailer(
            os.environ[ENVIRONMENT["smtp_host"]],
            int(os.environ[ENVIRONMENT["smtp_port"]]),
        ),
        os.environ[ENVIRONMENT["public_url"]],
        os.environ[ENVIRONMENT["management_token"]],
    )
