"""The second factor's routes: the code that finishes a sign-in, the enrolment.

A right password on an account with a second factor answers ``403`` with
``mfa_required`` and an ``mfa_token``, as Auth0 does; the code of the
authenticator app, sent with that token, finishes the sign-in, once per code.
"""

import datetime
from http import HTTPStatus

from fastapi import APIRouter
from pydantic import BaseModel, Field

from identity.models import Credentials, Session
from identity.tenant import Tenant
from identity.totp import TOTP_DIGITS


class MfaCode(BaseModel):
    """What the code form sends: the token of the pending sign-in, the code."""

    mfa_token: str = Field(min_length=10, max_length=100)
    code: str = Field(pattern=rf"^\d{{{TOTP_DIGITS}}}$")


class TotpEnrollment(BaseModel):
    """A new second factor: shown once, to be kept where the tests read it."""

    secret: str
    otpauth_uri: str


def mfa_router(tenant: Tenant) -> APIRouter:
    """Build the second factor's routes.

    Args:
        tenant: The tenant the codes are checked against.

    Returns:
        The router to include in the identity service.
    """
    router = APIRouter(prefix="/api/identity/mfa")

    @router.post("/verify")
    def verify_code(body: MfaCode) -> Session:
        """Finish a sign-in with the code of the authenticator app, once per code."""
        now = datetime.datetime.now(datetime.UTC)
        return Session.of(tenant.verify_code(body.mfa_token, body.code, now))

    @router.post("/enroll", status_code=HTTPStatus.CREATED)
    def enroll(body: Credentials) -> TotpEnrollment:
        """Give the account a second factor: its secret is shown this once."""
        enrollment = tenant.enroll(body.email, body.password)
        return TotpEnrollment(
            secret=enrollment.secret, otpauth_uri=enrollment.otpauth_uri
        )

    return router
