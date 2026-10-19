"""What Vault has handed out: the short-lived credentials alive now, the long-lived key.

The console reads Vault with a token of its own whose policy lists leases and
reads metadata, never a secret value. Each service's short-lived credentials
are a lease on a role (a MySQL user, a RabbitMQ user) that the Vault Agent
renews until its maximum life, then replaces; the Bank Partner's key is a
static secret the bank issued once and rotates itself.
"""

from dataclasses import dataclass, field
import datetime
from typing import Any

import httpx

DYNAMIC_ROLES = (
    ("database", "hello-api", "MySQL user on mycompany and orchestrator"),
    ("database", "order-worker", "MySQL user on mycompany and orchestrator"),
    ("database", "identity-service", "MySQL user on identity"),
    ("rabbitmq", "hello-api", "RabbitMQ user publishing the order events"),
    ("rabbitmq", "order-worker", "RabbitMQ user consuming and publishing them"),
)
"""Every short-lived credential the stack hands out: engine, role, what it opens."""

STATIC_SECRETS = (
    (
        "bank-partner",
        "Bank Partner API key",
        "Issued once by the bank to us, its client; long-lived, rotated by the bank.",
    ),
)
"""Every long-lived secret: its path under ``secret/``, its title, its story."""

TIMEOUT_SECONDS = 5
"""Budget for one call to Vault."""


@dataclass(frozen=True)
class Lease:
    """One credential handed out and still alive."""

    lease_id: str
    issued: str
    expires: str
    ttl_seconds: int
    renewed: bool


@dataclass
class DynamicRole:
    """A role of a secrets engine, its lifetimes and its live leases."""

    engine: str
    role: str
    opens: str
    default_ttl: int = 0
    max_ttl: int = 0
    leases: list[Lease] = field(default_factory=list)


@dataclass(frozen=True)
class StaticSecret:
    """A long-lived secret, known by its metadata only."""

    path: str
    title: str
    story: str
    created: str
    updated: str
    version: int


@dataclass
class VaultState:
    """Everything the page shows, or why Vault could not be read."""

    roles: list[DynamicRole] = field(default_factory=list)
    secrets: list[StaticSecret] = field(default_factory=list)
    error: str = ""


def _lease(data: dict[str, Any]) -> Lease:
    """A lease as ``sys/leases/lookup`` describes it."""
    return Lease(
        lease_id=data["id"],
        issued=data["issue_time"],
        expires=data["expire_time"],
        ttl_seconds=int(data["ttl"]),
        renewed=data.get("last_renewal") not in (None, data["issue_time"]),
    )


def seconds(value: str | int) -> int:
    """A Vault duration (``120``, ``"2m"``, ``"1h"``) in seconds.

    Args:
        value: As a role or a lease configuration gives it.

    Returns:
        The number of seconds.
    """
    if isinstance(value, int):
        return value
    units = {"s": 1, "m": 60, "h": 3600}
    if value and value[-1] in units:
        return int(value[:-1]) * units[value[-1]]
    return int(value or 0)


class VaultReader:
    """Reads leases and metadata with the console's own token."""

    def __init__(self, client: httpx.Client) -> None:
        """Point at Vault.

        Args:
            client: HTTP client on Vault, its token in ``X-Vault-Token``.
        """
        self._client = client

    def _get(self, path: str, method: str = "GET", body: Any = None) -> Any:
        response = self._client.request(method, f"/v1/{path}", json=body)
        if response.status_code == httpx.codes.NOT_FOUND:
            return {}
        response.raise_for_status()
        return response.json().get("data", {})

    def _role(self, engine: str, role: str, opens: str) -> DynamicRole:
        found = DynamicRole(engine, role, opens)
        if engine == "database":
            config = self._get(f"database/roles/{role}")
        else:
            config = {
                "default_ttl": (lease := self._get("rabbitmq/config/lease")).get("ttl"),
                "max_ttl": lease.get("max_ttl"),
            }
        found.default_ttl = seconds(config.get("default_ttl") or 0)
        found.max_ttl = seconds(config.get("max_ttl") or 0)
        prefix = f"{engine}/creds/{role}/"
        keys = self._get(f"sys/leases/lookup/{prefix}", method="LIST").get("keys", [])
        found.leases = sorted(
            (
                _lease(
                    self._get("sys/leases/lookup", "PUT", {"lease_id": prefix + key})
                )
                for key in keys
            ),
            key=lambda lease: lease.issued,
            reverse=True,
        )
        return found

    def _secret(self, path: str, title: str, story: str) -> StaticSecret:
        metadata = self._get(f"secret/metadata/{path}")
        return StaticSecret(
            path=f"secret/{path}",
            title=title,
            story=story,
            created=metadata.get("created_time", ""),
            updated=metadata.get("updated_time", ""),
            version=int(metadata.get("current_version", 0)),
        )

    def state(self) -> VaultState:
        """Every role with its live leases, every static secret's metadata.

        Returns:
            The state, or an empty one saying why Vault could not be read.
        """
        try:
            return VaultState(
                roles=[self._role(*role) for role in DYNAMIC_ROLES],
                secrets=[self._secret(*secret) for secret in STATIC_SECRETS],
            )
        except httpx.HTTPError as exc:
            return VaultState(error=f"Vault could not be read: {exc}")


def age(timestamp: str, now: datetime.datetime) -> str:
    """How long ago a Vault time was, in words.

    Args:
        timestamp: An RFC 3339 time as Vault writes it.
        now: The time it is.

    Returns:
        ``42 s``, ``3 min`` or ``2 h``.
    """
    when = datetime.datetime.fromisoformat(timestamp[:26].rstrip("Z") + "+00:00")
    elapsed = int((now - when).total_seconds())
    if elapsed < 60:
        return f"{elapsed} s"
    if elapsed < 3600:
        return f"{elapsed // 60} min"
    return f"{elapsed // 3600} h"
