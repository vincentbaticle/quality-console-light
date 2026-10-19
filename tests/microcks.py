"""Microcks replaying the Bank Partner from its contract and captured examples.

Microcks reads an OpenAPI file (the primary artifact) and the examples beside it
(the secondary artifact), then answers HTTP calls with the example whose request
matches. The API under test calls it exactly as it would call the real partner.
"""

from pathlib import Path
import time

import httpx

from tests.neighbours import PROJECT_ROOT

MICROCKS_IMAGE = "quay.io/microcks/microcks-uber:1.13.2"
"""Microcks all-in-one image, API and mocks on a single port."""

MICROCKS_PORT = 8080
"""Port Microcks listens on inside its container or sidecar."""

MICROCKS_URL_VARIABLE = "MICROCKS_URL"
"""Root URL of the Microcks sidecar, set by the CI job in sidecar mode."""

MICROCKS_ENV = {
    "JAVA_TOOL_OPTIONS": "-Xms128m -Xmx512m",
    "ASYNC_MINION_ENABLED": "false",
    "GRPC_ENABLED": "false",
    "GRAPHQL_ENABLED": "false",
}
"""Keeps Microcks to REST mocking, which cuts its boot time and memory."""

STARTUP_LOG_MARKER = "Started MicrocksApplication"
"""Log line printed once Microcks accepts artifacts and serves mocks."""

READINESS_TIMEOUT_SECONDS = 120
"""Budget for a sidecar to answer, generous enough for a cold CI runner."""

READINESS_POLL_SECONDS = 1.0
"""Delay between two readiness probes."""

UPLOAD_TIMEOUT_SECONDS = 30
"""Budget for one artifact upload, which parses and indexes the whole file."""

CONTRACTS_DIR = PROJECT_ROOT / "contracts"
"""Where the Bank Partner's contract and examples live."""

PRIMARY_ARTIFACT = CONTRACTS_DIR / "bank-partner-openapi.yaml"
"""Copy of the contract the partner publishes."""

SECONDARY_ARTIFACT = CONTRACTS_DIR / "bank-partner-examples.yaml"
"""Captured and hand-written examples Microcks answers with."""

MOCK_PATH = "/rest/Bank+Partner/1.0.0"
"""Where Microcks serves the partner: ``info.title`` (spaces as ``+``), then
``info.version`` of the contract."""


def wait_until_ready(base_url: str) -> None:
    """Poll a Microcks that may still be booting until its API answers.

    Args:
        base_url: Root URL of the Microcks instance.

    Raises:
        RuntimeError: When it never answered in time.
    """
    deadline = time.monotonic() + READINESS_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        try:
            ready = httpx.get(f"{base_url}/api/services").is_success
        except httpx.TransportError:
            ready = False
        if ready:
            return
        time.sleep(READINESS_POLL_SECONDS)
    raise RuntimeError(f"Microcks at {base_url} not ready")


def load_bank_partner(base_url: str) -> None:
    """Upload the Bank Partner's contract, then its examples.

    Args:
        base_url: Root URL of the Microcks instance.
    """
    _upload(base_url, PRIMARY_ARTIFACT, main_artifact=True)
    _upload(base_url, SECONDARY_ARTIFACT, main_artifact=False)


def _upload(base_url: str, artifact: Path, *, main_artifact: bool) -> None:
    """Post one artifact to the Microcks import endpoint.

    Args:
        base_url: Root URL of the Microcks instance.
        artifact: OpenAPI file to import.
        main_artifact: True for the contract, False for extra examples.

    Raises:
        RuntimeError: When Microcks refuses the file.
    """
    with artifact.open("rb") as content:
        response = httpx.post(
            f"{base_url}/api/artifact/upload",
            files={"file": (artifact.name, content, "application/x-yaml")},
            data={"mainArtifact": str(main_artifact).lower()},
            timeout=UPLOAD_TIMEOUT_SECONDS,
        )
    if not response.is_success:
        raise RuntimeError(f"Microcks refused {artifact.name}: {response.text}")
