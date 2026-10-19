"""What every acceptance scenario shares: the running stack, the scenario state.

The scenarios run against the stack ``mise run up`` started, on the URLs of
the environment (the runner service sets the compose aliases), and skip with
the reason when it is not running. ``--only-feature`` and ``--only-scenario`` narrow a
run to what the console's Run button asked for.
"""

from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
import os
from typing import Any

from google.auth.credentials import AnonymousCredentials
from google.cloud import storage
import httpx
import hvac
from playwright.sync_api import Browser, Page
import pytest
from pytest_bdd import given, parsers, then

from quality_console.scenario_template import ACTOR

URLS = {
    "storefront": ("STOREFRONT_URL", "http://localhost:8080"),
    "mailbox": ("MAILPIT_URL", "http://localhost:8025"),
    "console": ("CONSOLE_URL", "http://localhost:8081"),
    "storage_url": ("STORAGE_EMULATOR_HOST", "http://localhost:4443"),
    "partner": ("PARTNER_URL", "http://localhost:8090"),
    "vault": ("VAULT_ADDR", "http://localhost:8200"),
    "vault_token": ("VAULT_TOKEN", "tests-token"),
}
"""Each part of the stack a scenario talks to: its variable and local default."""

PROBE_TIMEOUT_SECONDS = 3
"""Budget for telling whether the stack runs."""


@dataclass(frozen=True)
class Stack:
    """Where the running stack answers."""

    storefront: str
    mailbox: str
    console: str
    storage_url: str
    partner: str
    vault: str
    vault_token: str

    def storage_client(self) -> storage.Client:
        """A Cloud Storage client on the stack's emulator, no credentials."""
        return storage.Client(
            project="local",
            credentials=AnonymousCredentials(),
            client_options={"api_endpoint": self.storage_url},
        )


@dataclass
class Context:
    """What a scenario remembers from one step to the next."""

    response: httpx.Response | None = None
    values: dict[str, Any] = field(default_factory=dict)


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Keep only the feature and scenario the run asked for."""
    feature = config.getoption("--only-feature")
    scenario = config.getoption("--only-scenario")
    if not feature and not scenario:
        return
    kept: list[pytest.Item] = []
    dropped: list[pytest.Item] = []
    for item in items:
        bound = getattr(getattr(item, "obj", None), "__scenario__", None)
        matches = bound is not None and (
            (not feature or bound.feature.rel_filename.endswith(feature))
            and (not scenario or bound.name == scenario)
        )
        (kept if matches else dropped).append(item)
    if dropped:
        config.hook.pytest_deselected(items=dropped)
        items[:] = kept


TOOL_TAG_PREFIX = "tool-"
"""Tags naming what drives a feature (pytest, k6...), shown by the console."""


def pytest_bdd_apply_tag(tag: str, function: Callable[..., object]) -> bool | None:
    """Keep the tool tags out of the pytest markers: they only label a feature."""
    return True if tag.startswith(TOOL_TAG_PREFIX) else None


@pytest.fixture(scope="session")
def stack() -> Stack:
    """The running stack, or a skip saying how to start it."""
    urls = {name: os.environ.get(var, default) for name, (var, default) in URLS.items()}
    try:
        httpx.get(f"{urls['storefront']}/api/health", timeout=PROBE_TIMEOUT_SECONDS)
    except httpx.TransportError as exc:
        pytest.skip(f"The stack is not running, start it with mise run up: {exc}")
    return Stack(**urls)


BANK_PARTNER_SECRET = "bank-partner"
"""Path under ``secret/`` of the key the bank issued us."""


@pytest.fixture(scope="session")
def partner_api_key(stack: Stack) -> str:
    """The Bank Partner's key, read from Vault like any test credential.

    The tests token may read this one path: a test asks Vault, never a file of
    the repository, for what it needs to call a partner.
    """
    vault = hvac.Client(url=stack.vault, token=stack.vault_token)
    secret = vault.secrets.kv.v2.read_secret(path=BANK_PARTNER_SECRET)
    return str(secret["data"]["data"]["api_key"])


@pytest.fixture
def page(browser: Browser) -> Iterator[Page]:
    """A fresh browser page per scenario, for the steps that click the storefront.

    Built here because ``context`` names the scenario's memory in these steps,
    where pytest-playwright's own ``page`` expects its browser context.
    """
    browser_context = browser.new_context()
    yield browser_context.new_page()
    browser_context.close()


@pytest.fixture
def context() -> Context:
    """A fresh memory for each scenario."""
    return Context()


@then(parsers.parse("the storefront answers {status:d}"))
@then(parsers.parse("the console answers {status:d}"))
def answers(context: Context, status: int) -> None:
    """The last call answered this status code."""
    assert context.response is not None
    assert context.response.status_code == status, context.response.text


@given(parsers.re(ACTOR.pattern))
def actor_plays(context: Context, actor: str, account: str, rights: str) -> None:
    """Declare who plays: the account and its rights are test data too."""
    context.values.setdefault("actors", {})[actor] = (account, rights)
