"""The bodies the tenant's routes share: what a sign-in sends and answers."""

import secrets

from pydantic import BaseModel, Field

from identity.store import User

EMAIL_MAX_LENGTH = 254
"""Longest address SMTP allows."""

PASSWORD_MAX_LENGTH = 128
"""Longest password accepted, so a pasted novel is never hashed."""


class Credentials(BaseModel):
    """What the sign-in form sends."""

    email: str = Field(min_length=3, max_length=EMAIL_MAX_LENGTH)
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class Session(BaseModel):
    """A successful sign-in."""

    user_id: str
    email: str
    access_token: str

    @classmethod
    def of(cls, user: User) -> Session:
        """Open a session for a signed-in account, with a new token."""
        return cls(
            user_id=user.id, email=user.email, access_token=secrets.token_urlsafe(24)
        )
