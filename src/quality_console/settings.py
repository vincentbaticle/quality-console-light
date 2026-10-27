"""Everything the Quality Console is wired to, built once at start-up."""

from collections.abc import Callable
from dataclasses import dataclass, field
import datetime
import os
from pathlib import Path

from google.cloud import storage
import httpx

from company_db import DatabaseSettings, settings_from_environment
from test_results.index import build_index
from test_results.models import IndexHeader
from test_results.reader import ResultsReader
from test_results.storage import open_bucket, open_client

STOREFRONT_VARIABLE = "PRODUCT_URL"
"""Variable holding the URL of the storefront, whose products the home page opens."""

LINK_VARIABLES = {
    "QA mailbox": "MAILBOX_URL",
    "Observability": "OBSERVABILITY_URL",
    "Message broker": "BROKER_URL",
    "Vault": "VAULT_UI_URL",
    "Contract mocks (Prism)": "MOCKS_URL",
}
"""Services running beside the console, by name, each from its URL variable."""

PATH_VARIABLES = {
    "contracts": "CONTRACTS_DIR",
    "features": "FEATURES_DIR",
    "designs": "DESIGNS_DIR",
    "capture": "CAPTURE_DIR",
    "docs": "DOCS_DIR",
    "announcements": "ANNOUNCEMENTS_DIR",
}
"""Folders of the repository the console reads, mounted read-only."""

RESULTS_BUCKET_VARIABLE = "RESULTS_BUCKET"
"""Variable naming the bucket CI uploads its test results to."""

RUNNER_URL_VARIABLE = "RUNNER_URL"
"""Root URL of the Gherkin runner."""

RUNNER_TIMEOUT_SECONDS = 330
"""Budget for one run of the runner, a bit more than its own."""

RUNNER_CONNECT_RETRIES = 2
"""New connections tried when the runner was restarted under a new address."""

API_URL_VARIABLE = "API_URL"
"""Root URL of the storefront API, which the retro-footprint calls."""

API_URL_VARIABLES = {"newsletter": "NEWSLETTER_URL"}
"""Root URL of each other API retro-footprint may call, by API name."""

FRONT_URL_VARIABLES = {
    "storefront": "FRONT_URL",
    "quality-console": "CONSOLE_URL",
}
"""Root URL of each front retro-footprint may open a page of, by front name."""

AUDIO_ASSETS_VARIABLE = "AUDIO_ASSETS_DIR"
"""Folder the audio asset generator writes into, mounted read-write."""

VAULT_VARIABLES = ("VAULT_ADDR", "VAULT_TOKEN")
"""Where Vault answers, and the console's own token (leases and metadata only)."""

TEMPO_URL_VARIABLE = "TEMPO_URL"
"""Root URL of Tempo's HTTP API, where the retro-footprint searches traces."""

CALL_TIMEOUT_SECONDS = 10
"""Budget for one call of the storefront API or of Tempo."""


@dataclass(frozen=True)
class ConsoleSettings:
    """What the console reads and calls.

    Attributes:
        database: The console's read-only account on the MySQL server.
        storefront: URL of the storefront page.
        links: Name and URL of each service running beside the console.
        results: Reads the test results bucket.
        rebuild_index: Rebuilds the run index of that bucket now.
        storage: Lists the buckets for the bucket browser.
        contracts: Folder of the API contracts.
        features: Folder of the Gherkin features.
        designs: Folder of the scenario designs.
        capture: Folder of the capture journals.
        docs: Folder of the documentation pages.
        announcements: Folder of the release announcements.
        audio_assets: Folder the audio asset generator writes into.
        runner: HTTP client of the Gherkin runner.
        api: HTTP client of the storefront API, for the retro-footprint.
        tempo: HTTP client of Tempo, ``None`` when no trace backend runs.
        fronts: HTTP client of each front, for retro-footprint, by name.
        apis: HTTP client of each other API, for retro-footprint, by name.
        vault: HTTP client of Vault with the console's token, None without one.
    """

    database: DatabaseSettings
    storefront: str
    links: dict[str, str]
    results: ResultsReader
    rebuild_index: Callable[[], IndexHeader]
    storage: storage.Client
    contracts: Path
    features: Path
    designs: Path
    capture: Path
    docs: Path
    audio_assets: Path
    announcements: Path
    runner: httpx.Client
    api: httpx.Client
    tempo: httpx.Client | None
    fronts: dict[str, httpx.Client] = field(default_factory=dict)
    apis: dict[str, httpx.Client] = field(default_factory=dict)
    vault: httpx.Client | None = None


def settings_from_env() -> ConsoleSettings:
    """Read the settings a deployment gives through the environment.

    Returns:
        The console's settings.
    """
    bucket = open_bucket(os.environ[RESULTS_BUCKET_VARIABLE])
    return ConsoleSettings(
        database=settings_from_environment(),
        storefront=os.environ[STOREFRONT_VARIABLE],
        links={
            name: os.environ[variable]
            for name, variable in LINK_VARIABLES.items()
            if os.environ.get(variable)
        },
        results=ResultsReader(bucket),
        rebuild_index=lambda: build_index(bucket, datetime.datetime.now(datetime.UTC)),
        storage=open_client(),
        contracts=Path(os.environ[PATH_VARIABLES["contracts"]]),
        features=Path(os.environ[PATH_VARIABLES["features"]]),
        designs=Path(os.environ[PATH_VARIABLES["designs"]]),
        capture=Path(os.environ[PATH_VARIABLES["capture"]]),
        docs=Path(os.environ[PATH_VARIABLES["docs"]]),
        announcements=Path(os.environ[PATH_VARIABLES["announcements"]]),
        audio_assets=Path(os.environ[AUDIO_ASSETS_VARIABLE]),
        runner=httpx.Client(
            base_url=os.environ[RUNNER_URL_VARIABLE],
            timeout=RUNNER_TIMEOUT_SECONDS,
            transport=httpx.HTTPTransport(retries=RUNNER_CONNECT_RETRIES),
        ),
        api=httpx.Client(
            base_url=os.environ[API_URL_VARIABLE], timeout=CALL_TIMEOUT_SECONDS
        ),
        tempo=httpx.Client(
            base_url=os.environ[TEMPO_URL_VARIABLE], timeout=CALL_TIMEOUT_SECONDS
        )
        if os.environ.get(TEMPO_URL_VARIABLE)
        else None,
        fronts={
            name: httpx.Client(
                base_url=os.environ[variable], timeout=CALL_TIMEOUT_SECONDS
            )
            for name, variable in FRONT_URL_VARIABLES.items()
            if os.environ.get(variable)
        },
        apis={
            name: httpx.Client(
                base_url=os.environ[variable], timeout=CALL_TIMEOUT_SECONDS
            )
            for name, variable in API_URL_VARIABLES.items()
            if os.environ.get(variable)
        },
        vault=httpx.Client(
            base_url=os.environ[VAULT_VARIABLES[0]],
            headers={"X-Vault-Token": os.environ[VAULT_VARIABLES[1]]},
            timeout=CALL_TIMEOUT_SECONDS,
        )
        if all(os.environ.get(v) for v in VAULT_VARIABLES)
        else None,
    )
